# 异构箱件配载与失败路线恢复：结果

日期：2026-10-10。执行者：主线（Codex）。本文件是实际运行后的结果，不是计划。

## 1. 要解决的问题

此前的基准与冲突案例中，箱件几乎都是同规格立方体（500³ 或 600³）。换成连锁药店真实形态的**混合纸箱**（长条、大件、小盒混在一起）后，三种方法在多门店路线上几乎全部装载失败。修复前 `coupled` 在 small 只能部分服务、在 standard/stress 直接 0 门店（`budget_exhausted`）。评委若按 README 的邀请导入一份真实尺寸 JSON，会直接看到「全军覆没」。

根因在 `backend/packing.py`：

1. 候选位置排序固定为「低重心、靠车头」，与到站顺序无关，早送门店的箱子被塞到车头、被后送箱子堵住；
2. 卸货可行性只在整车放完后事后校验，失败只换三种排序重试，三次撞同一堵墙；
3. 承托要求「单个箱完整托住」，混合尺寸时堆叠被卡死，地板一满就失败。

## 2. 修复方案（H01）

同步 `ALGORITHMS.md` A6/A7，改动集中在 `backend/packing.py`、`backend/solver.py`、`backend/budget.py`：

- **逆站序分区配载**：存在多种长宽高时，先按逆站序尝试三种可装入构造（按站纵向分区 / 共享空间 + 底面积排序 / 共享空间 + 体积排序）；分区模式每完成一站，把下一站可用车长收至该站最小 x；共享模式允许符合既有单箱承托规则的跨站叠放。
- **异构候选**：候选坐标额外包含已放箱左/右边对齐的 x/y 位置，补足不同底面尺寸的承托机会；惰性生成，最多 2000 个；每次放置额外检查沿车门进入的扫掠路径。
- **逐店恢复**：剩余预算用于失败路线的逐店恢复——保留已验证路线，未配送门店按最早截止时间处理，优先费用增量最低的已用车与空车，仅重配目标车，接受前全量独立校验且服务门店数必须 +1。
- **约束不变**：独立 geometry/unloading/validation 规则未放宽，仍不允许跨箱共同承托；失败不声明物理不可行；接口无新增字段。

## 3. 案例设计

| 组 | 案例 | 用途 |
|---|---|---|
| 固定正向控制 | `hetero-floor-2`、`hetero-floor-3`、`hetero-long-2`（3 案） | 已知可行的异构多站案例，验证改动不破坏已有能力 |
| 开发回归案 | `hetero-dev-6`（1 案，seed 6） | 由失败挑出的最小复现：修复前四法 0/3 |
| 混合箱件正式集 | `small/standard/stress` × mixed-1/mixed-2（6 案） | 修复前后对比 |
| 留出集 | `small-22`/`standard-22`/`stress-44` × mixed-11/22（6 案） | 未参与调试的种子，验证泛化 |

全部为合成输入，非药店真实订单。原始 request/response/validation 与 data_hash 落盘在对应 `artifacts/benchmarks/hetero-*/`。

## 4. 结果

### 4.1 固定正向控制（修复不得破坏已有能力）

| 案例 | 四法覆盖 | coupled repair_status |
|---|---|---|
| hetero-floor-2 | 2/2 全服务 | not_needed |
| hetero-floor-3 | 3/3 全服务 | not_needed |
| hetero-long-2 | 2/2 全服务 | not_needed |

3 案 × 4 法 = 12 次全部有效、全服务；coupled 在无需修复案例正确返回 `not_needed`。

### 4.2 开发回归案（hetero-dev-6）

| | 修复前 | 修复后 |
|---|---|---|
| greedy / sequential / coupled | 0/3 | 3/3 |
| sequential_reinsert | 2/3 | 3/3 |

### 4.3 混合箱件正式集（6 案，服务门店数 / 总数）

**修复前（`hetero-mixed-before-20261010`）**：

| 案例 | greedy | sequential | sequential_reinsert | coupled |
|---|---|---|---|---|
| small-11-mixed-1 | 0/10 | 0/10 | 10/10 | 8/10（partially_repaired） |
| small-11-mixed-2 | 0/10 | 0/10 | 10/10 | 7/10（partially_repaired） |
| standard-11-mixed-1 | 0/30 | 0/30 | 30/30 | **0/30（budget_exhausted）** |
| standard-11-mixed-2 | 0/30 | 0/30 | 30/30 | **0/30（budget_exhausted）** |
| stress-44-mixed-1 | 0/60 | 0/60 | 50/60 | **0/60（budget_exhausted）** |
| stress-44-mixed-2 | 0/60 | 0/60 | 53/60 | **0/60（budget_exhausted）** |

**修复后（`hetero-mixed-after-20261010`）**：

| 案例 | coupled 覆盖 | coupled 费用 | sequential_reinsert 覆盖 | 费用 |
|---|---|---|---|---|
| small-11-mixed-1 | **10/10（repaired）** | 1334 元 | 10/10 | 1334 元 |
| small-11-mixed-2 | **10/10（repaired）** | 1255 元 | 10/10 | 1255 元 |
| standard-11-mixed-1 | **30/30（repaired）** | 3282 元 | 30/30 | 2987 元 |
| standard-11-mixed-2 | **30/30（repaired）** | 3014 元 | 29/30 | 2804 元 |
| stress-44-mixed-1 | **60/60（repaired）** | 6895 元 | 32/60 | 2976 元 |
| stress-44-mixed-2 | **60/60（repaired）** | 6758 元 | 36/60 | 3208 元 |

### 4.4 留出集（未参与调试，`hetero-holdout-20261010`）

| 案例 | coupled 覆盖 | repair_status |
|---|---|---|
| small-22-mixed-11 | 10/10 | repaired |
| small-22-mixed-22 | 10/10 | repaired |
| standard-22-mixed-11 | 30/30 | repaired |
| standard-22-mixed-22 | 30/30 | repaired |
| stress-44-mixed-11 | 60/60 | repaired |
| stress-44-mixed-22 | 60/60 | repaired |

留出集全部 100% 覆盖且 `repaired`，说明修复不是对开发种子的过拟合。

## 5. 结论

1. **崩溃已修复**：混合箱件下 `coupled` 从 standard/stress 的 0 门店恢复到全规模 100% 覆盖，且协同修复真正触发（`repair_status=repaired`、`repair_attempted`/`repair_accepted` 非零）。
2. **覆盖率是主要收益**：`coupled` 在 stress 达到 60/60，而 `sequential_reinsert` 在 stress 只有 32–36/60（预算耗尽）；`greedy`/`sequential` 在多数混合案例 0 服务。协同修复的「从不可执行到可执行」价值首次有了数据支撑。
3. **费用不是收益，且要如实说明**：在服务门店集合相同的案例上，`coupled` 与 `sequential_reinsert` 费用打平（small）或更高（standard，约 +9%）。`coupled` 用更多车辆换全覆盖，符合「先最大化服务门店数、再最小化费用」的目标序，但**不能声称协同修复带来降本**。stress 上两者服务集合不同，费用不可直接比较，应先报告覆盖变化。

## 6. 边界

- 仍不允许跨箱共同承托（单箱完整承托未放宽）；搜索不完备，失败只表示未找到。
- 混合箱件案例为合成输入，非药店真实订单；真实 SKU 外箱尺寸仍需用户补充。
- 修复后 `coupled` 在 stress 用 19–22 辆车（体积利用率约 20%），说明该规模下仍偏保守，有进一步优化空间，但不影响可执行性。
- 数据与代码版本：基准提交 `1c5054e`，H01 实现为工作区修改（后端 `packing.py`/`solver.py`/`budget.py` 及配套脚本、测试、文档）。
