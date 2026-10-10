import json
from pathlib import Path

import pytest

from agent.interpret import apply_ops, interpret
from agent.llm import FakeLLM, NullLLM
from agent.schemas import IntentOp, InterpretRequest, SolveRequest
from agent.tests.checks import load_request, verify
from agent.timeparse import find_time, to_minutes

DATA = Path(__file__).with_name("data") / "instructions.jsonl"
CASES = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
RULE_CASES = [c for c in CASES if c["mode"] == "rule"]


@pytest.mark.parametrize("case", RULE_CASES, ids=[c["id"] for c in RULE_CASES])
def test_rule_mode(case):
    original = load_request(case["request"])
    req = InterpretRequest(schema_version="0.1", request=original, instruction=case["instruction"])
    r = interpret(req, NullLLM())
    assert r.mode == "template" and r.model is None
    resp = r.model_dump()
    patched = r.patched_request.model_dump() if r.patched_request else None
    errs = verify(original, patched, case["expect"], resp)
    assert not errs, f"{case['instruction']!r}: {errs}\nsummary={r.summary}"


def test_time_parsing():
    assert find_time("14:00")[0] == 840
    assert find_time("下午两点")[0] == 840
    assert find_time("上午 9 点半")[0] == 570
    assert find_time("晚上八点二十")[0] == 1220
    assert find_time("中午12点")[0] == 720
    assert find_time("十一点")[0] == 660
    assert to_minutes(840) == 840 and to_minutes("840") == 840 and to_minutes("14:00") == 840
    assert to_minutes("随便") is None


def test_whitelist_blocks_dimension_and_unknown_target():
    original = SolveRequest(**load_request("partial"))
    ops = [
        IntentOp(action="set", target="box", id="B01", field="length_mm", value=500),
        IntentOp(action="set", target="vehicle", id="V01", field="max_weight_kg", value=9999),
        IntentOp(action="set", target="store", id="S01", field="x_km", value=0),
    ]
    patch, patched, rejected, accepted = apply_ops(original, ops)
    assert patch == [] and accepted == [] and len(rejected) == 3
    assert patched.model_dump() == original.model_dump()
    assert all("不在允许修改范围" in x.reason or "不支持 set" in x.reason for x in rejected)


def test_remove_last_vehicle_rejected_but_other_ops_continue():
    original = SolveRequest(**load_request("partial"))
    ops = [
        IntentOp(action="remove_vehicle", target="vehicle", id="V01"),
        IntentOp(action="set", target="options", field="seed", value=7),
    ]
    patch, patched, rejected, accepted = apply_ops(original, ops)
    assert len(rejected) == 1 and "至少保留一辆车" in rejected[0].reason
    assert [p.path for p in patch] == ["/options/seed"] and patched.options.seed == 7


def test_sequential_remove_resolves_indices_at_each_step():
    r = load_request("partial2v")
    v3 = dict(r["vehicles"][0], id="V03")
    r["vehicles"].append(v3)
    original = SolveRequest(**r)
    ops = [IntentOp(action="remove_vehicle", target="vehicle", id="V01"), IntentOp(action="remove_vehicle", target="vehicle", id="V03")]
    patch, patched, rejected, _ = apply_ops(original, ops)
    # V01 在下标 0；移除后 V03 的下标从 2 变 1
    assert [p.path for p in patch] == ["/vehicles/0", "/vehicles/1"]
    assert [v.id for v in patched.vehicles] == ["V02"] and rejected == []


def test_add_vehicle_duplicate_id_rejected():
    original = SolveRequest(**load_request("partial"))
    v = original.vehicles[0].model_dump()
    ops = [IntentOp(action="add_vehicle", target="vehicle", value=v)]
    _, _, rejected, _ = apply_ops(original, ops)
    assert len(rejected) == 1 and "已存在" in rejected[0].reason


def test_llm_mode_uses_same_pipeline(req_partial):
    original = load_request("partial")
    llm = FakeLLM([json.dumps({"intent_ops": [
        {"action": "set", "target": "store", "id": "S01", "field": "window_end_min", "value": "14:00"},
        {"action": "set", "target": "box", "id": "B01", "field": "length_mm", "value": 500},
        {"action": "set", "target": "store", "id": "S99", "field": "window_start_min", "value": 600},
    ], "summary": "改 S01 时间窗"}, ensure_ascii=False)])
    r = interpret(InterpretRequest(schema_version="0.1", request=original, instruction="S01 下午两点前送到，B01 长度 500，S99 十点"), llm)
    assert r.mode == "llm" and r.model == "fake" and r.understood
    assert [p.path for p in r.patch] == ["/stores/0/window_end_min"] and r.patch[0].value == 840
    reasons = [x.reason for x in r.rejected_ops]
    assert len(reasons) == 2 and any("不在允许修改范围" in x for x in reasons) and any("S99 不存在" in x for x in reasons)
    assert r.patched_request.stores[0].window_end_min == 840 and r.patched_request.boxes[0].length_mm == 1000
    user = llm.calls[0][1]
    assert "x_km" not in user and '"S01"' in user  # 实体清单不含坐标


def test_llm_garbage_falls_back_to_rules():
    original = load_request("partial")
    llm = FakeLLM(["这不是 JSON"])
    r = interpret(InterpretRequest(schema_version="0.1", request=original, instruction="时间预算 20 秒"), llm)
    assert r.mode == "template" and any("规则模式" in w for w in r.warnings)
    assert r.patched_request.options.time_limit_ms == 20000


def test_llm_empty_ops_means_not_understood():
    original = load_request("partial")
    llm = FakeLLM([json.dumps({"intent_ops": [], "summary": "请说明要改哪家门店"})])
    r = interpret(InterpretRequest(schema_version="0.1", request=original, instruction="今天天气不错"), llm)
    assert r.mode == "llm" and not r.understood and r.patch == [] and "请说明" in r.summary
