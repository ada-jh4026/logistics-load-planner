# 给 Claude：前端与智能体优化提示词

以下正文可直接复制发送，包含独立接手所需的主要要求；同一工作区另读 `docs/optimization-plan.md` 的 O04/O05、`docs/playbook/CONTRACT.md` 和 `docs/conflict-results.md`。

---

我们已完成当前一版联调。I02 已推送提交是 `b84a592`：21 次实验通过独立校验，coupled 与 sequential 相同，修复未触发。主线**已在本地完成 O01/O02，尚未推送**：Result 新增真实 `repair_trace`，19 案四法共 76 次全部通过独立校验。两类真实冲突中 coupled 有 10 次接受动作并恢复全服务；简单重新插入基线也同样恢复、费用相同，不能宣称 coupled 优于该基线。完整事实见 `artifacts/evidence/O01.md`、`artifacts/evidence/O02.md`、`docs/conflict-results.md`。请你负责 frontend/、agent/、README.md、docs/architecture.md、docs/limitations.md、docs/demo-script.md 和自己的验收证据。

请开始可独立完成的工作，并按下列要求推进：

**一、先做旧数据兼容和界面结构。**
新增“协同修复”区域。旧记录没有修复字段时显示“此记录未提供修复过程”，不要显示确定的 0 次。预留无需修复、成功、部分成功、未解决、预算退出、记录截断等状态。可以使用明确标注的 UI 样例开发，不得把它作为真实算法演示或实验。

**二、与主线统一字段后实现消费端。**
主线已在 Result 新增可选 `repair_trace`，字段以 docs/playbook/CONTRACT.md 和真实响应为准，不要自行发明字段或更改后端。**完整 JobResponse** 样例在 `artifacts/repair-trace/api-geometry-22/job_response.json`、`api-time-geometry-22/job_response.json`（真实 POST/GET API 响应）；无修复的 Result 样例在 `artifacts/repair-trace/small-11/response.json`。同目录有原始 request/validation。前端可选真实案例 `geometry-22`、`time-geometry-22` 已放入 `data/cases/`，运行 `/api/examples` 可发现；正式实验原始 JSON 在 `artifacts/benchmarks/o02-conflict-20261010/`。
你需同步 agent/schemas.py 的独立 Pydantic 模型和 frontend/src/protocol/contract.ts 的 Zod 模型，验证缺字段的旧 JSON 仍可读；不能只写 TypeScript 类型却忘记运行时解析。主线尚未做消费端联调；先升级消费者兼容，再与新后端一起重启联调，记录真实结果。

**三、展示真实修复事件。**
面板展示“发现冲突→尝试调整→接受或拒绝→最终验证”；拒绝事件可折叠。选择接受事件时联动门店、车辆和箱件高亮，并展示真实前后指标。3D 前后布局只读取后端快照，不能从错误文字推测坐标。没有失败布局时只展示真实诊断与实体高亮，非法候选不能画成最终执行方案。
成本前后对比必须检查服务门店集合是否相同；服务更多但费用增加时先解释覆盖变化，不硬算降本率。无需修复与缺记录分别显示。

**四、调度助手依据事实解释修复。**
扩充 agent/facts.py 等确定性事实表，提供真实动作、实体、原因、校验和统计；模板模式必须可用。优先在现有总览/本车解释中加入事实，暂不扩展 explain focus。LLM 不生成调度动作或坐标；不得将 rejected 说成 accepted，不得对 not_needed 结果声称协同修复降本。数字核对只能证明数字匹配，动作解释尽量使用确定性文本；仍保留原有重试、回退和人工确认。
不要改主线的求解器协议。智能体协议如需调整，记录 AGENT_CONTRACT/CHANGES 并交接，避免和主线同时编辑同一文件。

**五、测试、演示和材料。**
覆盖旧响应、无需修复、真实成功修复、未解决、预算退出、截断等状态；跑 agent 测试、前端构建与真实浏览器联调。离线测试用 FakeLLM；有密钥时补实际模型联调并记录 mode，无密钥不阻断模板流程。逐项核对页面数字、实体与动作和原始 JSON，记录控制台异常与截图。
使用主线已交付的真实 `geometry-22` 或 `time-geometry-22` 案例录制三分钟流程：业务问题→顺序法的真实冲突→coupled 修复→装卸验证→一句自然语言调整、字段确认与重算→实验边界。请同时明确简单重新插入基线在这 10 个冲突案例上与 coupled 持平，不用手工样例拼接成独有增益。
最后更新 README/架构/限制/演示脚本：常规基准与冲突实验分表引用原始记录；不要把已有 4.73%–19.61% 降本归因于修复，也不要把 O02 的服务恢复误述为优于简单重新插入基线。不要由少量规模点宣称耗时近似线性。主张聚焦约束反馈修复、独立校验、人工确认和有据解释，不宣称全新算法或企业实测收益。

工作顺序：同步现有协议和兼容空态→接入类型、面板和事实表→用已交付的真实案例联调→更新材料。请保留主线实验和算法目录，不要代改 backend/tests/scripts/data。

交付 artifacts/evidence/O04.md、artifacts/demo/repair/，说明修改文件、实际命令及退出结果、协议兼容、真实案例 ID、原始 JSON 路径、截图、模型模式、尚未完成项和提交状态。board 由主线统一更新。遵循仓库协作规则；不自动正式提交或邀请评审，推送按用户指令执行。

---

说明：本地工作区已包含实际 CONTRACT、真实 request/response/validation 和两条前端可选案例。若 Claude 在另一台机器上工作，应先同步本轮尚未推送的文件；仅收到这段提示词时可先做旧数据兼容和面板结构，不能据此假定本机已有后端改动。
