# 智能体服务协议 v0.1
本文件是「调度助手」智能体服务（`agent/`）对外接口的唯一依据，与 CONTRACT.md（求解器）配套，`schema_version` 同为 "0.1"。本服务**不修改** CONTRACT.md 的任何字段。

## 设计原则（摘自 DECISIONS D08）
- 智能体只做三件事：理解自然语言指令并生成受控补丁、基于真实求解结果生成有据可查的解释、比较两次方案。
- 智能体**不输出**任何坐标、路线、车辆分配或箴件去向；不直接调用求解接口；所有补丁由前端展示给人确认后再提交 `/api/solve`。
- 任何解释文本中的数字都要能在「事实表」里找到；核对不通过则回退为模板文本。没有模型密钥时全部能力以模板/规则模式运行，核心流程不中断。
- 发送给模型的只有事实表与实体摘要（ID、时间窗、尺寸、费用等），不含坐标、不含凭据。

## 部署
- 独立 FastAPI 进程，默认 `127.0.0.1:8001`；前端经 Vite 代理 `/agent/*` 访问。与求解器（8000）零代码耦合，仅共享 JSON 协议。
- 配置来自环境变量（见 `agent/.env.example`）：`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）、`AGENT_MODEL`（默认 `deepseek-chat`）、`AGENT_TIMEOUT_S`（默认 30）。密钥缺失不是错误，服务进入模板模式。
- 任何 OpenAI 兼容接口均可替换，便于对接企业私有化部署的模型。

## 公共字段
- 请求均含 `schema_version: "0.1"`。
- 响应均含 `schema_version`、`mode: "llm" | "template"`、`model: string | null`、`warnings: string[]`。`mode` 反映本次响应实际由谁生成；回退时 `warnings` 写明原因。
- 输入非法：HTTP 422，错误外壳与 CONTRACT 相同 `{schema_version, error:{code:"INVALID_INPUT", message, details:[{path,message}]}}`。
- 模型不可用、超时或输出不合格**不返回 5xx**，改走模板并记录 `warnings`。

## 1. GET /agent/health
→ `{status:"ok", schema_version:"0.1", llm:{provider:"deepseek"|null, model:string|null, configured:boolean}}`

## 2. POST /agent/explain
请求：
```json
{"schema_version":"0.1","request":SolveRequest,"response":JobResponse,
 "focus":"overview"|"unassigned"|"unload"|"vehicle","vehicle_id":"V01"(focus=vehicle 时必填),"question":"可选的自由提问"}
```
- `response.status` 必须为 succeeded 或 partial，否则 422。
- `focus=unload` 生成「现场装卸作业单」：按车辆、按到站顺序列出每一步卸哪箱、注意事项（易碎、承托）；装货指引为卸货逆序，措辞必须与 D05 一致。

响应：
```json
{"schema_version":"0.1","mode":"llm","model":"deepseek-chat","warnings":[],
 "text":"Markdown，中文",
 "facts":FactSheet,
 "grounding":{"checked_numbers":12,"unmatched_numbers":[],"passed":true}}
```
- `facts` 为服务端从 request+response **确定性**推导的事实表（见下）。模型只看事实表。
- `grounding`：从 `text` 提取可识别的数字（阿拉伯数字含紧邻中文者、常见中文数字、「万 / 亿」倍率、百分数与「百分之 N」、时刻 HH:MM），逐个与事实表值匹配（允许四舍五入到 1 位小数、百分数与小数互转、分钟与 HH:MM 互转）。带单位的数字只在同类事实里找；子句只提到一个车辆 / 门店 ID 时，费用、里程、重量、分钟、百分数、时刻只在该实体的事实里找，不借用全局合计。有未匹配数字则带纠正提示重试一次；仍不通过则 `mode="template"`，`text` 换为模板文本，`warnings` 记录未匹配数字。核对是文本层面的拦截：证明被识别的数字都出现在事实表里，不证明句子语义正确；无法识别的表达不计入 `checked_numbers`。

### FactSheet
```
case:{case_id, store_count, box_count, vehicle_count, depot_departure_min}
run:{status, method, termination_reason, elapsed_ms, is_mock, data_source}
metrics: 与 CONTRACT metrics 完全相同的 12 个字段
vehicles:[{vehicle_id, store_ids, stop_count, box_count, distance_km, cost, fixed_cost, cost_per_km,
           return_min, volume_utilization, weight_utilization, max_weight_kg, loaded_weight_kg}]
stops:[{vehicle_id, store_id, arrival_min, service_start_min, departure_min, window_start_min, window_end_min, wait_min, slack_min}]
unassigned:[{store_id, box_count, reason_code, message}]
unload:[{vehicle_id, steps:[{step, store_id, box_id, fragile}]}]
diagnostics_count:int
repair: null | {provided:true, status, status_word, attempted_count, accepted_count, detected_count, rejected_count_recorded,
                truncated, omitted_count, initial_served_stores, final_served_stores, total_stores,
                initial_total_cost, final_total_cost, initial_used_vehicles, final_used_vehicles,
                same_served_set, cost_comparable, newly_served:[store_id],
                detected:[{vehicle_id, store_ids, reason_code}], accepted:[{event_id, store_ids, source_vehicle_id, target_vehicle_id, served_before, served_after}]}
        （2026-10-10 O04 增补：从 Result.repair_trace 确定性推导；旧响应无 trace 时为 null，与 not_needed 区分。模型不得把 rejected 说成 accepted，not_needed 不得称收益，same_served_set=false 不得给费用百分比。）
```
单车利用率由服务端按 request 独立重算，不信任响应里的任何合计。

## 3. POST /agent/interpret
请求：`{"schema_version":"0.1","request":SolveRequest,"instruction":"S07 今天只能 14 点以后收货，V02 不出车"}`

响应：
```json
{"schema_version":"0.1","mode":"llm","model":"deepseek-chat","warnings":[],
 "understood":true,
 "intent_ops":[{"action":"set","target":"store","id":"S07","field":"window_start_min","value":840},
               {"action":"remove_vehicle","target":"vehicle","id":"V02"}],
 "patch":[{"op":"replace","path":"/stores/6/window_start_min","value":840},
          {"op":"remove","path":"/vehicles/1"}],
 "patched_request":SolveRequest,
 "rejected_ops":[{"intent":{...},"reason":"字段 length_mm 不在允许修改范围"}],
 "summary":"将 S07 最早收货时间改为 14:00；移除车辆 V02。"}
```
- 模型输出的是 `intent_ops`（按 **ID** 指代实体），服务端把 ID 解析为下标生成 RFC 6902 `patch`，再应用并用协议模型校验 `patched_request`。模型不写下标、不写完整请求。
- 允许的操作（白名单，之外一律进入 `rejected_ops`）：
  - `set`：`depot.departure_min`；`stores[id].window_start_min|window_end_min|service_min`；`boxes[id].fragile|allow_rotate_xy`；`options.method|seed|time_limit_ms|max_iterations|speed_kmph`。
  - `remove_vehicle`：按 id 移除车辆（至少保留一辆）。
  - `add_vehicle`：`value` 为完整车辆对象，id 不得重复。
- 时刻可用 "14:00"、"下午两点"、"840" 表达，服务端统一为分钟。
- 校验失败（如时间窗颠倒）→ 该操作进入 `rejected_ops`，其余继续；`patched_request` 始终是通过校验的请求或 null。
- `understood=false`：无法映射到任何实体/字段，`patch=[]`，`summary` 说明需要澄清。
- 模板模式：规则解析器覆盖常见句式（改时间窗、改服务时长、车辆不可用、改时间预算、改车速）；覆盖不到的返回 `understood=false`。

## 4. POST /agent/compare
请求：`{"schema_version":"0.1","baseline":{"request":SolveRequest,"response":JobResponse},"candidate":{...},"instruction":"可选，说明两者差异来源"}`

响应：
```json
{"schema_version":"0.1","mode":"llm","model":"...","warnings":[],
 "deltas":{"served_stores":{"baseline":9,"candidate":10,"delta":1}, "...所有 metrics 字段"},
 "same_served_set":false,"both_valid":true,"comparable_cost":false,
 "cost_change_rate":null,
 "text":"Markdown，中文",
 "grounding":{...}}
```
- `comparable_cost` 按 EVALUATION 口径：两者 `validation.valid=true` 且已服务门店集合相同且基线费用>0；否则 `cost_change_rate=null`，文本必须先说明覆盖变化，不得给降本百分比。

## 变更
改本文件须同步 `agent/schemas.py`、前端 `frontend/src/protocol/agent.ts` 与 CHANGES.md。
