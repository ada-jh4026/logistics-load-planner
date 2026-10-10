"""Recheck every stored O02 response with the independent validator."""

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
    expected = {(entry["case_id"], method)
                for entry in manifest["cases"]
                for method in manifest["methods"]}
    actual = {(record["case_id"], record["method"]) for record in records}
    assert actual == expected and len(records) == len(expected)

    accepted = 0
    for record in records:
        assert record["valid"] is True and "error" not in record
        base = directory / "runs" / record["case_id"] / record["method"]
        request = SolveRequest.model_validate(json.loads(
            (base / "request.json").read_text(encoding="utf-8")))
        response = Result.model_validate(json.loads(
            (base / "response.json").read_text(encoding="utf-8")))
        validation = json.loads((base / "validation.json")
                                .read_text(encoding="utf-8"))
        assert validation == {"valid": True, "violations": []}
        assert validate_solution(request, response) == []
        assert response.metrics.model_dump() == record["metrics"]
        assert sorted(sid for route in response.routes
                      for sid in route.store_ids) == record["served_store_ids"]
        assert record["data_hash"] == next(
            _data_hash(SolveRequest.model_validate(json.loads(
                (Path(entry["path"])).read_text(encoding="utf-8"))))
            for entry in manifest["cases"]
            if entry["case_id"] == record["case_id"])
        if record["method"] == "sequential_reinsert":
            assert request.options.method == "sequential"
        else:
            assert request.options.method == record["method"]

        trace = response.repair_trace
        if record["method"] == "coupled":
            assert trace is not None
            assert trace.final_metrics == response.metrics
            state = [route.model_dump() for route in trace.initial_routes]
            event_accepted = 0
            for event in trace.events:
                if event.outcome == "accepted":
                    assert [r.model_dump() for r in event.routes_before] == state
                    state = [r.model_dump() for r in event.routes_after]
                    event_accepted += 1
            assert state == [route.model_dump() for route in response.routes]
            assert event_accepted == trace.accepted_count
            accepted += event_accepted
        else:
            assert trace is None
    return {"runs": len(records), "validated": len(records),
            "accepted_events": accepted}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    outcome = audit(args.input)
    print(" ".join(f"{key}={value}" for key, value in outcome.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
