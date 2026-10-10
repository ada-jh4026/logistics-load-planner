# 执行手册变更记录

每次修改 docs/playbook 下的规格、决策或任务结构，在此追加一条：日期、改动者、原因、逐文件改动、不变的部分、需要重新验收的范围。

---

## 2026-10-10 增补智能体层（Agent lane）

改动者：前端/智能体线（Claude Code）。队友已口头认可增补方向。

### 原因
- 赛题原文在「智能体需解决问题示例」中直接使用智能体措辞；评审五维度中「技术创新」「业务价值」「企业落地」三项都需要 AI 层支撑。原手册把模型能力放在 P2，且「自然语言改规则」列为明确不做，与比赛定位不符。
- 增补方式：**不改求解器契约和算法**，在其之上加一个独立的「调度助手」服务。LLM 只做理解、解释、对比，不做任何调度决策；补丁需人确认后才提交求解。

### 逐文件改动
| 文件 | 改动 |
|---|---|
| `AGENT_CONTRACT.md` | 新增。智能体服务接口 v0.1：health / explain / interpret / compare，事实表、数字核对、白名单补丁的规则。 |
| `DECISIONS.md` | D03 增加智能体服务分层与端口 8001；D04 把智能体线 A01–A03 定为 P1（与前端并行，不占主线时间）；新增 D08 智能体层原则；D07 追加本次记录。 |
| `CONTRACT.md` | 末尾加一行指向 AGENT_CONTRACT.md。字段零改动。 |
| `ACCEPTANCE.md` | 新增 C13 指令解释、C14 解释证据绑定。 |
| `EVALUATION.md` | 新增「智能体评估」小节：指令测试集准确率、解释数字核对通过率、模型调用延迟。不影响 21 条求解对比记录。 |
| `SCHEDULE.md` | 填入绝对截止时刻（英国时间 2026-10-12 11:00）；增加智能体线排程与冻结时刻。 |
| `STATE.md` | 更新事实：分工、模型选型 DeepSeek、目录归属、分支策略、仓库与截止时间。 |
| `board.json` | 新增 lane `agent`：A01–A04；新增 F07 调度助手面板；F06 增加依赖 F07。 |
| `tasks/A01–A04.md`、`tasks/F07.md` | 新增任务卡。 |
| `HANDOFF.md` | 增加给智能体线模型的接力提示词。 |
| 根目录 `AGENTS.md` | 增加目录归属与直接推 main 的协作规则。 |
| 根目录 `README.md` | 分工表、服务端口、目录树加入 agent/。 |
| 根目录 `两天参赛执行计划.md` | 顶部加指向本记录的说明；第 2 节分工表更新。 |

### 不变的部分
CONTRACT.md 的 SolveRequest / JobResponse / Result / 错误码；ALGORITHMS.md 全部；B01–B16、I01–I04 任务卡；三组接口样例。

### 需要重新验收的范围
`python scripts/check_playbook.py` 通过（31 张卡）。其余为新增规格，由 A01 起的任务卡落实。

---

## 2026-10-10（晚）参赛材料与跨目录改动

改动者：前端/智能体线（Claude Code）。

| 文件 | 改动 |
|---|---|
| 根目录 `README.md` | 替换为参赛 README（I03）。原执行手册入口移至 `docs/playbook/README_playbook.md`，内容不变，顶部加一行说明。 |
| `START_HERE.md` | 入口表中的 README 链接改指向 `docs/playbook/README_playbook.md`。 |
| `docs/architecture.md`、`docs/limitations.md`、`docs/submission-checklist.md`、`docs/demo-script.md` | 新增。 |
| `artifacts/probes/` | 新增：路线构造费用口径探针脚本、可选补丁与说明。**未改 `backend/`**，是否采纳由主线决定。 |
| `artifacts/demo/` | 新增演示截图与索引。 |
| `agent/requirements.txt` | 去掉与 `requirements-dev.txt` 冲突的 pytest / httpx 钉。 |

不变：`backend/`、`tests/`、`data/`、`scripts/`、CONTRACT / ALGORITHMS / 任务卡。

---

## 2026-10-10 下一轮优化方案与模型交接（仅规划）

改动者：主线（Codex）。用户要求写好执行细节和给 Claude 的提示词，随后切换模型实施。

- 新增 `docs/optimization-plan.md`：O01–O06 分工、修复记录协议建议、冲突实验与增强基线、算法取舍、前端与事实表验收、演示与最终收口。
- 新增 `docs/handoffs/codex-optimization.md`、`docs/handoffs/claude-optimization.md`：可直接复制的分工提示词。
- 更新 START_HERE、STATE 的当前入口，避免下一模型误从已经完成的 B01 开始；更正 AGENTS 中“尚无产品代码”的过时事实描述。
- 本次没有修改运行接口、算法、实验结果或任务状态。`repair_trace` 是待实施建议；实施前必须同步 CONTRACT/DECISIONS/样例及两个消费端。O01–O06 尚未完成，执行者开始时登记任务。
- 当前材料为本地规划，未据此声称已推送、已联调或已正式提交。验收范围仅为文档及现有计划自检。

---

## 2026-10-10 O01 协同修复记录协议（执行中）

改动者：主线（Codex）。原基准 coupled 未触发修复，前端无法从最终方案复原真实修复动作；需要结构化、可检验的过程记录。

- 更新 CONTRACT.md 的 Result，追加可选 repair_trace v1；旧响应缺字段解析为 null。定义事件、已验证快照、状态、截断与计数语义。
- 更新 DECISIONS.md D07，记录原 0.1 版本追加字段的兼容范围及消费者交接要求；新增 O01/O02 任务卡并登记 board，初始仅 O01 in_progress。
- 运行接口旧字段、路由/装载/卸货约束及原 I02 结果不变。此项不是宣称修复算法有新的收益。
- 验收范围：backend 模型与 coupled 搜索的相关测试、API 真实 JSON、旧 JSON 解析、独立校验和文档自检；agent/frontend 严格消费端由 Claude 更新并独立联调。

## 2026-10-10 O02 合成冲突实验（已完成）

改动者：主线（Codex）。增加固定的 19 案对照集和仅实验内部的 sequential_reinsert 基线；公开 SolveRequest.options.method 与求解 API 不变。开发 seed 11 和正式变体 seed 22/33/44/55/66 分开；完整来源和限制见 `docs/conflict-results.md`。

- `data/conflict_cases/`、`scripts/generate_conflict_cases.py`：保存案例、证书和选案清单；两个代表输入复制到 `data/cases/` 供真实页面选取。
- `scripts/sequential_reinsert.py`、`scripts/conflict_benchmark.py`、`scripts/audit_conflict_benchmark.py`：第四对照、原始文件与复审。
- O02 全部 76 次独立校验通过；全量后端测试 176 passed。修复与简单 reinsert 在 10 个冲突案的覆盖和费用相同，卸货类没有端到端修复触发。详见 `artifacts/evidence/O02.md`。
- 无消费者协议新增；Claude 仍需按 O01 同步 agent/frontend 的 repair_trace 模型并完成真实联调。现有 I02 原始记录保留。

## 2026-10-10 O03 择优搬移与消融

改动者：主线（Codex）。原因：O02 发现首个可行搬移与简单重新插入打平，需要检验预算内候选择优的实际增益。新增 `tasks/O03.md`，`board.json` 标记 O03 完成，`STATE.md` 更新接力状态。公开请求/响应协议、O02 原始记录和前端/智能体目录保持不变。重新验收范围：后端 177 项测试、O03 60 次持久化输出独立复审；结论和局限见 `artifacts/evidence/O03.md`。

## 2026-10-10 H01 异构箱件配载与失败路线恢复

改动者：主线（Codex）；用户明确要求实际修复 Claude 在 `1c5054e` 报告的问题。

- 同步 ALGORITHMS A6/A7：增加逆站序分区、逐件可装入构造、异构承托面对齐、惰性候选枚举；为失败路线的逐店恢复保留总预算，恢复时保留已有有效路线并分散目标车辆候选。
- 独立 geometry/unloading/validation 规则保持不变，仍不允许跨箱共同承托；失败不声明物理不可行。接口无新增字段；修复 accepted 事件必须确实服务被移门店。
- 范围：backend、tests、scripts、data、主线文档和真实验收证据；不覆盖 Claude 的 frontend、agent、README、architecture。已有 repair_trace 消费端问题仍须 Claude 联调。
- 验收区分手工可行见证、开发复现集、未参与调试的种子；保留旧实现、原始请求/响应和代码快照。结果见 `docs/heterogeneous-results.md`、`artifacts/evidence/H01.md`。

---

## 2026-10-10 O04 消费端：repair_trace 兼容、修复面板、修复事实

改动者：前端/智能体线（Claude Code）。

| 文件 | 改动 |
|---|---|
| `agent/schemas.py`、`frontend/src/protocol/contract.ts` | 镜像 CONTRACT 的 RepairTrace / RepairEvent；缺字段与 null 均为「未提供记录」。 |
| `AGENT_CONTRACT.md` | FactSheet 增加 `repair` 字段（见上）。接口与端点不变。 |
| `agent/facts.py`、`agent/templates.py`、`agent/explain.py` | 修复事实的确定性推导与模板段落；模型提示增加第 6 条规则。 |
| `frontend/src/components/RepairPanel.tsx`、`lib/repair.ts`、`lib/archive.ts` | 协同修复面板（状态、计数、时间线、接受事件前后快照只读回放、实体高亮）；案例选择器新增「历史实验记录」组，直接引用 `artifacts/benchmarks/hetero-*` 的真实输出，覆盖 repaired / partially_repaired+截断 / budget_exhausted / unresolved / not_needed。 |

不变：求解器协议、`backend/`、主线实验记录。

