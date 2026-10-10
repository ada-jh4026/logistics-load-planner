"""探针：独立校验器对「篡改型」结果的漏检（GPT 只读审查 B1 / B2，2026-10-10）。

用法（仓库根目录，只读，不写 artifacts/）：
    .venv/Scripts/python.exe -X utf8 artifacts/probes/validator_tamper_probe.py

每一行应当打印 LEAK（当前漏检）或 CAUGHT（已被校验器发现）。修好后全部应为 CAUGHT。
建议把本文件的 TAMPERS 逐条搬进 tests/test_validation.py 作为回归。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.models import Result, SolveRequest  # noqa: E402
from backend.solver import solve  # noqa: E402
from backend.validation import validate_solution  # noqa: E402


def _base() -> tuple[SolveRequest, dict]:
    req = SolveRequest(**json.loads((ROOT / "data/cases/c01.json").read_text(encoding="utf-8")))
    res = solve(req)
    result = res.result if hasattr(res, "result") else res
    d = result.model_dump() if hasattr(result, "model_dump") else result
    assert d["routes"], "c01 应至少产生一条路线"
    assert not validate_solution(req, Result(**d)), "基线必须先通过校验"
    return req, d


def t_drop_placements(d):
    d["routes"][0]["placements"] = []
    return "B1a 首车 placements 清空（box_ids 保留）"


def t_drop_unload_steps(d):
    d["routes"][0]["unload_steps"] = []
    return "B1b 首车 unload_steps 清空"


def t_drop_both(d):
    d["routes"][0]["placements"] = []
    d["routes"][0]["unload_steps"] = []
    return "B1c placements 与 unload_steps 同时清空"


def t_duplicate_placement(d):
    r = d["routes"][0]
    if len(r["placements"]) >= 2:
        r["placements"][1] = copy.deepcopy(r["placements"][0])
    return "B1d 同一箱件出现两个 placement，另一箱件无位置"


def t_zero_distance_and_cost(d):
    r = d["routes"][0]
    v = r["vehicle_id"]
    d["metrics"]["total_distance_km"] -= r["distance_km"]
    d["metrics"]["total_cost"] -= r["cost"]
    r["distance_km"] = 0.0
    r["cost"] = 100.0  # 只剩固定费
    d["metrics"]["total_cost"] += 100.0
    return f"B2a 路线 {v} 里程改 0、费用改 100，总指标同步改"


def t_zero_route_cost_only(d):
    d["routes"][0]["cost"] = 0.0
    return "B2b 只把 route.cost 改 0（总指标不动）"


def t_zero_timestamps(d):
    r = d["routes"][0]
    for s in r["stops"]:
        s["arrival_min"] = 0.0
        s["service_start_min"] = 0.0
        s["departure_min"] = 0.0
    r["return_min"] = 0.0
    return "B2c 所有到站/开始/离店/回仓时刻改 0"


def t_shuffle_stop_order_fields(d):
    r = d["routes"][0]
    if len(r["stops"]) >= 2:
        r["stops"][0], r["stops"][1] = r["stops"][1], r["stops"][0]
    return "B2d stops 顺序与 store_ids 顺序不一致"


TAMPERS = [t_drop_placements, t_drop_unload_steps, t_drop_both, t_duplicate_placement,
           t_zero_distance_and_cost, t_zero_route_cost_only, t_zero_timestamps, t_shuffle_stop_order_fields]


def main() -> int:
    req, base = _base()
    leaks = 0
    for fn in TAMPERS:
        d = copy.deepcopy(base)
        label = fn(d)
        try:
            result = Result(**d)
        except Exception as e:  # 协议层就拒绝也算 CAUGHT
            print(f"CAUGHT  {label}  (协议校验拒绝: {type(e).__name__})")
            continue
        v = validate_solution(req, result)
        if v:
            print(f"CAUGHT  {label}  -> {sorted({x.code for x in v})}")
        else:
            leaks += 1
            print(f"LEAK    {label}  -> violations=[]")
    print(f"\n{leaks} / {len(TAMPERS)} 条篡改未被独立校验器发现")
    return 1 if leaks else 0


if __name__ == "__main__":
    sys.exit(main())
