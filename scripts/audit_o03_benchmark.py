"""Independently revalidate every persisted O03 request and response."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.models import Result, SolveRequest
from backend.validation import validate_solution
from scripts.benchmark import _data_hash


def audit(directory: Path) -> dict:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    records = json.loads((directory / "runs.json").read_text(encoding="utf-8"))
    expected = {(entry["case_id"], variant)
                for entry in manifest["cases"] for variant in manifest["variants"]}
    hashes = {entry["case_id"]: _data_hash(SolveRequest.model_validate(json.loads(
        Path(entry["path"]).read_text(encoding="utf-8"))))
        for entry in manifest["cases"]}
    assert len(records) == len(expected)
    assert {(r["case_id"], r["variant"]) for r in records} == expected
    accepted = 0
    for record in records:
        base = directory / "runs" / record["case_id"] / record["variant"]
        request = SolveRequest.model_validate(json.loads(
            (base / "request.json").read_text(encoding="utf-8")))
        result = Result.model_validate(json.loads(
            (base / "response.json").read_text(encoding="utf-8")))
        validation = json.loads((base / "validation.json").read_text(encoding="utf-8"))
        assert validation == {"valid": True, "violations": []}
        assert record["valid"] and validate_solution(request, result) == []
        assert result.metrics.model_dump() == record["metrics"]
        assert sorted(s for route in result.routes for s in route.store_ids) == record["served_store_ids"]
        assert hashes[record["case_id"]] == record["data_hash"]
        if record["variant"] == "sequential_reinsert":
            assert request.options.method == "sequential" and result.repair_trace is None
        else:
            assert request.options.method == "coupled"
            trace = result.repair_trace
            assert trace is not None and trace.final_metrics == result.metrics
            state = [r.model_dump() for r in trace.initial_routes]
            count = 0
            for event in trace.events:
                if event.outcome == "accepted":
                    assert [r.model_dump() for r in event.routes_before] == state
                    state = [r.model_dump() for r in event.routes_after]
                    count += 1
            assert state == [r.model_dump() for r in result.routes]
            assert count == trace.accepted_count
            accepted += count
    return {"runs": len(records), "validated": len(records), "accepted_events": accepted}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    print(audit(args.input))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
