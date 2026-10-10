"""O03 fixed-case ablation: legacy first, ranked best, simple reinsertion."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from backend.budget import Budget
from backend.models import SolveRequest
from backend.solver import MAX_RELOCATION_CANDIDATES, solve_coupled
from backend.validation import validate_solution
from scripts.benchmark import _data_hash, _env_info, cost_improvement
from scripts.conflict_benchmark import ROOT, _check_certificate, _write
from scripts.sequential_reinsert import solve_sequential_reinsert

VARIANTS = ("first", "best", "sequential_reinsert")


def run(output: Path) -> dict:
    manifest = json.loads((ROOT / "data/conflict_cases/manifest.json").read_text(encoding="utf-8"))
    entries = list(manifest["cases"])
    entries.append({"case_id": "ranked-geometry-22",
                    "path": "data/conflict_cases/ranked-geometry-22.json",
                    "category": "development_regression"})
    records = []
    for entry in entries:
        path = ROOT / entry["path"]
        raw = json.loads(path.read_text(encoding="utf-8"))
        request = SolveRequest.model_validate(raw)
        if request.case_id != entry["case_id"] or raw.get("is_mock") is True:
            raise ValueError(f"invalid case: {path}")
        meta = path.with_suffix(".meta.json")
        if meta.exists():
            _check_certificate(request, json.loads(meta.read_text(encoding="utf-8")))
        case_hash = _data_hash(request)
        for variant in VARIANTS:
            current = request.model_copy(deep=True)
            current.options.method = ("sequential" if variant == "sequential_reinsert"
                                      else "coupled")
            directory = output / "runs" / request.case_id / variant
            _write(directory / "request.json", current.model_dump())
            budget = Budget(current.options.time_limit_ms, current.options.max_iterations)
            start = time.monotonic()
            if variant == "sequential_reinsert":
                result = solve_sequential_reinsert(current, budget)
            else:
                result = solve_coupled(current, budget, selection=variant)
            elapsed = (time.monotonic() - start) * 1000
            violations = validate_solution(current, result)
            record = {
                "case_id": request.case_id, "category": entry["category"],
                "variant": variant, "data_hash": case_hash,
                "valid": not violations,
                "served_store_ids": sorted(s for r in result.routes for s in r.store_ids),
                "metrics": result.metrics.model_dump(),
                "violations": [v.code for v in violations],
                "repair_attempted": (result.repair_trace.attempted_count
                                     if result.repair_trace else None),
                "repair_accepted": (result.repair_trace.accepted_count
                                    if result.repair_trace else None),
                "elapsed_ms": elapsed,
                "termination_reason": budget.termination_reason(),
            }
            _write(directory / "response.json", result.model_dump())
            _write(directory / "validation.json", {
                "valid": not violations,
                "violations": [v.model_dump() for v in violations],
            })
            records.append(record)
            _write(output / "runs.json", records)
    by_case = {(r["case_id"], r["variant"]): r for r in records}
    comparisons = []
    for entry in entries:
        cid = entry["case_id"]
        for baseline in ("first", "sequential_reinsert"):
            improvement, reason = cost_improvement(by_case[(cid, baseline)],
                                                    by_case[(cid, "best")])
            comparisons.append({"case_id": cid, "category": entry["category"],
                                "baseline": baseline, "candidate": "best",
                                "cost_improvement": improvement, "reason": reason})
    files = ("backend/solver.py", "scripts/sequential_reinsert.py",
             "scripts/o03_benchmark.py")
    _write(output / "manifest.json", {
        "experiment": "O03 ranked relocation ablation",
        "cases": entries, "variants": list(VARIANTS),
        "candidate_cap": MAX_RELOCATION_CANDIDATES,
        "budget": "same per-request time_limit_ms/max_iterations; independent per run",
        "development_case": "ranked-geometry-22 was developed and regression-tested before this run; report separately",
        "environment": _env_info(),
        "implementation_sha256": {
            f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files},
    })
    _write(output / "comparisons.json", comparisons)
    _write(output / "summary.json", {
        "runs": len(records), "valid": sum(r["valid"] for r in records),
        "comparisons": comparisons,
    })
    return {"runs": len(records), "valid": sum(r["valid"] for r in records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.output)
    print(f"runs={result['runs']} valid={result['valid']}")
    return 0 if result["runs"] == result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
