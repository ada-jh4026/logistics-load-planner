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
