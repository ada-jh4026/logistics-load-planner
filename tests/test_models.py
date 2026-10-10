"""B02 模型与非法数据处理测试。

覆盖 CONTRACT.md 的输入校验与 ACCEPTANCE.md C08：样例可解析、重复 ID、
未知门店引用、负尺寸、NaN/Infinity、反向时间窗、不合法 options 等。
"""

import copy
import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.models import JobResponse, SolveRequest

EXAMPLES = Path("docs/playbook/examples")


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def _valid() -> dict:
    return _load("request-success.json")


# --------------------------------------------------------------------------
# 样例解析
# --------------------------------------------------------------------------

def test_parse_request_success_example():
    req = SolveRequest.model_validate(_load("request-success.json"))
    assert req.case_id == "ui-success"
    assert req.schema_version == "0.1"
    assert req.data_source == "synthetic"
    assert len(req.boxes) == 2
    assert req.options.method == "coupled"


def test_parse_request_partial_example():
    req = SolveRequest.model_validate(_load("request-partial.json"))
    assert len(req.stores) == 2
    assert len(req.boxes) == 3
    assert {b.store_id for b in req.boxes} == {"S01", "S02"}


def test_parse_response_success_example():
    resp = JobResponse.model_validate(_load("response-success.json"))
    assert resp.status == "succeeded"
    assert resp.result is not None
    assert resp.result.validation.valid is True
    assert resp.error is None


def test_parse_response_partial_example():
    resp = JobResponse.model_validate(_load("response-partial.json"))
    assert resp.status == "partial"
    assert len(resp.result.unassigned) == 1
    assert resp.result.unassigned[0].reason_code == "BOX_TOO_LARGE"


def test_parse_response_failed_example():
    resp = JobResponse.model_validate(_load("response-failed.json"))
    assert resp.status == "failed"
    assert resp.result is None
    assert resp.error.code == "INTERNAL_ERROR"


# --------------------------------------------------------------------------
# 非法输入（C08）
# --------------------------------------------------------------------------

def test_duplicate_box_id_rejected():
    data = _valid()
    data["boxes"][1]["id"] = data["boxes"][0]["id"]  # 重复 B01
    with pytest.raises(ValidationError, match="重复 ID"):
        SolveRequest.model_validate(data)


def test_duplicate_store_id_rejected():
    data = _valid()
    data["stores"].append(copy.deepcopy(data["stores"][0]))
    with pytest.raises(ValidationError, match="重复 ID"):
        SolveRequest.model_validate(data)


def test_unknown_store_id_rejected():
    data = _valid()
    data["boxes"][0]["store_id"] = "S99"  # 不存在的门店
    with pytest.raises(ValidationError, match="未知 store_id"):
        SolveRequest.model_validate(data)


def test_negative_dimension_rejected():
    data = _valid()
    data["boxes"][0]["length_mm"] = -1000
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_zero_dimension_rejected():
    data = _valid()
    data["boxes"][0]["height_mm"] = 0
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_nan_coordinate_rejected():
    data = _valid()
    data["stores"][0]["x_km"] = float("nan")
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_infinity_weight_rejected():
    data = _valid()
    data["boxes"][0]["weight_kg"] = float("inf")
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_reversed_time_window_rejected():
    data = _valid()
    data["stores"][0]["window_start_min"] = 600
    data["stores"][0]["window_end_min"] = 500  # 颠倒
    with pytest.raises(ValidationError, match="时间窗颠倒"):
        SolveRequest.model_validate(data)


def test_invalid_method_rejected():
    data = _valid()
    data["options"]["method"] = "magic"
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_time_limit_out_of_range_rejected():
    data = _valid()
    data["options"]["time_limit_ms"] = 50  # 低于 100
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_max_iterations_out_of_range_rejected():
    data = _valid()
    data["options"]["max_iterations"] = 0  # 低于 1
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_store_without_box_rejected():
    data = _valid()
    # 给 partial 样例的 S02 门店，但只保留 S01 的箱，制造无箱门店
    data["stores"].append(
        {"id": "S02", "x_km": 6, "y_km": 8,
         "window_start_min": 480, "window_end_min": 700, "service_min": 5}
    )
    with pytest.raises(ValidationError, match="没有任何箱件"):
        SolveRequest.model_validate(data)


def test_empty_stores_rejected():
    data = _valid()
    data["stores"] = []
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_empty_vehicles_rejected():
    data = _valid()
    data["vehicles"] = []
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_empty_boxes_rejected():
    data = _valid()
    data["boxes"] = []
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


def test_wrong_schema_version_rejected():
    data = _valid()
    data["schema_version"] = "0.2"
    with pytest.raises(ValidationError):
        SolveRequest.model_validate(data)


# --------------------------------------------------------------------------
# 有效边界（不误拒绝）
# --------------------------------------------------------------------------

def test_zero_coordinate_and_cost_accepted():
    data = _valid()
    data["depot"]["x_km"] = 0
    data["depot"]["y_km"] = 0
    data["vehicles"][0]["fixed_cost"] = 0
    data["vehicles"][0]["cost_per_km"] = 0
    req = SolveRequest.model_validate(data)
    assert req.vehicles[0].fixed_cost == 0


def test_default_options_accepted():
    data = _valid()
    del data["options"]  # 使用协议默认值
    req = SolveRequest.model_validate(data)
    assert req.options.method == "coupled"
    assert req.options.seed == 42
    assert req.options.time_limit_ms == 10000
    assert req.options.max_iterations == 200
    assert req.options.speed_kmph == 30


def test_finite_float_ok():
    # 确认 math 不参与，仅确认正常浮点可通过
    data = _valid()
    data["boxes"][0]["weight_kg"] = 0.5
    req = SolveRequest.model_validate(data)
    assert req.boxes[0].weight_kg == 0.5
