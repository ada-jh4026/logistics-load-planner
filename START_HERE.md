# 从这里继续：两天物流赛题执行路线
本仓库已有可运行系统及实验/联调证据。O01–O03 已实施并验收；Claude 消费端联调和 I04 最终验收待办。方案见 `docs/optimization-plan.md`，实际结果见 `docs/conflict-results.md`、`artifacts/evidence/O03.md` 与 board。不要把尚未执行的后续建议或接口样例当作已完成能力。

## 新模型首次进入
1. 读 AGENTS.md。
2. 读 docs/playbook/STATE.md 和 board.json，了解事实与下一任务。
3. 读 docs/playbook/DECISIONS.md，再只读所领取的任务卡及其“必读材料”。
4. 检查任务对应文件是否已有他人修改；依赖任务未完成时不要假定它已经可用。
5. 一次领取一张任务卡。卡内步骤按序完成，运行验收，保存真实输出，更新进度。
6. 按 docs/playbook/HANDOFF.md 格式报告。用户明确要求连续推进时，可继续下一张依赖已满足的任务。

## 入口
- 当前进度：docs/playbook/STATE.md
- 任务与依赖：docs/playbook/board.json
- 两天排程：docs/playbook/SCHEDULE.md
- 不再反复讨论的设计：docs/playbook/DECISIONS.md
- 数据与API唯一规格：docs/playbook/CONTRACT.md
- 算法实现细则：docs/playbook/ALGORITHMS.md
- 正反验收案例：docs/playbook/ACCEPTANCE.md
- 实验及指标口径：docs/playbook/EVALUATION.md
- 给模型和同学的提示词：docs/playbook/HANDOFF.md
- 独立任务卡：docs/playbook/tasks/
- 接口示例：docs/playbook/examples/
- 官方背景与初版排期：两天参赛执行计划.md

## 立即执行
按用户最新指令与 STATE/board 接力，不重新执行已完成的 B01/F01。切换后的主线模型使用 `docs/handoffs/codex-optimization.md`；前端/智能体线使用 `docs/handoffs/claude-optimization.md`。在用户发出实施指令后落实任务、保存证据并更新状态。

默认分工：主线负责 backend/、tests/、scripts/、data/、docs/ 和根目录配置；同学负责 frontend/。主线维护 board.json，前端通过交接报告提供状态，避免两人同时改同一状态文件。

## 文档自检
在项目根目录运行：python scripts/check_playbook.py

该命令只检查计划、依赖、示例引用和任务状态一致性，不证明业务系统已实现或算法正确。

