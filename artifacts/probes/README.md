# 探针：路线构造的费用比较口径

日期：2026-10-10（英国时间 19:10）。提出方：前端/智能体线。本目录不改 `backend/`，只放可复现的探针脚本与一份可选补丁，由主线决定是否采纳。

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
