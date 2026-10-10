"""B09 配载启发式测试（ACCEPTANCE C02/C04/C05 + ALGORITHMS A6）。"""

import json
from pathlib import Path

from backend.models import SolveRequest
from backend.packing import pack_route
from backend.validation import validate_vehicle_candidate


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _make_request(box_length, box_width, allow_rotate=True, height=500):
    return SolveRequest.model_validate({
        "schema_version": "0.1",
        "case_id": "test-pack",
        "data_source": "synthetic",
        "depot": {"id": "DEPOT", "x_km": 0, "y_km": 0, "departure_min": 480},
        "stores": [{"id": "S01", "x_km": 3, "y_km": 4,
                    "window_start_min": 0, "window_end_min": 1440,
                    "service_min": 5}],
        "vehicles": [{"id": "V01", "length_mm": 2000, "width_mm": 1000,
                      "height_mm": 2000, "max_weight_kg": 500,
                      "fixed_cost": 100, "cost_per_km": 2}],
        "boxes": [{"id": "B01", "store_id": "S01", "length_mm": box_length,
                   "width_mm": box_width, "height_mm": height, "weight_kg": 10,
                   "fragile": False, "allow_rotate_xy": allow_rotate}],
        "options": {"method": "coupled", "seed": 42, "time_limit_ms": 10000,
                    "max_iterations": 200, "speed_kmph": 30},
    })


# --------------------------------------------------------------------------
# C02 单件尺寸
# --------------------------------------------------------------------------

def test_box_too_large():
    req = _load_case("c02")  # 箱 2100x500x500，车 2000x1000x2000
    result = pack_route(req, "V01", ["S01"])
    assert result.success is False
    assert result.reason_code == "BOX_TOO_LARGE"


def test_box_fits_1900():
    req = _make_request(1900, 500)
    result = pack_route(req, "V01", ["S01"])
    assert result.success is True
    assert len(result.placements) == 1


def test_rotation_allows_fit():
    # 800x1900：0 度宽 1900 超限，90 度长 1900<=2000、宽 800<=1000 可放
    req = _make_request(800, 1900, allow_rotate=True)
    result = pack_route(req, "V01", ["S01"])
    assert result.success is True
    assert result.placements[0].rotation_xy == 90


def test_rotation_forbidden_fails():
    # 同尺寸但禁止旋转：0 度宽 1900 超限 → BOX_TOO_LARGE
    req = _make_request(800, 1900, allow_rotate=False)
    result = pack_route(req, "V01", ["S01"])
    assert result.success is False
    assert result.reason_code == "BOX_TOO_LARGE"


# --------------------------------------------------------------------------
# 堆叠与独立校验
# --------------------------------------------------------------------------

def test_c01_two_boxes_stack_and_validate():
    req = _load_case("c01")  # 两箱 1000^3，B01 非易碎、B02 易碎
    result = pack_route(req, "V01", ["S01"])
    assert result.success is True
    assert len(result.placements) == 2
    # 独立校验无违规
    violations = validate_vehicle_candidate(
        req, "V01", ["S01"], result.placements, result.unload_steps)
    assert violations == []


def test_pack_result_independent_validation():
    req = _make_request(1000, 1000, height=1000)
    # 加第二箱做堆叠
    data = json.loads(Path("data/cases/c01.json").read_text(encoding="utf-8"))
    req2 = SolveRequest.model_validate(data)
    result = pack_route(req2, "V01", ["S01"])
    assert result.success is True
    violations = validate_vehicle_candidate(
        req2, "V01", ["S01"], result.placements, result.unload_steps)
    assert violations == []


def test_candidate_attempts_recorded():
    req = _load_case("c01")
    result = pack_route(req, "V01", ["S01"])
    assert result.success is True
    assert result.candidate_attempts > 0
