"""Re-audit frozen heterogeneous runs, including loading and trace destinations."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backend.models import Result, SolveRequest
from backend.unloading import generate_loading_steps, validate_loading_steps
from scripts.audit_conflict_benchmark import audit


def run(directory: Path) -> dict:
    summary = audit(directory)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    records = json.loads((directory / "runs.json").read_text(encoding="utf-8"))
    expected = {(case["case_id"], method) for case in manifest["cases"]
                for method in manifest["methods"]}
    assert len(records) == len(expected)
    assert {(r["case_id"], r["method"]) for r in records} == expected
    for name, checksum in manifest["implementation_sha256"].items():
        raw = (directory / "implementation" / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == checksum, name
    sources = {entry["case_id"]: SolveRequest.model_validate(json.loads(
        Path(entry["path"]).read_text(encoding="utf-8"))) for entry in manifest["cases"]}
    loading_routes = 0
    for record in records:
        path = directory / "runs" / record["case_id"] / record["method"]
        request = SolveRequest.model_validate(json.loads((path / "request.json").read_text(encoding="utf-8")))
        source = sources[record["case_id"]].model_copy(deep=True)
        source.options.method = request.options.method
        assert source == request, "Input changed beyond method"
        result = Result.model_validate(json.loads((path / "response.json").read_text(encoding="utf-8")))
        boxes = {b.id: b for b in request.boxes}
        vehicles = {v.id: v for v in request.vehicles}
        for route in result.routes:
            assert validate_loading_steps(generate_loading_steps(route.unload_steps),
                                          boxes, route.placements, vehicles[route.vehicle_id]) == []
            loading_routes += 1
        if result.repair_trace:
            for event in result.repair_trace.events:
                if event.outcome == "accepted":
                    assert all(any(r.vehicle_id == event.target_vehicle_id and sid in r.store_ids
                                   for r in event.routes_after) for sid in event.store_ids)
    return {**summary, "loading_routes_validated": loading_routes,
            "source_snapshots_verified": len(manifest["implementation_sha256"])}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.input)))
