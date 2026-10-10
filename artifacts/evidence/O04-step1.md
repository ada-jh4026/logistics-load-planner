# O04 第一步：消费端兼容 repair_trace —— 验收证据

日期：2026-10-10（英国时间 22:10）。执行者：前端/智能体线（Claude Code）。基础提交 `1c5054e`（含主线 O01–O03）。

## 改动
- `agent/schemas.py`：按 CONTRACT v0.1 新增 `RepairEvent`、`RepairTrace` 严格模型（`extra="forbid"`），`Result.repair_trace: RepairTrace | None = None`。缺字段与显式 null 都解析为 None（「未提供记录」），`not_needed` 由 trace 自身状态表达。
- `frontend/src/protocol/contract.ts`：对应 Zod 模型；`ResultSchema.repair_trace` 为 `nullable().default(null)`，旧响应缺字段不再被丢弃为 undefined，而是明确 null。导出 `RepairTrace` / `RepairEvent` / `RepairStatus` 类型供 O04 面板使用。
- `frontend/scripts/check-protocol.mts`：运行时检查脚本，用真实响应与旧样例喂 Zod。
- `agent/tests/test_repair_trace_compat.py`：5 项。

## 实际命令与结果
```
.venv\Scripts\python.exe -m pytest -q agent/tests                 → 57 passed
npx --yes tsx frontend/scripts/check-protocol.mts                  → 6 项 PASS，全部通过
cd frontend && npx tsc -b                                          → exit 0
```
用例覆盖：
- 真实 `artifacts/repair-trace/api-geometry-22/job_response.json`、`api-time-geometry-22/job_response.json`（主线 O01 真实 POST/GET 产物）：status=repaired，accepted 事件带 before/after 快照，非 accepted 事件快照为 null。
- 旧样例 `docs/playbook/examples/response-success.json`、`response-partial.json`：缺字段 → null。
- `artifacts/repair-trace/small-11/response.json`（Result 外壳）：not_needed，0 事件。
- 非法 status 被两端拒绝。

## 真实联调（新后端 dfaf382 代码，重启后）
- `POST /api/solve` geometry-22 → `GET /api/jobs/{run_id}`：status=succeeded，`result.repair_trace.status=repaired`，2 个事件，2/2 门店。
- 把该响应原样发给 `POST /agent/explain`（focus=overview）：HTTP 200，mode=llm，核对 18 个数字全部匹配。修复前此请求会被 agent 严格模型以 422 拒绝。
- 浏览器加载 geometry-22 并运行：页面正常渲染，控制台无错误（截图 `_tools/shots/trace-g22.png`，未入库）。

## 尚未做（属 O04 后续步骤）
- 前端尚未展示 repair_trace 内容（面板、时间线、快照回放）。
- 事实表尚未加入修复事实；解释文本目前不提及修复过程。
