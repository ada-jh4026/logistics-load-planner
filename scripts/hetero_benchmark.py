"""Run the fixed known-feasible mixed-carton cases without selecting winners."""

from __future__ import annotations

import argparse
import json
import hashlib
import subprocess
import importlib.util
import sys
from pathlib import Path

from backend.models import SolveRequest
from scripts.benchmark import _data_hash
from scripts.benchmark import _env_info
from scripts.conflict_benchmark import METHODS, ROOT, _check_certificate, _run_one, _write


def run(output: Path, *, development: bool = False, mixed: bool = False,
        holdout: bool = False, legacy_packer: bool = False, methods=METHODS) -> dict:
    if (output / "runs.json").exists():
        raise ValueError("Choose a new output directory; existing experimental evidence is immutable")
    if legacy_packer:
        # Frozen historical implementation, loaded only in this benchmark process.
        path = ROOT / "artifacts/probes/legacy_packing_1c5054e.py"
        spec = importlib.util.spec_from_file_location("legacy_packing_1c5054e", path)
        legacy = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = legacy
        spec.loader.exec_module(legacy)
        import backend.baselines as baselines
        import backend.solver as solver
        import scripts.sequential_reinsert as reinsert
        baselines.pack_route = solver.pack_route = reinsert.pack_route = legacy.pack_route
        spec_solver = importlib.util.spec_from_file_location(
            "legacy_solver_1c5054e", ROOT / "artifacts/probes/legacy_solver_1c5054e.py")
        historical_solver = importlib.util.module_from_spec(spec_solver)
        sys.modules[spec_solver.name] = historical_solver
        spec_solver.loader.exec_module(historical_solver)
        historical_solver.pack_route = legacy.pack_route
        import scripts.conflict_benchmark as benchmark
        benchmark.solve = historical_solver.solve
    filename = ("mixed-holdout-manifest.json" if holdout else
                "mixed-manifest.json" if mixed else "manifest.json")
    source = json.loads((ROOT / "data/hetero_cases" / filename).read_text(encoding="utf-8"))
    if development:
        source = {"kind": "development_selected_after_packer_failure",
                  "cases": [{"case_id": "hetero-dev-6",
                             "path": "data/hetero_cases/hetero-development.json"}]}
    files = [str(p.relative_to(ROOT)).replace("\\", "/") for p in sorted((ROOT / "backend").glob("*.py"))]
    files += ["scripts/hetero_benchmark.py", "scripts/conflict_benchmark.py",
              "scripts/sequential_reinsert.py", "scripts/benchmark.py"]
    if legacy_packer:
        files += ["artifacts/probes/legacy_packing_1c5054e.py",
                  "artifacts/probes/legacy_solver_1c5054e.py"]
    hashes = {}
    for filename in files:
        raw = (ROOT / filename).read_bytes()
        snapshot = output / "implementation" / filename
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(raw)
        hashes[filename] = hashlib.sha256(raw).hexdigest()
    _write(output / "manifest.json", {**source, "methods": list(methods),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "environment": _env_info(), "legacy_packer": legacy_packer,
        "legacy_solver_commit": "1c5054e" if legacy_packer else None,
        "implementation_sha256": hashes,
        "note": "Synthetic cases; mixed inputs are not certified in advance. Explicit witnesses exist only where supplied."})
    records = []
    for entry in source["cases"]:
        path = ROOT / entry["path"]
        request = SolveRequest.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if request.case_id != entry["case_id"]:
            raise ValueError(f"case mismatch: {path}")
        if path.with_suffix(".meta.json").exists():
            metadata = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
            _check_certificate(request, metadata)
        data_hash = _data_hash(request)
        for method in methods:
            record = _run_one(request, method,
                              output / "runs" / request.case_id / method,
                              data_hash)
            records.append(record)
            print(f"{request.case_id} {method}: {record['metrics']['served_stores'] if record['metrics'] else 'ERROR'} valid={record['valid']}", flush=True)
            _write(output / "runs.json", records)
    _write(output / "summary.json", {
        "runs": len(records), "valid": sum(r["valid"] for r in records),
        "served": [{"case_id": r["case_id"], "method": r["method"],
                    "served_stores": r["metrics"]["served_stores"] if r["metrics"] else None,
                    "total_stores": r["metrics"]["total_stores"] if r["metrics"] else None}
                   for r in records],
    })
    return {"runs": len(records), "valid": sum(r["valid"] for r in records)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--development", action="store_true")
    group.add_argument("--mixed", action="store_true")
    group.add_argument("--holdout", action="store_true")
    parser.add_argument("--legacy", "--legacy-packer", dest="legacy_packer", action="store_true",
                        help="Use frozen packing AND solver implementations from 1c5054e; run in a separate process")
    parser.add_argument("--method", action="append", choices=METHODS)
    args = parser.parse_args()
    result = run(args.output, development=args.development, mixed=args.mixed,
                 holdout=args.holdout, legacy_packer=args.legacy_packer, methods=args.method or METHODS)
    print(result)
    return 0 if result["runs"] == result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
