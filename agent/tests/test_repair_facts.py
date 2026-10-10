"""O04：事实表与模板解释中的协同修复事实。"""
import json
from pathlib import Path

import pytest

from agent.explain import explain
from agent.facts import build_facts
from agent.llm import FakeLLM, NullLLM
from agent.schemas import ExplainRequest, JobResponse, SolveRequest
from agent.templates import render, repair_block

ROOT = Path(__file__).resolve().parents[2]


def _real(case: str):
    d = ROOT / "artifacts" / "repair-trace" / case
    if not d.is_dir():
        pytest.skip(f"{d} 不存在")
    job = JobResponse(**json.loads((d / "job_response.json").read_text(encoding="utf-8")))
    req = SolveRequest(**json.loads((d / "request.json").read_text(encoding="utf-8")))
    return req, job


def test_repair_facts_from_real_repaired_case():
    req, job = _real("api-geometry-22")
    f = build_facts(req, job)
    rep = f["repair"]
    assert rep["provided"] and rep["status"] == "repaired" and rep["accepted_count"] >= 1
    assert rep["initial_served_stores"] < rep["final_served_stores"] == rep["total_stores"]
    assert rep["same_served_set"] is False and rep["cost_comparable"] is False
    assert rep["accepted"][0]["target_vehicle_id"]
    text = render(f, "overview")
    assert "协同修复：修复成功" in text and "采用 1 次" in text and "不可直接比较" in text
    assert text.count("- 采用：") == len(rep["accepted"][:3])  # 只转述 accepted


def test_old_response_without_trace_says_not_provided(req_success, resp_success):
    f = build_facts(SolveRequest(**req_success), JobResponse(**resp_success))
    assert f["repair"] is None
    assert repair_block(f) == "协同修复：此记录未提供修复过程。"


def test_not_needed_is_not_claimed_as_benefit(req_success, resp_success):
    body = json.loads(json.dumps(resp_success))
    m = body["result"]["metrics"]
    body["result"]["repair_trace"] = {
        "version": 1, "status": "not_needed", "initial_metrics": m, "final_metrics": m,
        "initial_routes": body["result"]["routes"], "attempted_count": 0, "accepted_count": 0,
        "events": [], "truncated": False, "omitted_count": 0,
    }
    f = build_facts(SolveRequest(**req_success), JobResponse(**body))
    assert f["repair"]["status"] == "not_needed"
    assert repair_block(f) == "协同修复：初始方案已全部可执行，未触发修复。"


def test_non_coupled_method_has_no_repair_block(req_partial, resp_partial):
    body = json.loads(json.dumps(resp_partial))
    body["method"] = "greedy"
    f = build_facts(SolveRequest(**req_partial), JobResponse(**body))
    assert repair_block(f) == ""


def test_llm_prompt_carries_repair_facts_and_grounding_covers_counts():
    req, job = _real("api-geometry-22")
    llm = FakeLLM(["**全部配送**。协同修复：发现 1 处装载失败，检查 1 个候选，采用 1 次，可执行门店从 0 变为 2。"])
    r = explain(ExplainRequest(schema_version="0.1", request=req, response=job, focus="overview"), llm)
    assert r.mode == "llm" and r.grounding.passed
    assert '"repair"' in llm.calls[0][1] and "not_needed" in llm.calls[0][0]


def test_template_mode_mentions_repair():
    req, job = _real("api-time-geometry-22")
    r = explain(ExplainRequest(schema_version="0.1", request=req, response=job, focus="overview"), NullLLM())
    assert r.mode == "template" and "协同修复：" in r.text
