"""B15: 可复现实验与对比汇总。

从落盘数据（data/cases）按三种 method 运行，保存原始输入输出、独立验证、
数据哈希、环境信息；计算费用改善率时做可比性保护（服务门店集合相同、均有效、
基线成本>0），不可比输出 null 及原因。拒绝 mock 数据。

用法：
    python scripts/benchmark.py --suite standard --output artifacts/benchmarks/latest
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import sys
import time
import traceback
from pathlib import Path

from backend.budget import Budget
from backend.models import SolveRequest
from backend.solver import solve
from backend.validation import validate_solution

METHODS = ["greedy", "sequential", "coupled"]

# EVALUATION.md：小/标准各 3 seed，压力 1 seed
SUITE_SEEDS = {
    "small": [11, 22, 33],
    "standard": [11, 22, 33],
    "stress": [44],
}


def _data_hash(request: SolveRequest) -> str:
    payload = json.dumps(request.model_dump(), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _env_info() -> dict:
    dependencies = {}
    for name in ("fastapi", "pydantic"):
        try:
            dependencies[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "dependencies": dependencies,
    }


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_one(request: SolveRequest, method: str, run_dir: Path) -> dict:
    req = request.model_copy(deep=True)
    req.options.method = method
    _write_json(run_dir / "request.json", req.model_dump())
    budget = Budget(req.options.time_limit_ms, req.options.max_iterations)
    start = time.monotonic()
    record = {
        "case_id": req.case_id,
        "method": method,
        "data_hash": _data_hash(request),
        "valid": False,
        "violations": [],
        "served_store_ids": [],
        "metrics": None,
    }
    try:
        result = solve(req, budget)
        violations = validate_solution(req, result)
        record["valid"] = not violations
        record["violations"] = [v.code for v in violations]
        record["served_store_ids"] = sorted(sid for route in result.routes for sid in route.store_ids)
        record["metrics"] = result.metrics.model_dump()
        _write_json(run_dir / "response.json", result.model_dump())
        _write_json(run_dir / "validation.json", {
            "valid": not violations,
            "violations": [v.model_dump() for v in violations],
        })
    except Exception as exc:
        record["violations"] = ["SOLVER_EXCEPTION"]
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        _write_json(run_dir / "error.json", {
            **record["error"], "traceback": traceback.format_exc(),
        })
    record["elapsed_ms"] = (time.monotonic() - start) * 1000.0
    record["termination_reason"] = (
        "exception" if "error" in record else budget.termination_reason()
    )
    return record


def cost_improvement(baseline: dict, candidate: dict):
    """费用改善率 (基线-本方案)/基线；不可比时返回 (None, reason)。"""
    if baseline["valid"] is not True or candidate["valid"] is not True:
        return None, "方案未通过独立验证"
    b_ids = baseline.get("served_store_ids")
    c_ids = candidate.get("served_store_ids")
    if b_ids is None or c_ids is None:
        return None, "缺少服务门店集合"
    if set(b_ids) != set(c_ids):
        return None, "服务门店集合不同"
    b = baseline["metrics"]
    c = candidate["metrics"]
    if b["total_cost"] <= 0:
        return None, "基线成本为 0"
    return (b["total_cost"] - c["total_cost"]) / b["total_cost"], None


def run_benchmark(suite: str, output_dir: Path) -> dict:
    """运行一个 suite 的基准，返回汇总 dict。"""
    seeds = SUITE_SEEDS[suite]
    runs: list[dict] = []

    output_dir.mkdir(parents=True, exist_ok=True)
    for seed in seeds:
        case_path = Path(f"data/cases/{suite}-{seed}.json")
        data = json.loads(case_path.read_text(encoding="utf-8"))
        if data.get("is_mock") is True:
            raise ValueError(f"拒绝 mock 数据：{case_path}")
        request = SolveRequest.model_validate(data)

        for method in METHODS:
            run = _run_one(request, method,
                           output_dir / "runs" / f"{suite}-{seed}" / method)
            runs.append(run)
            _write_json(output_dir / "runs.json", runs)

    # 按 case 分组计算对比
    summary = _summarize(runs)

    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "manifest.json", {
        "suite": suite, "seeds": seeds, "methods": METHODS,
        "environment": _env_info(), "total_runs": len(runs),
    })
    with (output_dir / "runs.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        fields = ["case_id", "method", "data_hash", "valid", "elapsed_ms",
                  "termination_reason", "served_stores", "total_cost", "used_vehicles"]
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for run in runs:
            metrics = run["metrics"] or {}
            writer.writerow({key: run.get(key, metrics.get(key)) for key in fields})

    return summary


def _summarize(runs: list[dict]) -> dict:
    """按 case 汇总，计算 greedy/sequential 相对 coupled 的改善率。"""
    by_case: dict[str, dict[str, dict]] = {}
    for run in runs:
        by_case.setdefault(run["case_id"], {})[run["method"]] = run

    comparisons = []
    for case_id, methods in sorted(by_case.items()):
        for baseline_name in ("greedy", "sequential"):
            if baseline_name not in methods or "coupled" not in methods:
                continue
            imp, reason = cost_improvement(methods[baseline_name],
                                           methods["coupled"])
            comparisons.append({
                "case_id": case_id,
                "baseline": baseline_name,
                "candidate": "coupled",
                "improvement": imp,
                "reason": reason,
            })

    return {
        "env": _env_info(),
        "total_runs": len(runs),
        "comparisons": comparisons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="运行配载对比基准")
    parser.add_argument("--suite", choices=["small", "standard", "stress"],
                        default="standard")
    parser.add_argument("--output", type=str,
                        default="artifacts/benchmarks/latest")
    args = parser.parse_args()

    summary = run_benchmark(args.suite, Path(args.output))
    print(f"runs={summary['total_runs']} "
          f"comparisons={len(summary['comparisons'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
