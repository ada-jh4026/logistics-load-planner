"""O04 第一步：智能体严格模型必须接受带 repair_trace 的新响应，也必须接受缺字段的旧响应。"""
import json
from pathlib import Path

import pytest

from agent.facts import build_facts
from agent.schemas import JobResponse, SolveRequest

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "artifacts" / "repair-trace"


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", ["api-geometry-22", "api-time-geometry-22"])
def test_real_coupled_response_with_trace_parses(case):
    d = REAL / case
    if not d.is_dir():
        pytest.skip(f"{d} 不存在")
    job = JobResponse(**_load(d / "job_response.json"))
    req = SolveRequest(**_load(d / "request.json"))
    rt = job.result.repair_trace
    assert rt is not None and rt.version == 1 and rt.status == "repaired"
    assert rt.accepted_count >= 1 and rt.attempted_count >= rt.accepted_count
    accepted = [e for e in rt.events if e.outcome == "accepted"]
    assert accepted and all(e.routes_before is not None and e.routes_after is not None for e in accepted)
    assert all(e.routes_before is None for e in rt.events if e.outcome != "accepted")
    # 事实表照常工作
    f = build_facts(req, job)
    assert f["metrics"]["served_stores"] == job.result.metrics.served_stores


def test_old_response_without_trace_parses(resp_success):
    assert "repair_trace" not in resp_success["result"]
    job = JobResponse(**resp_success)
    assert job.result.repair_trace is None


def test_explicit_null_trace_parses(resp_partial):
    body = json.loads(json.dumps(resp_partial))
    body["result"]["repair_trace"] = None
    assert JobResponse(**body).result.repair_trace is None


def test_not_needed_trace_from_small_11():
    p = REAL / "small-11" / "response.json"
    if not p.is_file():
        pytest.skip("样例不存在")
    body = _load(p)  # 这是不带 JobResponse 外壳的 Result
    from agent.schemas import Result

    r = Result(**body)
    assert r.repair_trace is not None and r.repair_trace.status == "not_needed"
    assert r.repair_trace.attempted_count == 0 and r.repair_trace.events == []


def test_unknown_status_rejected(resp_success):
    body = json.loads(json.dumps(resp_success))
    body["result"]["repair_trace"] = {
        "version": 1, "status": "magic", "initial_metrics": body["result"]["metrics"], "final_metrics": body["result"]["metrics"],
        "initial_routes": [], "attempted_count": 0, "accepted_count": 0, "events": [], "truncated": False, "omitted_count": 0,
    }
    with pytest.raises(Exception):
        JobResponse(**body)
