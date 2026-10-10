# 城市配送智能配载 · logistics-load-planner

「AI重构产业·架构师大赛」物流赛道作品。面向连锁门店城市配送：把订单、车辆、时间窗输入，输出每辆车的配送路线、每个箱件在车厢里的三维摆放、按到站顺序的卸货步骤，所有方案经独立校验器重算约束；一个调度助手智能体负责把结果解释给调度员、把一句话指令变成受人确认的修改、比较调整前后的方案。

> 当前版本运行在**模拟数据**上（字段与真实业务一致，数值为程序生成）。所有收益数字来自本仓库可复现的实验，不代表真实企业效果。

## 团队

| 角色 | 姓名 | 介绍 |
|---|---|---|
| 前端、智能体、文档与提交 | （待补） | （待补） |
| 求解器后端、数据与实验 | （待补） | （待补） |

开发过程中两名成员各自使用 AI 编程助手（Claude Code、GPT 系列），按 `docs/playbook/` 的任务卡逐张实现并留下验收证据（`artifacts/evidence/`）。

## 1. 业务场景与痛点

传化物流的城市配送场景：一个中心仓每天向几十家门店（赛题以连锁药店为例）配送几百个 SKU，调度员要在车辆容量、货物装载条件、门店交付时效的多重约束下，同时决定派哪些车、每辆车跑什么顺序、货物怎么装、到店怎么卸。赛题列出的五个痛点里，我们把**配载与配送计划缺乏协同**作为核心：总体积装得下不等于箱子真能摆进去；路线合理也不等于到站后前面的货取得出来。这两件事现在只能靠人到现场才发现。

目标用户是中心仓调度员与现场装卸人员。使用流程：导入当日订单与可用车辆 → 运行求解 → 查看路线、3D 装载与卸货步骤 → 对不满意的地方用一句话改约束（某门店只能下午收货、某车今天不出车）→ 确认后重算并对比 → 把装卸作业单给现场。

## 2. 核心方案

```
交互层  frontend/   调度工作台：路线 / 3D 车厢 / 逐步卸货 / 调度助手面板
决策层  backend/    路线构造 → 3D 配载 → 卸货可行性 → 协同修复 → 独立校验
智能体  agent/      事实表 → 证据绑定解释 / 一句话 → 受控补丁 / 方案对比
```
三个进程只通过两份 JSON 协议相连（`docs/playbook/CONTRACT.md`、`AGENT_CONTRACT.md`）。详细架构见 [docs/architecture.md](docs/architecture.md)。

**求解器**：门店按最晚收货时间排序后做路线构造（简单贪心尾插、全位置插入 + 2-opt 两种策略）；每辆车按卸货逆序做确定性 3D 配载（候选位置由已放箱边界生成，允许水平旋转，承托须由单个非易碎箱完整托住）；再逐站逐件模拟沿后门方向抽出，检查是否被挡、是否抽走了承托中的底箱。装不下或卸不出时，**协同修复**把冲突门店移到其他车的最佳插入位或新车，重新装载校验，保留最佳可行快照。最终方案由独立校验器重算全部约束，不信任求解器自报的结果。

**智能体**（LLM 不做调度决策）：
- 解释：服务端从请求与响应确定性推导「事实表」，模型只看事实表；回答中的每个数字、百分数、时刻都逐个核对，编造的数字触发重试，再不通过回退到模板文本。
- 指令：模型把「S07 下午两点后才能收货，V02 不出车」翻成按 ID 的意图；服务端检查白名单（时间窗、服务时长、易碎、旋转、求解选项、增减车辆），生成 RFC 6902 补丁并用协议校验；越权修改（改箱件尺寸、改车辆载重）被明确拒绝并说明。前端把补丁显示为字段级 diff，**人确认后**才提交求解。
- 对比：按「服务门店集合相同且均通过校验」判定费用是否可比；不可比时只讲覆盖变化，不给降本百分比。
- 无模型密钥时全部能力以模板模式运行，核心流程不中断。

## 3. 运行方式

环境：Python 3.12（3.13 亦可）、Node 22+。Windows 命令如下，macOS / Linux 把 `.venv\Scripts\python.exe` 换成 `.venv/bin/python`。

```bash
git clone https://github.com/ada-c38f0bb79f/logistics-load-planner.git
cd logistics-load-planner

# 后端 + 智能体共用一个虚拟环境
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r agent/requirements.txt

# 可选：模型密钥（不填则智能体为模板模式）
copy agent\.env.example agent\.env    # 填入 DEEPSEEK_API_KEY

# 三个服务，各开一个终端
.venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
.venv\Scripts\python.exe -m uvicorn agent.app:app   --host 127.0.0.1 --port 8001
cd frontend && npm install && npm run dev            # http://127.0.0.1:5173
```
打开页面，案例下拉里选「服务案例 standard-11」，点「运行求解」。

测试：
```bash
.venv\Scripts\python.exe -m pytest -q tests          # 后端 162 项
.venv\Scripts\python.exe -m pytest -q agent/tests    # 智能体 49 项，不依赖网络
cd frontend && npm run build                          # 类型检查 + 构建
```
实验：
```bash
.venv\Scripts\python.exe -m scripts.benchmark --suite small    --output artifacts/benchmarks/small
.venv\Scripts\python.exe -m scripts.benchmark --suite standard --output artifacts/benchmarks/latest
.venv\Scripts\python.exe -m scripts.benchmark --suite stress   --output artifacts/benchmarks/stress
.venv\Scripts\python.exe -m agent.scripts.eval_interpret        # 需密钥；模型模式指令解析准确率
```

## 4. 数据来源

- **模拟数据**：`scripts/generate_cases.py` 用固定随机种子生成，门店平面坐标、时间窗、箱件尺寸重量、两种车型。案例在 `data/cases/`：small（10 店 36 箱 4 车）、standard（30 店 112 箱 12 车）、stress（60 店 236 箱 24 车）各 3 / 3 / 1 个种子，以及 c01 / c02 / c03 / c07 四个验收案例。正常案例按「已知可行」构造，保证至少存在一个全配送方案。
- **手工界面样例**：`docs/playbook/examples/`，响应 `is_mock=true`，只用于前端开发与协议校验，页面上标「演示数据」。
- **距离与时间**：门店间为平面欧氏距离，固定车速换算；不是真实道路测算，页面与解释文本均注明。
- **人工环节**：验收案例的期望值由人工手算（`docs/playbook/ACCEPTANCE.md`）；指令测试集（`agent/tests/data/instructions.jsonl`）的 20 条指令与期望补丁由人工编写。
- 晋级后的真实业务数据将按赛事方规则另行接入，本仓库不含任何企业数据。

## 5. 测试结果与实验

### 5.1 求解器基准（主线 B15 修正版，`artifacts/benchmarks/corrected-*/`，Windows 11 / Python 3.12）
三种方法共用同一数据、同一独立校验器、同一时间预算。21 条记录全部 100% 服务门店、全部通过独立校验、终止原因均为搜索完成。每条记录保留请求、响应与校验文件。

| 案例（门店 / 箱件） | 简单贪心 | 先路线后装载 | 配载与路线协同 | 协同相对贪心 |
|---|---|---|---|---|
| small-11（10 / 36） | 2 车 912.3 元 | 2 车 869.2 元 | 2 车 869.2 元 | −4.7% |
| small-22 | 2 车 960.8 元 | 2 车 873.4 元 | 2 车 873.4 元 | −9.1% |
| small-33 | 2 车 1,089.3 元 | 2 车 940.2 元 | 2 车 940.2 元 | −13.7% |
| standard-11（30 / 112） | 6 车 2,492.0 元 | 5 车 2,003.2 元 | 5 车 2,003.2 元 | −19.6% |
| standard-22 | 5 车 2,346.8 元 | 5 车 2,176.6 元 | 5 车 2,176.6 元 | −7.3% |
| standard-33 | 5 车 2,040.0 元 | 5 车 1,834.9 元 | 5 车 1,834.9 元 | −10.1% |
| stress-44（60 / 236） | 9 车 3,829.2 元 | 8 车 3,263.9 元 | 8 车 3,263.9 元 | −14.8% |

费用改善率只在「服务门店集合相同且均通过校验」时计算（`scripts/benchmark.py`）。体积利用率：standard 70–77%，stress 92%。单次求解耗时：small 15–50 ms，standard 60–130 ms，stress 200–330 ms（同一机器，含独立校验）。

如实说明两点：
1. 在这批「已知可行」数据上装载从未失败，协同修复一次也没触发，因此「协同」与「先路线后装载」结果相同。协同机制的作用目前由单元测试证明（C10：小车几何不合 → 移到大车后可执行），没有基准数据支撑；要补一组几何冲突案例进入基准才能给出量化结论。
2. 首轮实验（`artifacts/benchmarks/{small,latest,stress}/`）中插入式构造比贪心多用一倍车辆，根因是候选按整车费用而非增量费用比较。两名成员分别独立定位到同一原因（`artifacts/probes/`、`artifacts/evidence/B15-correction.md`），修正后重跑得到上表。首轮记录保留但不再适用于当前代码。

### 5.2 智能体（`artifacts/evidence/A0*.md`，真实 DeepSeek `deepseek-chat`，temperature 0）
| 项目 | 结果 |
|---|---|
| 指令解析准确率（20 条测试集，模型模式） | 20 / 20，中位耗时 1.0 s，最大 1.9 s（`A03_eval.json`） |
| 规则模式（无模型）覆盖 | 测试集中 16 条句式逐条断言通过 |
| 解释数字核对 | 实测 overview 首轮出现 2 个未匹配时刻，重试后 19 个数字全部匹配（`A02_live.json`） |
| 单元测试 | 49 项，FakeLLM 注入，含编造数字拦截、不可比时拦截降本百分比、异常回退 |

### 5.3 端到端
三服务同机，浏览器自动化（修正后的求解器）：small-11 真实求解（2 车 869.2 元）→ 模型解释（核对 23 个数字）→ 指令「V02 今天不出车」→ 字段级 diff「车辆 V02：可用 → 移除」→ 确认重算 → 自动对比：10 → 10 店，2 → 2 车，869.2 → 919.2 元，服务集合相同、费用可比，**上升 5.8%**。少一辆可选车让方案变贵，系统如实报告上升，不做任何美化。截图与日志见 `artifacts/evidence/F05.md`、`F07.md`、`I01.md`。

## 6. 技术架构与外部依赖

| 层 | 技术 | 第三方组件（许可） |
|---|---|---|
| 后端 | Python 3.12，FastAPI 0.143，pydantic 2.14 | FastAPI / Starlette / pydantic / uvicorn（MIT / BSD） |
| 智能体 | Python，FastAPI，openai SDK 3.28（OpenAI 兼容接口，默认 DeepSeek） | openai-python（Apache-2.0），python-dotenv（BSD） |
| 前端 | Vite 8，React 19，TypeScript 6，Three.js 0.186（@react-three/fiber、drei），zod 4 | 均 MIT；Barlow 字体（SIL OFL，@fontsource 自托管） |
| 外部服务 | 仅智能体层可选调用一个 OpenAI 兼容模型接口；求解不依赖任何外部服务 | DeepSeek API（按其服务条款） |

不使用数据库、消息队列、地图服务。任务为内存存储，服务重启即丢（原型约定）。

## 7. 当前限制

- 单仓、单日、每车一趟；箱形货物；固定时间窗；不建模实时路况、多仓、异形物体、材质承重、重心。
- 3D 配载是保守启发式：「未找到布局」不等于数学上不可行；体积利用率不代表空间最优。
- 距离为平面直线，不是道路网络。
- 协同修复在当前基准数据上未被触发（见 5.1）。
- 智能体不做多轮对话；指令白名单之外的修改需要在页面或 JSON 中手工完成。
- 单进程串行求解，队列上限 8；未做并发与持久化。

## 8. 工程化与落地路径

**规模**：求解耗时随门店数近似线性（上表），当前规模远未触及时间预算；瓶颈会首先出现在协同修复的候选枚举。扩展思路：按地理分区并行、候选位置索引、任务队列换为外部队列横向扩展求解进程（接口不变）。

**对接**：输入侧 OMS 订单 → `stores` / `boxes`，TMS 车辆主数据 → `vehicles`；输出侧路线与装载坐标回写 TMS，装卸作业单下发现场 PDA。本仓库只定义 JSON 协议，不含企业系统适配代码。

**模型与数据安全**：智能体只向模型发送事实表与实体摘要（ID、时间窗、尺寸、费用），不含坐标、不含凭据；接口为 OpenAI 兼容协议，可直接指向企业内网私有化部署的模型（传化已有本地化部署的 DeepSeek）；模型不可用时系统降级为模板模式，调度结果的正确性不依赖模型。

**实施路径**：① 历史订单离线回放，用独立校验器与人工方案对照；② 调度员影子试用，系统方案与人工方案并行、只看不用；③ 人工确认后执行，逐步扩大自动化范围。每一步的指标口径与本仓库实验一致（完成率、车辆数、费用、利用率、准时率、卸货阻挡）。

**关键障碍**：真实车厢的门框、轮包、绑扎点等结构；货物的实际可堆叠层数与抗压；门店收货的实际作业时长。这些都是晋级后需要真实数据才能标定的参数。

## 9. 仓库结构

```
backend/      求解器（模型、路线、配载、卸货、修复、校验、任务队列）
agent/        调度助手智能体服务（事实表、解释、指令、对比、模型客户端）
frontend/     调度工作台（Vite + React + Three.js）
scripts/      案例生成、基准实验、手册自检
data/cases/   模拟案例；data/witnesses/ 已知可行见证
tests/        后端测试；agent/tests/ 智能体测试
artifacts/    evidence/ 任务验收证据与截图；benchmarks/ 实验原始记录；probes/ 探针与可选补丁
docs/         architecture.md 架构；demo-script.md 演示脚本；submission-checklist.md 提交清单；
              playbook/ 执行手册（协议、算法、验收、任务卡、变更记录）
```

## 10. 合规说明

- 代码为团队原创；第三方组件见第 6 节，均为宽松开源许可。
- 模拟数据、手工样例、人工环节见第 4 节。
- 模型调用：解释与指令解析可选调用 DeepSeek API；仓库不含任何密钥，`agent/.env` 已被 `.gitignore` 排除。
- 赛题来源：传化 × 动势「AI重构产业·架构师大赛」物流赛道「城市配送智能配载」。
