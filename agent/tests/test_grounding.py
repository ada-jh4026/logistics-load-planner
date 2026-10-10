from agent.facts import build_facts
from agent.grounding import check_grounding, cn_to_number
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



# ---- 2026-10-10 审查 B3：以下五类文本以前都能拿到 passed=true ----
def test_digits_adjacent_to_chinese_are_extracted(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    checked, unmatched = check_grounding("总费用99999元。启用1辆车。", f)
    assert "99999 元" in unmatched and checked == 2


def test_chinese_numerals_are_converted_and_checked(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    _, unmatched = check_grounding("总费用为九万九千九百九十九元。", f)
    assert unmatched == ["九万九千九百九十九元"]
    _, unmatched = check_grounding("总费用一百二十元，总里程十公里，完成率百分之五十。", f)
    assert unmatched == []
    assert cn_to_number("一千二") == 1200 and cn_to_number("一万二") == 12000 and cn_to_number("两") == 2


def test_multiplier_unit_is_applied(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    _, unmatched = check_grounding("总里程为 10 万公里。", f)
    assert unmatched == ["10 万 公里"]


def test_derived_sum_is_rejected(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    _, unmatched = check_grounding("总费用 120 元，再加 120 元，合计费用240元。", f)
    assert unmatched == ["240 元"]


def test_entity_bound_measure_cannot_borrow_global_total(req_partial, resp_partial):
    """「V01 的费用 120 元」恰好等于总费用时仍通过（本例单车即全局）；改成不属于 V01 的数值必须被拦。"""
    f = _facts(req_partial, resp_partial)
    f["metrics"]["total_cost"] = 500.0  # 制造全局合计 ≠ 单车
    _, unmatched = check_grounding("V01 的费用为 500 元。", f)
    assert unmatched == ["500 元"]
    _, unmatched = check_grounding("V01 的费用为 120 元，总费用 500 元。", f)
    assert unmatched == []
    # 计数类单位允许退回全局：「V01 停靠 1 站，共 2 家门店」
    _, unmatched = check_grounding("V01 停靠 1 站，案例共 2 家门店。", f)
    assert unmatched == []


def test_article_yi_and_ordinals_are_not_facts(req_partial, resp_partial):
    f = _facts(req_partial, resp_partial)
    checked, unmatched = check_grounding("没有一处卸货阻挡；第一站 S01，下一站回仓。", f)
    assert unmatched == [] and checked == 0
