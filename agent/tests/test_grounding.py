from agent.facts import build_facts
from agent.grounding import check_grounding
from agent.schemas import JobResponse, SolveRequest


def _facts(req, resp):
    return build_facts(SolveRequest(**req), JobResponse(**resp))


def test_numbers_in_facts_pass(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    text = "总费用 120 元，体积利用率 50%，载重利用率 30%，S01 等待 10 分钟，08:10 到达、08:20 开始，回仓 08:35，总里程 10 km。"
    checked, unmatched = check_grounding(text, f)
    assert unmatched == [] and checked >= 8


def test_fabricated_number_detected(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    checked, unmatched = check_grounding("总费用 150 元，利用率 50%。", f)
    assert unmatched == ["150 元"]


def test_fabricated_percent_and_time_detected(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    _, unmatched = check_grounding("利用率 65%，09:15 到达。", f)
    assert set(unmatched) == {"65%", "09:15"}


def test_ordinals_and_ids_are_not_facts(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    text = "第 1 站 S01：先卸 B02，再卸 B01。\n1. 从后门取出 B02\n2. 从后门取出 B01\n步骤 2 完成。"
    checked, unmatched = check_grounding(text, f)
    assert unmatched == []


def test_rounding_tolerance(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    f["metrics"]["total_distance_km"] = 10.04
    _, unmatched = check_grounding("总里程 10 km，或 10.0 km。", f)
    assert unmatched == []


def test_half_up_rounding_is_accepted(req_partial, resp_partial):
    """0.5625 → 模型写 56.3%（四舍五入）必须通过；Python round(56.25,1)=56.2 不能成为误判来源。"""
    f = _facts(req_partial, resp_partial)
    f["metrics"]["volume_utilization"] = 0.5625
    f["metrics"]["total_cost"] = 919.25
    _, unmatched = check_grounding("体积利用率 56.3%，也可写 56.2% 或 56%；总费用 919.3 元或 919.2 元或 919 元。", f)
    assert unmatched == []


def test_tolerance_does_not_accept_wrong_digit(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    f["metrics"]["volume_utilization"] = 0.5625
    _, unmatched = check_grounding("体积利用率 56.4%，总费用 121 元。", f)
    assert set(unmatched) == {"56.4%", "121 元"}

