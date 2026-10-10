import copy

from agent.compare import compare
from agent.llm import FakeLLM, NullLLM
from agent.schemas import CompareRequest


def _pair(req, resp):
    return {"request": req, "response": resp}


def test_not_comparable_when_served_sets_differ(req_partial, resp_partial, req_success, resp_success):
    # 基线 partial（只服务 S01），候选用 success 的请求+响应但 case 不同也无妨；这里构造候选服务 S01+S02
    cand_req = copy.deepcopy(req_partial)
    cand_resp = copy.deepcopy(resp_partial)
    cand_resp["status"] = "succeeded"
    cand_resp["result"]["unassigned"] = []
    route = cand_resp["result"]["routes"][0]
    route["store_ids"] = ["S01", "S02"]
    route["stops"].append({"store_id": "S02", "arrival_min": 515, "service_start_min": 515, "departure_min": 520})
    route["box_ids"].append("B03")
    route["placements"].append({"box_id": "B03", "x_mm": 0, "y_mm": 0, "z_mm": 0, "rotation_xy": 0})
    route["unload_steps"].append({"step": 3, "store_id": "S02", "box_id": "B03"})
    m = cand_resp["result"]["metrics"]
    m.update(served_stores=2, served_boxes=3, completion_rate=1.0, total_cost=140, total_distance_km=20)
    r = compare(CompareRequest(schema_version="0.1", baseline=_pair(req_partial, resp_partial), candidate=_pair(cand_req, cand_resp)), NullLLM())
    assert r.mode == "template"
    assert r.same_served_set is False and r.comparable_cost is False and r.cost_change_rate is None
    assert r.deltas["served_stores"].delta == 1 and r.deltas["total_cost"].delta == 20
    assert "门店集合不同" in r.text and "%" not in r.text.split("门店集合不同")[1].split("\n")[0]
    assert "新增配送门店：S02" in r.text


def test_comparable_cost_change(req_success, resp_success):
    cand = copy.deepcopy(resp_success)
    cand["result"]["metrics"]["total_cost"] = 108
    cand["result"]["routes"][0]["cost"] = 108
    r = compare(CompareRequest(schema_version="0.1", baseline=_pair(req_success, resp_success), candidate=_pair(req_success, cand)), NullLLM())
    assert r.same_served_set and r.both_valid and r.comparable_cost
    assert abs(r.cost_change_rate - (-0.1)) < 1e-9
    assert "下降 10.0%" in r.text and r.grounding.passed


def test_invalid_candidate_not_comparable(req_success, resp_success):
    cand = copy.deepcopy(resp_success)
    cand["result"]["validation"] = {"valid": False, "violations": [{"code": "OVERLAP", "vehicle_id": "V01", "box_ids": ["B01", "B02"], "store_id": None, "message": "重叠"}]}
    r = compare(CompareRequest(schema_version="0.1", baseline=_pair(req_success, resp_success), candidate=_pair(req_success, cand)), NullLLM())
    assert r.both_valid is False and r.comparable_cost is False and "未通过独立校验" in r.text


def test_llm_percent_on_incomparable_is_rejected(req_partial, resp_partial, req_success, resp_success):
    # 基线服务 S01（partial），候选为 success 案例（只有 S01，但 case 不同：served 集合相同 {S01}）→ 可比；
    # 改成不可比：候选去掉 S01 服务 → 用 partial 响应把 route 清空
    cand = copy.deepcopy(resp_partial)
    cand["result"]["routes"] = []
    cand["result"]["unassigned"].append({"store_id": "S01", "box_ids": ["B01", "B02"], "reason_code": "TIME_LIMIT", "message": "预算用尽"})
    cand["result"]["metrics"].update(served_stores=0, served_boxes=0, completion_rate=0, used_vehicles=0, total_cost=0, total_distance_km=0, on_time_rate=None, volume_utilization=None, weight_utilization=None)
    llm = FakeLLM(["候选方案费用下降 100%，很好。", "候选方案不再配送 S01，两方案服务的门店集合不同，费用不可直接比较。"])
    r = compare(CompareRequest(schema_version="0.1", baseline=_pair(req_partial, resp_partial), candidate=_pair(req_partial, cand)), llm)
    assert r.mode == "llm" and r.comparable_cost is False
    assert any("重试后通过" in w for w in r.warnings)
    assert "不可直接比较" in r.text
