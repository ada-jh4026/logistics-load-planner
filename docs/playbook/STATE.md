# 当前事实与接力状态
更新时间：2026-10-10（下一轮优化交接）
阶段：原有后端、前端、智能体及 I01–I03 已有完成记录；O01/O02 已在提交 `df6fa93` 推送。O03 已实施并验收；Claude O04 消费端和 I04 最终验收待办。方案见 `docs/optimization-plan.md`，结果见 `docs/conflict-results.md` 与 `artifacts/evidence/O03.md`。

## 已确定的事实
- 比赛窗口：英国时间 2026-10-10 11:00 开始，**2026-10-12 11:00 截止**（北京时间 10-12 18:00）。内部冻结 10-12 07:30，提交 09:30。提交渠道以赛事通知为准。
- 仓库：https://github.com/ada-c38f0bb79f/logistics-load-planner（私有，main）。两人直接推 main；推前先 `git pull --ff-only`；各自只改自己目录；不 force push。
- 分工：队友（主线，GPT 系列工具）负责 `backend/` `tests/` `scripts/` `data/` 及根目录 Python 依赖与 board.json 主线状态；本方（Claude Code）负责 `frontend/` `agent/` `README.md` `docs/architecture.md` 及最终提交。`docs/playbook/` 的智能体相关文件由本方维护，其余由主线维护。
- 模型：DeepSeek API（OpenAI 兼容），模型名默认 deepseek-chat；无密钥时智能体走模板模式。
- 技术栈：后端 Python + FastAPI（8000）；智能体 Python + FastAPI（8001）；前端 Vite + React + TypeScript + Three.js（5173）。

## 已完成
- 官方赛题与提交要求已读取；两方对齐选择「城市配送智能配载」。
- 执行手册：求解器契约 v0.1、算法细则、验收 C01–C14、26+5 张任务卡、三组 UI 样例。
- 2026-10-10 增补智能体层（见 CHANGES.md）：AGENT_CONTRACT.md、D08、A01–A04、F07。`python scripts/check_playbook.py` 通过，31 张卡依赖无环。
- 历史规划材料本身不是运行证据；现有实现、实验与联调以 board 和下方接力记录中的证据为准。尚未据此完成官方提交。

## 下一步
- 主线：O01–O03 已完成；O03 仅胜过旧首可行策略的开发回归案，与简单重新插入仍持平。待 Claude 交接后做 O05/O06 和 I04。
- 前端/智能体线：最新协议与真实案例已在本地工作区，交接提示词见 `docs/handoffs/claude-optimization.md`；同步严格模型、完成 O04 真实联调并更新材料。
- 任何一方改 docs/playbook 规格先写 CHANGES.md。

## 尚待用户提供
- 队名、成员介绍（README「团队」表占位）。
- 赛事通知原文（提交渠道）。
- 真实模型调用此前已有验收；换机器时需另行配置本机 `agent/.env`（不入库），模板模式不依赖密钥。

## 接力记录（完成任务后追加）
日期/任务ID/完成者/变更文件/实际命令与结果/证据路径/下一步/阻塞项。
- 2026-10-10 / 手册增补 / 本方 / 见 CHANGES.md / `py -3.13 -I scripts/check_playbook.py` PASS 31 cards / CHANGES.md / 下一步 F01、A01 / 无阻塞。
- 2026-10-10 / B01 / 主线（AI 助手）/ backend/__init__.py、backend/app.py、requirements.txt、requirements-dev.txt、tests/test_health.py、docs/environment.md、artifacts/evidence/B01.md / 环境 Python 3.14.8、Node v24.21.0；建 .venv 并装 fastapi 0.143.0、uvicorn 0.54.0、pytest 9.1.1、httpx 0.28.1；pytest 1 passed；uvicorn 8000 启动后 GET /api/health 返回 HTTP 200 `{"status":"ok","schema_version":"0.1"}` / 证据 artifacts/evidence/B01.md / 下一步 B02 / 阻塞：无（DSH 沙箱 + Python 3.14 os.mkdir(mode) 问题已用 sitecustomize.py 规避，详见 docs/environment.md）。
- 2026-10-10 / B02 / 主线（AI 助手）/ backend/models.py、tests/test_models.py、artifacts/evidence/B02.md / pydantic v2 定义 SolveRequest/JobResponse/Result 等模型 + 字段/跨字段校验；pytest 24 passed（含样例解析、重复ID、未知门店、负/零尺寸、NaN/Infinity、反向时间窗、非法 options）；全量 25 passed 无回归 / 证据 artifacts/evidence/B02.md / 下一步 B03 / 阻塞：无。
- 2026-10-10 / B03 / 主线（AI 助手）/ scripts/__init__.py、scripts/generate_cases.py、tests/test_data.py、data/cases/、data/witnesses/、artifacts/evidence/B03.md / 生成固定案例 c01/c02/c03/c07 + small/standard/stress 各 seed（10店36箱、30店112箱、60店236箱）；等规格箱地板布局见证；pytest 12 passed；全量 37 passed / 证据 artifacts/evidence/B03.md / 下一步 B04 / 阻塞：无。
- 2026-10-10 / B04 / 主线（AI 助手）/ backend/network.py、backend/metrics.py、tests/test_routing.py、tests/test_metrics.py、artifacts/evidence/B04.md / distance_km/travel_min/schedule_route/compute_metrics；C01 手算 10km/120元/服务500/回仓515/利用率0.5·0.3 断言通过；pytest 11 passed；全量 48 passed / 证据 artifacts/evidence/B04.md / 下一步 B05 / 阻塞：无。
- 2026-10-10 / B05 / 主线（AI 助手）/ backend/routing.py、tests/test_route_builders.py、artifacts/evidence/B05.md / build_greedy_routes（尾插）+ build_insertion_routes（全位置插入 + 2 轮 2-opt）；门店原子分配、必要条件通过、确定性；pytest 11 passed；全量 59 passed / 证据 artifacts/evidence/B05.md / 下一步 B06 / 阻塞：无。
- 2026-10-10 / B06 / 主线（AI 助手）/ backend/geometry.py、tests/test_geometry.py、artifacts/evidence/B06.md / oriented_size/intersects/inside_vehicle/find_support/validate_layout；C04 易碎承托、面接触不碰撞、浮空/跨箱/越界/旋转禁止；pytest 15 passed；全量 74 passed / 证据 artifacts/evidence/B06.md / 下一步 B07 / 阻塞：无。
- 2026-10-10 / B07 / 主线（AI 助手）/ backend/unloading.py、tests/test_unloading.py、artifacts/evidence/B07.md / generate/validate_unload_steps + loading 逆序；C05 阻挡与交换通过、C06 抽底拒绝、生成与验证分离；pytest 9 passed；全量 83 passed / 证据 artifacts/evidence/B07.md / 下一步 B08 / 阻塞：无。
- 2026-10-10 / B08 / 主线（AI 助手）/ backend/validation.py、tests/test_validation.py、artifacts/evidence/B08.md / validate_solution + validate_vehicle_candidate；分配完整性→车辆唯一→时间/载重→布局→卸货→指标全链校验；C09 篡改全检出、成功样例通过；pytest 9 passed；全量 92 passed / 证据 artifacts/evidence/B08.md / 下一步 B09 / 阻塞：无。
- 2026-10-10 / B09 / 主线（AI 助手）/ backend/packing.py、tests/test_packing.py、artifacts/evidence/B09.md / pack_route 确定性3D配载启发式（逆配送序+候选边界生成+评分+3排序）；C02 尺寸不合/旋转可放/堆叠/独立校验；pytest 7 passed；全量 99 passed / 证据 artifacts/evidence/B09.md / 下一步 B10 / 阻塞：无。
- 2026-10-10 / B10 / 主线（AI 助手）/ backend/baselines.py、tests/test_baselines.py、artifacts/evidence/B10.md / solve_greedy + solve_sequential 连通路线构造与 packer，整车失败退回 unassigned、validate_solution 复核；c01 全分配、c07 部分、c02/c03 未分配、small-11 无违规；pytest 12 passed；全量 111 passed / 证据 artifacts/evidence/B10.md / 下一步 B11 / 阻塞：无。
- 2026-10-10 / B11 / 主线（AI 助手）/ backend/budget.py、backend/routing.py、backend/packing.py、backend/baselines.py、tests/test_budget.py、artifacts/evidence/B11.md / Budget 单调时钟+迭代上限+预留10%校验时间；routing/packing 接入 tick；baselines 默认创建 Budget；假时钟超时终止、time/iteration 区分；pytest 8 passed；全量 119 passed / 证据 artifacts/evidence/B11.md / 下一步 B12 / 阻塞：无。
- 2026-10-10 / B12 / 主线（AI 助手）/ backend/solver.py、backend/repair.py、tests/test_coupled.py、tests/test_pipeline.py、artifacts/evidence/B12.md / solve 路由 + coupled 协同修复（移单到大车）；C10 单箱 2500 小车放不下→移到大车可执行、全箱有去向、超时不丢最佳；pytest 14 passed；全量 133 passed / 证据 artifacts/evidence/B12.md / 下一步 B13 / 阻塞：无。
- 2026-10-10 / B13 / 主线（AI 助手）/ backend/jobs.py、backend/app.py、tests/test_api.py、artifacts/evidence/B13.md / JobManager 单线程串行 + examples/solve/jobs 接口 + CORS + 422/404/429 错误外壳 + case_id 白名单；POST 202→轮询 succeeded/partial、is_mock=false；pytest 10 passed；全量 143 passed / 证据 artifacts/evidence/B13.md / 下一步 B14 / 阻塞：无。
- 2026-10-10 / B14 / 主线（AI 助手）/ backend/explanations.py、tests/test_explanations.py、docs/explanations.md、backend/solver.py、artifacts/evidence/B14.md / generate_explanation + loading_guide 从真实结果生成确定性解释；修复 coupled unassigned reason_code 丢失；无编造收益/修复；pytest 6 passed；全量 149 passed / 证据 artifacts/evidence/B14.md / 下一步 B15 / 阻塞：无。
- 2026-10-10 / B15 / 主线（AI 助手）/ scripts/benchmark.py、tests/test_benchmark.py、artifacts/benchmarks/smoke/、artifacts/evidence/B15.md / run_benchmark + cost_improvement 可比性保护；small 冒烟 9 runs 6 comparisons、改善率如实含负值；不可比输出 null+原因；pytest 5 passed；全量 154 passed / 证据 artifacts/evidence/B15.md / 下一步 B16 / 阻塞：无。
- 2026-10-10 / B16 / 主线（AI 助手）/ tests/test_regression.py、scripts/generate_cases.py、backend/solver.py、data/、artifacts/evidence/B16.md / 见证改用 pack_route 构造修复抽底 bug、coupled reason_code 修复；7 份见证全过独立校验；C01–C11 回归映射齐全；全量 162 passed / 证据 artifacts/evidence/B16.md / 下一步 I01（待 F05 前端联调）/ 阻塞：无。
- 2026-10-10 / F01–F04 / 本方 / frontend/ 全部、artifacts/evidence/F0{1..4}.md 与截图 / `npm run build` 退出 0，`npm run dev` 于 127.0.0.1:5173 / artifacts/evidence/ / 下一步 A01 / 无阻塞；F05 等 B13。
- 2026-10-10 / A01–A02 / 本方 / agent/ 全部、artifacts/evidence/A01.md A02.md / `.venv\Scripts\python.exe -m pytest -q agent/tests` 18 passed；uvicorn 8001 health 与 explain 实测 / artifacts/evidence/ / 下一步 A03 / 真实模型调用待密钥。
- 2026-10-10 / A03–A04 / 本方 / agent/interpret.py rules.py timeparse.py compare.py app.py schemas.py、agent/tests、agent/scripts/eval_interpret.py / `pytest -q agent/tests` 49 passed；`python -m agent.scripts.eval_interpret` 真实 DeepSeek 20/20；interpret/compare 接口实测 / artifacts/evidence/A03.md A04.md A03_eval.json A03_A04_live.json A02_live.json / 下一步 F05 → F07 → I01 / 无阻塞。密钥已配置，A02 真实调用证据已补。
- 2026-10-10 / F05 / 本方 / frontend/src/lib/api.ts useSolver.ts cases.ts、TopBar/App / 三服务同机：页面选 standard-11 运行 → 30/30 门店 12 车 4287.4 元 15 ms；c02 → 0/1 未配送 BOX_TOO_LARGE；后端日志 run_id 与页面一致；`npm run build` 通过 / artifacts/evidence/F05.md + 3 截图 + 日志摘录 / 下一步 F07 → I01 / 无阻塞。发现：sequential/coupled 在 standard-11 用 12 车 4287 元，greedy 6 车 2228 元，coupled 与 sequential 完全相同（修复未触发），已反馈主线。
- 2026-10-10 / F07、I01 / 本方 / frontend/src/protocol/agent.ts lib/agentApi.ts useAssistant.ts patchDescribe.ts markdown.tsx components/AssistantPanel.tsx App.tsx / 浏览器自动化：small-11 求解 → 模型解释核对 12 数 → 「V02 今天不出车」→ 确认重算 → 自动对比 4→3 车、1577.1→1270.7 元、可比 −19.4%；无控制台错误；`npm run build` 通过 / artifacts/evidence/F07.md I01.md + 6 截图 / 下一步 I03 / 无阻塞。
- 2026-10-10 / F06、I03 / 本方 / README.md（参赛版）、docs/architecture.md limitations.md submission-checklist.md demo-script.md、artifacts/demo/、artifacts/probes/、agent/requirements.txt / 全新 venv 按 README 安装 → 后端 162 + 智能体 49 = 211 测试通过；探针在完整管线验证增量费用口径（standard-11 12→5 车） / artifacts/evidence/F06.md I03.md / 下一步 I02（主线）、I04 / 待主线决定补丁、待用户补团队信息。I03 的 I02 依赖已解除：README 引用的是主线 B15 正式记录，I02 复核后数字若变再更新。
- 2026-10-10 / 同步修正 / 本方 / README 5.1 换 corrected-* 数据、5.3 与 F07/I01/demo 换修正后流程数字；agent/grounding.py 改半单位容差（0.5625→56.3% 不再误判），agent 51 测试通过；修正后后端上重跑全流程（模型模式，核对 23/12 个数字，+5.8% 可比） / artifacts/evidence/F07.md、screenshots、demo / 下一步 I04 / 待用户补团队信息。
- 2026-10-10 / I02 / 主线（Codex）/ artifacts/benchmarks/i02-20261010-{small,standard,stress}/、docs/results.md、artifacts/evidence/I02.md、board.json / 21 次正式重跑全部 completed、独立校验通过、180/180 门店；同案哈希与服务集合一致；C01 手算 10 km/¥120 无违规；coupled 较 greedy 降本 4.73%–19.61%，较 sequential 为 0%，协同修复未触发 / artifacts/evidence/I02.md / 下一步 I04 / 无阻塞，团队信息及外部提交仍待用户。
- 2026-10-10 / O01 / 主线（Codex）/ CONTRACT、DECISIONS、CHANGES、backend/models.py solver.py、tests/test_repair_trace.py、data/conflict_cases/trace-c10.json、scripts/capture_repair_trace.py、真实 JSON / C10 修复 0→1 店、small-11 无需修复、两者独立校验通过；相关 52 测试通过；当前沙箱全量测试停滞后中断 / artifacts/evidence/O01.md / 下一步 O02，Claude 消费端按协议更新 / 前端与智能体尚未联调新增字段。
- 2026-10-10 / O02 / 主线（Codex）/ data/conflict_cases、data/cases 代表案例、scripts/generate_conflict_cases.py sequential_reinsert.py conflict_benchmark.py audit_conflict_benchmark.py、docs/conflict-results.md、tests/ / 19 案四法共 76 次有效；独立复审 76/76，coupled 接受修复 10 次；全量后端测试在沙箱外 176 passed；新增简单重新插入基线在 10 个修复案与 coupled 覆盖和费用相同 / artifacts/evidence/O02.md、artifacts/benchmarks/o02-conflict-20261010/ / 下一步有条件 O03、Claude O04 联调、I04 / 未证明 coupled 超过简单补救，卸货端到端修复未触发。
- 2026-10-10 / O03 / 主线（Codex）/ backend/solver.py、tests/test_coupled.py、scripts/o03_benchmark.py audit_o03_benchmark.py、data/conflict_cases/ranked-geometry-22.json、docs/playbook O03 卡 / 20 案三变体 60/60 独立有效，复审 60/60，全量后端 177 passed；开发回归案 best 86 元、旧 first 146 元、reinsert 86 元 / artifacts/evidence/O03.md、artifacts/benchmarks/o03-ranked-20261010/ / 下一步 Claude O04、I04 / 尚未证明超过简单 reinsert。
- 2026-10-10 / O04 第一步（消费端兼容 repair_trace） / 本方 / agent/schemas.py、agent/tests/test_repair_trace_compat.py、frontend/src/protocol/contract.ts、frontend/scripts/check-protocol.mts / agent 57 passed；`npx tsx frontend/scripts/check-protocol.mts` 6 项通过；tsc 通过；新后端 geometry-22 真实响应 → agent explain 200（此前 422） / artifacts/evidence/O04-step1.md / 下一步 分区式配载补丁（artifacts/probes/，交主线合入）→ O04 面板 / 无阻塞。
- 2026-10-11 / O04（面板 + 修复事实） / 本方 / frontend RepairPanel.tsx lib/repair.ts lib/archive.ts App.tsx、agent facts/templates/explain/grounding、AGENT_CONTRACT FactSheet.repair、CHANGES / agent 63 passed；tsc+build 通过；浏览器自动化：5 种状态 + 旧响应 + 快照回放 + 实时 geometry-22 + 助手解释，无控制台错误 / artifacts/evidence/O04.md、artifacts/demo/repair/ / 下一步 KPI 行、卸货动画、方法对比、作业单打印 / 无阻塞。board 的 O04 卡由主线登记。
- 2026-10-11 / 前端易用性四项 / 本方 / KpiRow、CargoView 动画、useMethodCompare+MethodCompare、worksheet.ts（提交 f17aeda、3525c48、3e9cf8c、7951368）/ tsc+build 每项通过；浏览器自动化：对比表 small-11 三法数值、动画、作业单 17 行 + 截图 / artifacts/evidence/UI-polish.md、artifacts/demo/ui/ / 下一步 README/演示脚本同步新功能，等主线 I04 / 无阻塞。
- 2026-10-11 / 材料同步 / 本方 / README（核心方案含分区配载与逐店恢复、5.2 冲突实验、5.3 混合箱件实验、5.4 智能体含修复事实、5.5 端到端含面板/对比/作业单、限制）、docs/limitations.md、demo-script.md（第 3 段改为 geometry-22 修复演示、第 4 段加三法对比）、architecture.md / 全量 248 测试通过、check_playbook 通过、引用路径逐一存在 / — / 下一步 等主线 I04；用户补团队信息 / 无阻塞。
