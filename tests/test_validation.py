"""B08 组合校验器测试（ACCEPTANCE C07/C09）。"""

import copy
import json
import pytest
from pathlib import Path

from backend.models import Result, SolveRequest, Unassigned
from backend.validation import validate_solution

EXAMPLES = Path("docs/playbook/examples")


def _success_request() -> SolveRequest:
    data = json.loads((EXAMPLES / "request-success.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _success_result() -> Result:
    data = json.loads((EXAMPLES / "response-success.json").read_text(encoding="utf-8"))
    return Result.model_validate(data["result"])


def _codes(violations):
    return {v.code for v in violations}


# --------------------------------------------------------------------------
# 成功样例
# --------------------------------------------------------------------------

def test_success_sample_passes():
    req = _success_request()
    res = _success_result()
    violations = validate_solution(req, res)
    assert violations == []


def test_all_unassigned_partial_allowed():
    req = _success_request()
    res = _success_result()
    # 全部箱移到 unassigned，routes 清空（部分计划，但无漏箱）
    res.unassigned = [Unassigned(store_id="S01", box_ids=["B01", "B02"],
                                 reason_code="SEARCH_EXHAUSTED", message="")]
    res.routes = []
    violations = validate_solution(req, res)
    # 无 BOX_MISSING / BOX_DUPLICATE；但 metrics 会不匹配（claimed 仍为满服务）
    assert "BOX_MISSING" not in _codes(violations)
    assert "BOX_DUPLICATE" not in _codes(violations)


# --------------------------------------------------------------------------
# C09 逐项篡改
# --------------------------------------------------------------------------

def test_duplicate_box_detected():
    req = _success_request()
    res = _success_result()
    res.unassigned.append(Unassigned(store_id="S01", box_ids=["B01"],
                                     reason_code="X", message="dup"))
    assert "BOX_DUPLICATE" in _codes(validate_solution(req, res))


def test_missing_box_detected():
    req = _success_request()
    res = _success_result()
    res.routes[0].box_ids = ["B01"]  # 移除 B02，且不进 unassigned
    assert "BOX_MISSING" in _codes(validate_solution(req, res))


def test_vehicle_reused_detected():
    req = _success_request()
    res = _success_result()
    res.routes.append(copy.deepcopy(res.routes[0]))  # 两路线同用 V01
    assert "VEHICLE_REUSED" in _codes(validate_solution(req, res))


def test_store_split_detected():
    req = _success_request()
    res = _success_result()
    res.routes[0].box_ids = ["B01"]  # B01 留在路线
    res.unassigned.append(Unassigned(store_id="S01", box_ids=["B02"],
                                     reason_code="X", message="split"))
    assert "STORE_SPLIT" in _codes(validate_solution(req, res))


def test_route_store_mismatch_detected():
    req = _success_request()
    res = _success_result()
    res.routes[0].store_ids = ["S99"]  # 门店与箱件门店不一致
    assert "STORE_SPLIT" in _codes(validate_solution(req, res))


def test_fake_cost_detected():
    req = _success_request()
    res = _success_result()
    res.metrics.total_cost = 1.0  # 伪造费用
    assert "METRIC_MISMATCH" in _codes(validate_solution(req, res))


def test_fake_volume_utilization_detected():
    req = _success_request()
    res = _success_result()
    res.metrics.volume_utilization = 0.9  # 伪造利用率
    assert "METRIC_MISMATCH" in _codes(validate_solution(req, res))


from artifacts.probes.validator_tamper_probe import TAMPERS, _base


@pytest.mark.parametrize("tamper", TAMPERS, ids=lambda fn: fn.__name__)
def test_review_tampering_is_rejected(tamper):
    request, data = _base("small-11" if tamper.__name__ == "t_shuffle_stop_order_fields" else "c01")
    original = copy.deepcopy(data)
    tamper(data)
    assert data != original, "Probe must actually modify this case"
    assert validate_solution(request, Result.model_validate(data))


@pytest.mark.parametrize("field", ["arrival_min", "service_start_min", "departure_min"])
def test_each_stop_timestamp_is_recomputed(field):
    req, data = _base()
    data["routes"][0]["stops"][0][field] += 1
    assert "METRIC_MISMATCH" in _codes(validate_solution(req, Result.model_validate(data)))


@pytest.mark.parametrize("location", ["vehicle", "store", "box", "placement", "unload", "stop"])
def test_unknown_references_return_violations_instead_of_crashing(location):
    req, data = _base()
    route = data["routes"][0]
    if location == "vehicle":
        route["vehicle_id"] = "UNKNOWN"
    elif location == "store":
        route["store_ids"][0] = "UNKNOWN"
    elif location == "box":
        route["box_ids"][0] = "UNKNOWN"
    elif location == "placement":
        route["placements"][0]["box_id"] = "UNKNOWN"
    elif location == "unload":
        route["unload_steps"][0]["box_id"] = "UNKNOWN"
    else:
        route["stops"][0]["store_id"] = "UNKNOWN"
    assert validate_solution(req, Result.model_validate(data))


def test_missing_stop_and_duplicate_unload_are_rejected():
    req, data = _base()
    missing = copy.deepcopy(data)
    missing["routes"][0]["stops"].pop()
    assert validate_solution(req, Result.model_validate(missing))
    duplicate = copy.deepcopy(data)
    route = duplicate["routes"][0]
    route["unload_steps"][1]["box_id"] = route["unload_steps"][0]["box_id"]
    assert validate_solution(req, Result.model_validate(duplicate))
