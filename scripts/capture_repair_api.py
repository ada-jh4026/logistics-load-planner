"""Capture an actual POST /api/solve and GET /api/jobs response."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.models import JobResponse, SolveRequest
from backend.validation import validate_solution


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2),
                    encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    request = SolveRequest.model_validate(raw)
    if request.options.method != "coupled":
        raise ValueError("expected coupled request")

    client = TestClient(app)
    posted = client.post("/api/solve", json=request.model_dump())
    if posted.status_code != 202:
        raise RuntimeError(f"POST failed: {posted.status_code} {posted.text}")
    run_id = posted.json()["run_id"]
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        polled = client.get(f"/api/jobs/{run_id}")
        if polled.status_code != 200:
            raise RuntimeError(f"GET failed: {polled.status_code}")
        body = polled.json()
        if body["status"] in ("succeeded", "partial", "failed"):
            break
        time.sleep(0.02)
    else:
        raise TimeoutError(f"run {run_id} did not finish")
    response = JobResponse.model_validate(body)
    if response.result is None:
        raise RuntimeError(f"solver did not return result: {response.status}")
    violations = validate_solution(request, response.result)
    _write(args.output / "request.json", request.model_dump())
    _write(args.output / "post_response.json", posted.json())
    _write(args.output / "job_response.json", body)
    _write(args.output / "validation.json", {
        "valid": not violations,
        "violations": [v.model_dump() for v in violations],
    })
    print(f"case={response.case_id} http_post=202 job={response.status} "
          f"trace={response.result.repair_trace.status} valid={not violations}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
