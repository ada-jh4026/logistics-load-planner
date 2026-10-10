# 异构箱件修复前验收基线

日期：2026-10-10。后端基线提交 `1c5054e`；本记录生成时只新增案例、脚本和原始输出，未修改 `backend/`、`agent/`、`frontend/`。案例均为合成输入，不是药店真实订单。

## 固定正向控制

运行 `.venv\\Scripts\\python.exe -m scripts.generate_hetero_cases`，退出 0，生成 3 个已知可行的异构箱件多站案例：`hetero-floor-2`、`hetero-floor-3`、`hetero-long-2`。每个 `.meta.json` 保存车厢坐标和逐站卸货步骤；生成时通过 `validate_vehicle_candidate` 独立验证。这些案例事先固定，不按 coupled 结果筛选。

运行 `.venv\\Scripts\\python.exe -m scripts.hetero_benchmark --output artifacts/benchmarks/hetero-before-20261010`，退出 0，3 案 × 4 法 = 12 次有效，全部全服务。原始 request/response/validation 和汇总在该目录。随后 `.venv\\Scripts\\python.exe -m scripts.audit_conflict_benchmark --input artifacts/benchmarks/hetero-before-20261010` 退出 0，输出 `runs=12 validated=12 accepted_events=0`。它们用于检查未来改动不得破坏已有可行异构布局，不证明目前的混合箱件问题已解决。

## 开发失败回归案

运行 `.venv\\Scripts\\python.exe -X utf8 -m scripts.find_hetero_witness`，退出 0。在固定的 seed 0..199 搜索序列中首次发现 seed 6：`data/hetero_cases/hetero-development.json`。该案只有一辆车，三店按时间窗限定为 S01→S02→S03。对应 `hetero-development.meta.json` 有经独立验证的 3 店 × 4 箱全配送布局；当前 `pack_route` 对同一车辆和门店顺序返回 `SEARCH_EXHAUSTED`，原因 `UNLOAD_BLOCKED`。这是**根据失败挑出的开发回归案**，不能列入盲测或泛化收益统计。

运行 `.venv\\Scripts\\python.exe -m scripts.hetero_benchmark --development --output artifacts/benchmarks/hetero-development-before-20261010`，退出 0；四法均为 0/3 店，但返回方案均独立有效。随后 `audit_conflict_benchmark` 复审 4/4 通过。这里的 0/3 是启发式没有找到已知可行布局，不是数学上无解。未来修复应让该案成功且保留同规格基准与固定正向控制；独立校验器不能放宽来制造通过。

## 协作边界

Claude 可在 `artifacts/probes/` 提交分区式补丁与回归测试草案；主线负责合入 `backend/`、校验器同步和重跑固定案例。当前 README 仍由 Claude 更新。协议 `repair_trace` 的严格模型兼容需 Claude 在 `agent/`、`frontend/` 优先修复。

新增的 `tests/test_hetero_cases.py` 已实跑，`1 passed`：逐案复核固定正向控制与开发回归案的独立可行见证。
