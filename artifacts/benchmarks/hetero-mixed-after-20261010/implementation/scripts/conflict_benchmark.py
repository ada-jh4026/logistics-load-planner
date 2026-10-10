"""Run every predeclared O02 case with three public methods and one adapter."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import time
import traceback
from pathlib import Path

from backend.budget import Budget
from backend.models import Placement, SolveRequest, UnloadStep
from backend.solver import solve
from backend.unloading import generate_unload_steps
from backend.validation import validate_solution, validate_vehicle_candidate
from scripts.benchmark import _data_hash, _env_info, cost_improvement
from scripts.sequential_reinsert import solve_sequential_reinsert

ROOT = Path(__file__).resolve().parents[1]
METHODS = ("greedy", "sequential", "sequential_reinsert", "coupled")


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def _check_certificate(request: SolveRequest, metadata: dict) -> None:
    for route in metadata.get("feasible_witness", []):
        placements = [Placement.model_validate(p)
                      for p in route["placements"]]
        steps = [UnloadStep.model_validate(s)
                 for s in route["unload_steps"]]
        violations = validate_vehicle_candidate(
            request, route["vehicle_id"], route["store_ids"],
            placements, steps)
        if violations:
            raise ValueError(f"{request.case_id}: invalid witness {violations}")
    blocked = metadata.get("blocked_candidate")
    if blocked:
        boxes = {b.id: b for b in request.boxes}
        placements = [Placement.model_validate(p)
                      for p in blocked["placements"]]
        _, error = generate_unload_steps(
            boxes, placements,
            metadata["feasible_witness"][0]["store_ids"])
        if error is None or error.code != blocked["violation"]:
            raise ValueError(f"{request.case_id}: blocked certificate changed")
    impossible = metadata.get("certificate")
    if impossible:
        box = next(b for b in request.boxes
                   if b.id == impossible["box_id"])
        if box.allow_rotate_xy or not all(
                box.length_mm > v.length_mm for v in request.vehicles):
            raise ValueError(f"{request.case_id}: infeasibility certificate changed")


def _run_one(original: SolveRequest, method: str, directory: Path,
             data_hash: str) -> dict:
    request = original.model_copy(deep=True)
    request.options.method = ("sequential" if method == "sequential_reinsert"
                              else method)
    _write(directory / "request.json", request.model_dump())
    budget = Budget(request.options.time_limit_ms,
                    request.options.max_iterations)
    started = time.monotonic()
    record = {"case_id": request.case_id, "method": method,
              "data_hash": data_hash, "valid": False,
              "served_store_ids": [], "metrics": None,
              "violations": []}
    try:
        if method == "sequential_reinsert":
            result = solve_sequential_reinsert(request, budget)
        else:
            result = solve(request, budget)
        violations = validate_solution(request, result)
        record.update({
            "valid": not violations,
            "served_store_ids": sorted(sid for route in result.routes
                                        for sid in route.store_ids),
            "metrics": result.metrics.model_dump(),
            "violations": [v.code for v in violations],
            "repair_status": (result.repair_trace.status
                              if result.repair_trace else None),
            "repair_attempted": (result.repair_trace.attempted_count
                                 if result.repair_trace else None),
            "repair_accepted": (result.repair_trace.accepted_count
                                if result.repair_trace else None),
        })
        _write(directory / "response.json", result.model_dump())
        _write(directory / "validation.json", {
            "valid": not violations,
            "violations": [v.model_dump() for v in violations],
        })
    except Exception as exc:
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        record["violations"] = ["SOLVER_EXCEPTION"]
        _write(directory / "error.json", {
            **record["error"], "traceback": traceback.format_exc()})
    record["elapsed_ms"] = (time.monotonic() - started) * 1000
    record["termination_reason"] = (
        "exception" if "error" in record else budget.termination_reason())
    return record


def run(output: Path, selected: set[str] | None = None) -> dict:
    manifest_path = ROOT / "data/conflict_cases/manifest.json"
    source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = source_manifest["cases"]
    if selected is not None:
        unknown = selected - {entry["case_id"] for entry in entries}
        if unknown:
            raise ValueError(f"unknown cases: {sorted(unknown)}")
        entries = [entry for entry in entries if entry["case_id"] in selected]
    runs = []
    output.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        case_path = ROOT / entry["path"]
        raw = json.loads(case_path.read_text(encoding="utf-8"))
        if raw.get("is_mock") is True:
            raise ValueError(f"mock case: {case_path}")
        request = SolveRequest.model_validate(raw)
        if request.case_id != entry["case_id"]:
            raise ValueError(f"case id mismatch: {case_path}")
        meta_path = case_path.with_suffix(".meta.json")
        if meta_path.is_file():
            _check_certificate(request,
                               json.loads(meta_path.read_text(encoding="utf-8")))
        data_hash = _data_hash(request)
        for method in METHODS:
            record = _run_one(request, method,
                              output / "runs" / request.case_id / method,
                              data_hash)
            record["category"] = entry["category"]
            runs.append(record)
            _write(output / "runs.json", runs)

    comparisons = []
    by_case = {(r["case_id"], r["method"]): r for r in runs}
    for entry in entries:
        cid = entry["case_id"]
        coupled = by_case[(cid, "coupled")]
        for baseline in METHODS[:-1]:
            improvement, reason = cost_improvement(
                by_case[(cid, baseline)], coupled)
            comparisons.append({"case_id": cid, "category": entry["category"],
                                "baseline": baseline, "candidate": "coupled",
                                "cost_improvement": improvement,
                                "reason": reason})

    implementation_files = [
        "backend/models.py", "backend/solver.py", "backend/baselines.py",
        "backend/packing.py", "backend/validation.py",
        "scripts/sequential_reinsert.py", "scripts/conflict_benchmark.py",
        "scripts/generate_conflict_cases.py"]
    fingerprint = hashlib.sha256()
    for name in implementation_files:
        fingerprint.update(name.encode("utf-8"))
        fingerprint.update((ROOT / name).read_bytes())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                            capture_output=True, text=True, check=True).stdout
    output_manifest = {
        "source_manifest": str(manifest_path.relative_to(ROOT)),
        "selection": ("all_predeclared" if selected is None else "development_subset"),
        "cases": entries, "methods": list(METHODS),
        "sequential_reinsert_adapter": (
            "request.options.method=sequential; adapter runs after sequential "
            "and is not a public API method"),
        "code_commit": commit, "dirty_worktree": bool(status),
        "implementation_sha256": fingerprint.hexdigest(),
        "environment": _env_info(), "total_runs": len(runs),
    }
    _write(output / "manifest.json", output_manifest)
    _write(output / "summary.json", {
        "total_runs": len(runs), "valid_runs": sum(r["valid"] for r in runs),
        "comparisons": comparisons})
    fields = ["case_id", "category", "method", "data_hash", "valid",
              "elapsed_ms", "termination_reason", "served_stores",
              "total_cost", "used_vehicles", "repair_status",
              "repair_attempted", "repair_accepted"]
    with (output / "runs.csv").open("w", encoding="utf-8-sig",
                                    newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in runs:
            metrics = record["metrics"] or {}
            writer.writerow({field: record.get(field, metrics.get(field))
                             for field in fields})
    return {"runs": len(runs), "valid": sum(r["valid"] for r in runs),
            "comparisons": len(comparisons)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append",
                        help="development subset only; omit for formal run")
    args = parser.parse_args()
    result = run(args.output, set(args.case) if args.case else None)
    print(f"runs={result['runs']} valid={result['valid']} "
          f"comparisons={result['comparisons']}")
    return 0 if result["valid"] == result["runs"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
