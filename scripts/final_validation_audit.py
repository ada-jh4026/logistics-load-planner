"""Revalidate published experimental outputs after validator changes; never rerun or rewrite them."""
import hashlib
import json
from pathlib import Path

from backend.models import Result, SolveRequest
from backend.validation import validate_solution
from backend.unloading import generate_loading_steps, validate_loading_steps


def main():
    root = Path(__file__).resolve().parents[1]
    names = ["i02-20261010-small", "i02-20261010-standard", "i02-20261010-stress",
             "o02-conflict-20261010", "o03-ranked-20261010",
             "hetero-mixed-after-20261010", "hetero-holdout-20261010"]
    rows = []
    for name in names:
        directory = root / "artifacts/benchmarks" / name
        for path in sorted(directory.glob("runs/**/request.json")):
            request = SolveRequest.model_validate_json(path.read_text(encoding="utf-8"))
            response_path = path.with_name("response.json")
            result = Result.model_validate_json(response_path.read_text(encoding="utf-8"))
            violations = validate_solution(request, result)
            boxes = {b.id: b for b in request.boxes}
            vehicles = {v.id: v for v in request.vehicles}
            for route in result.routes:
                violations.extend(validate_loading_steps(generate_loading_steps(route.unload_steps),
                                  boxes, route.placements, vehicles[route.vehicle_id]))
            rows.append({"path": str(response_path.relative_to(root)),
                         "sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
                         "valid": not violations, "violations": [v.model_dump() for v in violations]})
    report = {"date": "2026-10-11", "kind": "revalidation_of_saved_outputs_not_new_solver_runs",
              "validator_sha256": hashlib.sha256((root / "backend/validation.py").read_bytes()).hexdigest(),
              "runs": len(rows), "valid": sum(r["valid"] for r in rows), "records": rows}
    output = root / "artifacts/evidence/B1-B2-revalidation.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"runs={report['runs']} valid={report['valid']}")
    return 0 if rows and all(r["valid"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
