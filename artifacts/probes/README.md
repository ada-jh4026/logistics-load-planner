# 探针：路线构造的费用比较口径

> **结果：主线已在提交 31e9a54 独立做出同一修正**（`backend/routing.py` 改为增量费用），并重跑三套基准到 `artifacts/benchmarks/corrected-{small,standard,stress}/`，见 `artifacts/evidence/B15-correction.md`。本目录的补丁因此不再需要应用，保留作为问题定位与交叉验证的记录。

日期：2026-10-10（英国时间 19:10）。提出方：前端/智能体线。本目录不改 `backend/`，只放可复现的探针脚本与一份可选补丁。

## 现象（来自主线 B15 的正式实验，`artifacts/benchmarks/`）
| 案例 | greedy | sequential | coupled |
|---|---|---|---|
| standard-11（30 店 112 箱） | 6 车 2,227.8 元 | 12 车 4,287.4 元 | 12 车 4,287.4 元 |
| stress-44（60 店 236 箱） | 13 车 4,620.2 元 | 24 车 8,270.5 元 | 24 车 8,270.5 元 |

两点问题：
1. `sequential` / `coupled` 比简单贪心贵近一倍、启用车辆翻倍，体积利用率只有 22%。
2. `coupled` 与 `sequential` 在全部 21 条记录上完全相同（`diagnostics` 为空）：数据是「已知可行」构造，装载从不失败，协同修复从未触发。README 里「配载与路线协同」的主张目前没有数据支撑。

## 根因（`backend/routing.py`）
`build_insertion_routes` 对每辆车（含未用车）枚举插入位时，用 `_candidate_cost(cand)` 即候选整车费用做比较。已有车的候选费用包含它此前累积的里程，新开一辆车的候选只有固定费 + 单程里程，于是几乎总是新开车更"便宜"，直到车用完。`build_greedy_routes` 同样用整车费用比较尾插与新开车，问题稍轻（尾插不枚举位置）。

正确口径是**增量费用**：插入已有车 = 新整车费用 − 原整车费用；新开车 = 整车费用（原费用为 0）。这正是 ALGORITHMS A4/A5 写的「选增量成本最低者」。

## 验证（`routing_marginal_cost_probe.py`，在完整管线上：路线 → 3D 配载 → 卸货校验 → 独立校验 → coupled 修复）
```
.venv\Scripts\python.exe artifacts/probes/routing_marginal_cost_probe.py
```
| 案例 | 现状 sequential | 改为增量后 sequential | 改为增量后 greedy |
|---|---|---|---|
| small-11 | 4 车 1,577.1 元 | 2 车 869.2 元（体积利用率 56%） | 2 车 912.3 元 |
| standard-11 | 12 车 4,287.4 元 | 5 车 2,003.2 元（70%） | 6 车 2,492.0 元 |
| standard-22 | 12 车 4,553.5 元 | 5 车 2,176.6 元（70%） | 5 车 2,346.8 元 |
| standard-33 | 12 车 4,216.2 元 | 5 车 1,834.9 元（77%） | 5 车 2,040.0 元 |
| stress-44 | 24 车 8,270.5 元 | 8 车 3,263.9 元（92%） | 9 车 3,829.2 元 |

全部仍通过独立校验，耗时仍在 120 ms 内。改后 `sequential` 在所有案例上优于 `greedy`，与设计意图一致。

## 补丁
`routing_marginal_cost.patch`（37 行，只改 `backend/routing.py` 两处比较）。在仓库根目录：
```
git apply artifacts/probes/routing_marginal_cost.patch
.venv\Scripts\python.exe -m pytest -q tests
.venv\Scripts\python.exe -m scripts.benchmark --suite small    --output artifacts/benchmarks/small
.venv\Scripts\python.exe -m scripts.benchmark --suite standard --output artifacts/benchmarks/latest
.venv\Scripts\python.exe -m scripts.benchmark --suite stress   --output artifacts/benchmarks/stress
```
在后端副本上已验证：162 项测试全部通过（见本目录提交说明）。

## 仍未解决：协同修复没有触发案例
增量口径让车装得更满，装载失败的概率上升，但现有 7 个基准案例仍全部一次装下。建议主线补一组「几何冲突」案例进入基准（EVALUATION 允许扩展）：
- 箱件总体积 ≤ 车厢但单件尺寸组合装不下（如 2 个 1500×1000 箱进 2000×1000 车厢）；
- 后送门店的大箱必须靠车头、先送门店的箱件被挡（C05 型）；
- 两种车型混合，小车预筛通过但几何不合（C10 型）。
这样 `coupled` 相对 `sequential` 的「从不可执行到可执行」才有 21 条之外的实验证据；README 会按真实结果写，没有就写没有。

---

# 探针 2：异构箱件下的配载崩溃（2026-10-10 晚，前端/智能体线）

> **结果：主线已在提交 0081f4d（H01）实现分区式配载 + 逐店恢复**，见 `artifacts/evidence/H01.md` 与 `docs/heterogeneous-results.md`。本方在 H01 上重跑 `hetero_cartons_probe.py`：coupled 在 small/standard/stress 的 10 个混合种子上全部 100% 服务（greedy/sequential 仍大多失败），代价是车辆数偏多、体积利用率约 20–27%。原定由本方交付的补丁不再需要；下文保留为问题记录。

> **发现时的判断：这是目前最大的技术风险。** 基准与冲突案例的箱件几乎都是同规格立方体（500³ 或 600³）。换成连锁药店真实形态的混合纸箱后，三种方法在多门店路线上几乎全部装载失败，**0/10、0/30 门店**。评委若按 README 的邀请导入一份自己的 JSON，大概率看到这个结果。

## 复现
```
.venv\Scripts\python.exe artifacts/probes/hetero_cartons_probe.py     # 把基准案例的箱件换成 8 种混合纸箱（含少量长条/大件），跑三法
.venv\Scripts\python.exe artifacts/probes/pack_multistop_diag.py      # 定位：同一批箱件「单店」能装、「多店」就失败
.venv\Scripts\python.exe artifacts/probes/pack_unload_aware_probe.py  # 一个构造式修法的探针（见下）
```

## 现象（coupled，服务门店数/总数）
| 箱件混合程度 | small-11 三个种子 | standard-11 三个种子 |
|---|---|---|
| A 两种小立方（400³ / 500³） | 10/10，10/10，**0/10** | 0/30，0/30，0/30 |
| B 四种小纸箱（≤600 mm） | 0/10，10/10，5/10 | 0/30，0/30，0/30 |
| C 小纸箱 + 长条（800/1200 mm） | 5/10，5/10，10/10 | 0/30，0/30，0/30 |
| D 全部（含 900×600×500、1100×600×1000 大件） | 0/10，5/10，5/10 | 0/30，0/30，0/30 |

同一批混合箱件：**单店单车 20 箱全部能装**（`pack_multistop_diag.py`：6/6 种子成功，占地率超过 2 仍能靠堆叠放下）；改成 3 店 × 4 箱就开始失败，4 店 × 4 箱几乎全失败。失败原因两类：「箱 X 在当前排序下未找到可行位置」与「卸货序列生成失败：UNLOAD_BLOCKED」。

## 根因（`backend/packing.py`）
1. 候选位置排序固定为 `(z 低, x 大=靠车头, y 小)`，**与到站顺序无关**：早送门店的箱子也被塞到车头，被后送门店的箱子堵在后面；或者被放到后送箱子上面当承托（卸货时不能先抽底箱）。
2. 卸货可行性只在整车放完后事后校验；失败后只换三种排序重试，排序之间差别很小，三次都撞同一堵墙。
3. 承托要求「单个箱完整托住」：混合尺寸时一个 400×300 的箱子几乎永远托不住 600×400 的箱子，堆叠层数被卡死，地板一满就失败。

同规格立方体恰好绕开了这三点：所有箱同高同底、任何箱都能完整托住任何箱、同站箱件天然成列，所以基准全过。

## 探针修法（`pack_unload_aware_probe.py`，未改 backend/）
运行时替换候选排序与可放检查：放置时就拒绝会被「更晚到站」箱件挡住抽出路径的位置；非末站箱优先靠后门、末站箱靠车头；承托允许多个同高非易碎箱共同完整覆盖。结果：small-11 两个混合种子从 0/10 变 10/10（coupled），standard 仍大多失败，且同规格 standard-11 退化到 10/30。**说明局部修补不够**，需要把「按到站顺序分区」做成配载的一等约束：
- 沿 x 把车厢按到站逆序划成若干段（末站靠车头），每站箱件只在自己的段内做层式填充（wall-building），段长由该站箱件体积与占地估算、允许相邻段借用剩余空间；
- 段内允许多箱共同承托（并集完整覆盖）；
- 卸货校验保持事后独立进行，不放松。
这样「先送靠门、后送靠里」变成结构保证而不是事后碰运气，卸货阻挡只可能发生在段边界，修复循环也就有了真正会触发的来源。

## 为什么值得现在做
- 维度 1「实现可信度」：评委用真实尺寸试一次就能发现；比 O03 的择优搬移影响大得多。
- 维度 2「技术创新」：有了会自然失败的装载，协同修复才有机会与 reinsert 拉开差距（也可能拉不开，那也是真实结论）。
- 维度 3「业务契合」：药店配送的 SKU 外箱本来就不是立方体。

建议主线把混合纸箱案例（本探针的 8 种规格或更贴近药店的规格表）作为第二组基准，与同规格基准分表汇报。本方可按上面的分区方案写成完整探针 + 补丁 + 回归测试交主线合入，或由主线直接实现；需要用户拍板归属。

---

# 探针 3：独立校验器对篡改型结果的漏检（2026-10-10 晚，前端/智能体线转交，来源：GPT 只读审查 B1/B2）

> **状态：2026-10-11 已修复（本地待提交），8/8有效篡改 CAUGHT。** 原B2d在c01单站上没有实际交换，现改为small-11多站并增加修改断言。详见 `artifacts/evidence/H02.md`。下表保留历史记录。 归属 `backend/validation.py`、`backend/metrics.py`、`tests/`。本方不改 backend，只交付可复现脚本。

## 复现
```
.venv/Scripts/python.exe -X utf8 artifacts/probes/validator_tamper_probe.py
```
从 `data/cases/c01.json` 的真实求解结果出发，逐条篡改后调用 `validate_solution`。当前输出（提交 d9b7ebc）：

| 篡改 | 结果 |
|---|---|
| 首车 `placements` 清空（`box_ids` 保留） | CAUGHT（BOX_MISSING） |
| 首车 `unload_steps` 清空 | CAUGHT（BOX_MISSING） |
| **`placements` 与 `unload_steps` 同时清空** | **LEAK** |
| 同一箱件两个 placement、另一箱无位置 | CAUGHT（BOX_MISSING、OVERLAP） |
| **路线里程改 0、费用改 100，总指标同步改** | **LEAK** |
| **只把 `route.cost` 改 0** | **LEAK** |
| **所有到站 / 开始 / 离店 / 回仓时刻改 0** | **LEAK** |
| **`stops` 顺序与 `store_ids` 顺序不一致** | **LEAK** |

5 / 8 条未被发现。前 4 条说明 `box_ids`、`placements`、`unload_steps` 三者之间缺少「集合完全相等」的交叉检查（只有当 placements 非空时 `validate_unload_steps` 才会比对）；后 4 条说明 `compute_metrics` 直接汇总响应里的 `route.distance_km` 与时刻，没有从坐标、车速、费率重算后逐字段比较。

## 建议修法（一句话）
1. 每条路线：`set(box_ids) == {p.box_id} == {s.box_id for s in unload_steps}`，且三者无重复；缺一项即 `STEP_MISMATCH` / `BOX_MISSING`。
2. 每条路线：用 `schedule_route` 的重排结果逐站比较 `arrival / service_start / departure / return_min`，用坐标重算 `distance_km`，用车辆费率重算 `cost`；任一超出 EPS 即 `METRIC_MISMATCH`，并把总指标改为由重算值汇总后比较。
3. `stops[i].store_id` 必须与 `store_ids[i]` 顺序一致。
4. 把本脚本的 8 条篡改搬进 `tests/test_validation.py`。

## 边界
这是校验器的漏检，不是现有实验造假的证据：GPT 审查对 `artifacts/benchmarks/` 下 205 份结果 534 条路线做了独立重算，未发现不一致。修复后 README「独立校验器重算全部约束和指标」的说法才成立。
