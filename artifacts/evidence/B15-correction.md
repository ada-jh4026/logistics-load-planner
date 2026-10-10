# B15 复核：增量成本与正式实验留档

日期：2026-10-10。状态：已完成修正与后端回归；I02 的正式审查仍须等待 I01 前置验收。

## 修正

- `backend/routing.py`：greedy 和 sequential 在已有车辆上插入门店时，改用“插入后路线成本－插入前路线成本”；新启用车辆仍使用完整路线成本。这与 `docs/playbook/ALGORITHMS.md` A4/A5 一致。旧实现把已有车辆的完整路线成本当成增量成本，使多开车辆更容易入选。
- `scripts/benchmark.py`：按真实服务门店 ID 集合判断费用是否可比；三个方法对同一输入使用相同数据哈希；记录预算终止原因；单次求解异常保留错误文件并继续其他运行；输出 manifest、CSV，以及每次请求、响应和独立校验文件。
- `tests/test_route_builders.py`、`tests/test_benchmark.py`：新增增量成本选择和求解异常留档测试，调整门店集合测试。

## 实际验证

```
.\.venv\Scripts\python.exe -m pytest -q tests
    165 passed in 2.42s，退出码 0（沙箱外；沙箱内 API 测试挂起）

.\.venv\Scripts\python.exe -m scripts.benchmark --suite small --output artifacts/benchmarks/corrected-small
    runs=9 comparisons=6，退出码 0
.\.venv\Scripts\python.exe -m scripts.benchmark --suite standard --output artifacts/benchmarks/corrected-standard
    runs=9 comparisons=6，退出码 0
.\.venv\Scripts\python.exe -m scripts.benchmark --suite stress --output artifacts/benchmarks/corrected-stress
    runs=3 comparisons=2，退出码 0
```

## 修正后结果

金额为各 seed 的求解成本之和，车辆数为各 seed 用车数之和；这些是模拟案例结果，不代表企业实际节约。

| 套件 | greedy（成本/车辆） | sequential（成本/车辆） | coupled（成本/车辆） |
| --- | ---: | ---: | ---: |
| small，3 seed | ¥2962.39 / 6 | ¥2682.75 / 6 | ¥2682.75 / 6 |
| standard，3 seed | ¥6878.80 / 16 | ¥6014.65 / 15 | ¥6014.65 / 15 |
| stress，1 seed | ¥3829.25 / 9 | ¥3263.89 / 8 | ¥3263.89 / 8 |

21 次运行均独立校验通过、终止原因为 completed、服务所有门店。coupled 相对 greedy 的逐案例成本改善率为 4.73%–19.61%；相对 sequential 均为 0%。这些数据没有触发协同修复，因此不能据此声称协同修复带来了降本。

原始记录在 `artifacts/benchmarks/corrected-{small,standard,stress}/`。每个套件含 `manifest.json`、`runs.csv`、`runs.json`、`summary.json`，每次运行含 `request.json`、`response.json`、`validation.json`。首次实验保留在原目录，但因成本选择实现错误已不适用于当前代码。正式的 I02 报告仍待 I01 完成后编制。
