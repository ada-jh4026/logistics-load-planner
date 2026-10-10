from agent.facts import build_facts
from agent.schemas import JobResponse, SolveRequest


def test_facts_success(req_success, resp_success):
    f = build_facts(SolveRequest(**req_success), JobResponse(**resp_success))
    assert f["case"] == {"case_id": "ui-success", "store_count": 1, "box_count": 2, "vehicle_count": 1, "depot_departure_min": 480}
    assert f["run"]["status"] == "succeeded" and f["run"]["is_mock"] is True
    assert f["metrics"]["total_cost"] == 120 and f["metrics"]["volume_utilization"] == 0.5
    v = f["vehicles"][0]
    assert v["vehicle_id"] == "V01" and v["store_ids"] == ["S01"] and v["box_count"] == 2
    # 单车利用率按 request 独立重算：2 × 1e9 / 4e9 = 0.5；载重 150 / 500 = 0.3
    assert v["volume_utilization"] == 0.5 and v["weight_utilization"] == 0.3 and v["loaded_weight_kg"] == 150
    assert v["fragile_box_count"] == 1
    s = f["stops"][0]
    assert s["arrival_min"] == 490 and s["service_start_min"] == 500 and s["wait_min"] == 10 and s["slack_min"] == 100 and s["on_time"] is True
    assert f["unload"][0]["steps"][0] == {"step": 1, "store_id": "S01", "box_id": "B02", "fragile": True}
    assert f["unassigned"] == []


def test_facts_partial(req_partial, resp_partial):
    f = build_facts(SolveRequest(**req_partial), JobResponse(**resp_partial))
    assert f["metrics"]["served_stores"] == 1 and f["metrics"]["total_stores"] == 2
    assert f["unassigned"] == [
        {"store_id": "S02", "box_count": 1, "box_ids": ["B03"], "reason_code": "BOX_TOO_LARGE", "message": "箱件B03所有允许朝向均超过现有车厢尺寸。"}
    ]


def test_facts_failed_has_no_result(req_success, resp_failed):
    f = build_facts(SolveRequest(**req_success), JobResponse(**resp_failed))
    assert f["metrics"] is None and f["vehicles"] == [] and f["run"]["status"] == "failed"
