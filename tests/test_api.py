"""B13 HTTP 接口测试（CONTRACT API/JobResponse）。"""

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app, jobs

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_jobs():
    jobs._queue.clear()
    jobs._jobs.clear()
    yield
    jobs._queue.clear()
    jobs._jobs.clear()


def _valid_request() -> dict:
    return json.loads(Path("data/cases/c01.json").read_text(encoding="utf-8"))


def _poll(run_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{run_id}").json()
        if body["status"] in ("succeeded", "partial", "failed"):
            return body
        time.sleep(0.02)
    return body


# --------------------------------------------------------------------------
# health / examples
# --------------------------------------------------------------------------

def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "schema_version": "0.1"}


def test_list_examples():
    resp = client.get("/api/examples")
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["case_id"] == "c01" for i in items)


def test_get_example():
    resp = client.get("/api/examples/c01")
    assert resp.status_code == 200
    assert resp.json()["case_id"] == "c01"


def test_get_example_unknown_404():
    resp = client.get("/api/examples/nonexistent")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_get_example_path_traversal_rejected():
    resp = client.get("/api/examples/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# solve / jobs
# --------------------------------------------------------------------------

def test_solve_and_poll_success():
    resp = client.post("/api/solve", json=_valid_request())
    assert resp.status_code == 202
    body = resp.json()
    assert body["schema_version"] == "0.1"
    assert body["status"] == "queued"
    run_id = body["run_id"]

    result = _poll(run_id)
    assert result["status"] == "succeeded"
    assert result["is_mock"] is False
    assert result["termination_reason"] == "completed"
    assert result["elapsed_ms"] >= 0
    assert result["result"] is not None


def test_solve_partial_for_unservable():
    data = json.loads(Path("data/cases/c07.json").read_text(encoding="utf-8"))
    resp = client.post("/api/solve", json=data)
    run_id = resp.json()["run_id"]
    result = _poll(run_id)
    assert result["status"] == "partial"
    assert result["result"]["unassigned"]


def test_job_unknown_404():
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_invalid_input_422_not_queued():
    data = _valid_request()
    data["boxes"][1]["id"] = data["boxes"][0]["id"]  # 重复 ID
    resp = client.post("/api/solve", json=data)
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "INVALID_INPUT"
    assert body["error"]["details"]  # 有字段错误明细


def test_queue_full_429():
    jobs._max_queue = 0
    try:
        resp = client.post("/api/solve", json=_valid_request())
        assert resp.status_code == 429
        assert resp.json()["error"]["code"] == "QUEUE_FULL"
    finally:
        jobs._max_queue = 8
