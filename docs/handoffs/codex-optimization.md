# 给切换后的主线模型：执行提示词

以下为本轮开始时使用的执行指令。**2026-10-10 更新：O01、O02 已完成，见 `artifacts/evidence/O01.md`、`artifacts/evidence/O02.md`；不要重复执行。** 当前后续为有条件 O03、Claude O04、报告收口与 I04；先读 `docs/conflict-results.md` 和 board。

---

请接手 logistics-load-planner 的下一轮优化，按 `docs/optimization-plan.md` 执行。该方案是用户要求写好的待执行计划，不是已完成结果。先读 AGENTS.md、START_HERE.md、docs/playbook/STATE.md、board.json 和本方案，再检查工作区与远端最新代码；不要覆盖 Claude 的改动。

已知基准：`b84a592` 已推到 main，I02 的 21 次正式运行全部通过独立校验；coupled 相对 greedy 降本 4.73%–19.61%，但与 sequential 完全相同，不能把该降本归因于协同修复。原任务剩 I04，用户希望先继续优化，再最终验收。

请实际执行，不要再只给建议：
1. O01：先确定结构化修复记录协议，记 CHANGES/DECISIONS/CONTRACT。按方案建立可追溯的冲突、拒绝与接受事件，记录准确计数和已验证快照；测试旧响应兼容、成功、无需修复、未解决、预算退出和日志限长。发布真实 request/response/validation 供 Claude 接入。
2. O02：做组合几何、卸货顺序、时间窗联动三类冲突案例与控制例；固定规则/种子，保存所有结果。除了现有三方法，增加仅实验使用的简单重新插入基线，避免靠顺序法失败后放弃整车来制造优势。案例不能通过 coupled 成功筛选。
3. O03：依据 O02 的真实失败原因，优先考虑预算内择优搬移；只有顺序冲突成立才增加有限相邻交换。做消融，不承诺必然提升；记录跳过或无收益。
4. 继续完成不依赖 Claude 的实验报告、回归和入口事实更新。O04 的 UI 与 agent 由 Claude 负责；拿到交接后再验收 O05/O06 和 I04。

你拥有 backend/、tests/、scripts/、data/、docs/playbook/、实验报告与主线证据；Claude 拥有 frontend/、agent/、README、architecture/limitations/demo-script。不要未经协调修改他的目录。尤其 agent/schemas.py 是独立镜像，frontend/src/protocol/contract.ts 是 Zod 协议；新增字段要给对方明确交接，不能只改后端。

任务 O01–O06 目前只在方案中；开始实施时补真实任务卡与 board 状态，每阶段完成才填 evidence/done。协议先定，消费者兼容先行，随后重启联调。任何等待 Claude 的部分明确标注，继续独立工作，不伪造已联调。

重要边界：保留原 I02 证据；不同服务集合不能算降本率；SEARCH_EXHAUSTED 不等于数学不可行；失败布局不混入执行结果；不削弱校验、不硬编码收益、不新增大范围业务。用户没有要求新开聊天或派生代理，不自动创建。不自动推送本轮代码或正式提交，完成后报告可审查变更，遵循用户届时的推送指令。

每阶段交付真实命令、退出码、证据、版本、限制与下一步。优先交付可信实验和真实修复展示；若没有增益，也完整报告，不为满足预期挑选结果。

---

本轮规划材料位于本地工作区；如果切换到其他机器，先同步文件或把 `docs/optimization-plan.md` 一并提供给执行者。不要假定未推送的文件已经在 GitHub。
