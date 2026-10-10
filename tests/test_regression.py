"""B16 回归与生成数据复核。

把 B03 生成的「已知可行见证」（data/witnesses/*.witness.json）送入独立校验器，
验证见证的布局 + 卸货序列确实可行，从而坐实「已知可行」标签。
"""

import json
from pathlib import Path

import pytest

from backend.models import Placement, SolveRequest, UnloadStep
from backend.validation import validate_vehicle_candidate

WITNESS_DIR = Path("data/witnesses")


def _load_request(case_id: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{case_id}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _witness_files():
    return sorted(WITNESS_DIR.glob("*.witness.json"))


def test_witnesses_exist():
    files = _witness_files()
    assert len(files) == 7  # small/standard 各 3 + stress 1


@pytest.mark.parametrize("witness_path", _witness_files())
def test_witness_layout_feasible(witness_path):
    witness = json.loads(witness_path.read_text(encoding="utf-8"))
    case_id = witness["case_id"]
    request = _load_request(case_id)

    assert witness["kind"] == "witness"
    assert witness["routes"], f"{case_id} 见证无路线"

    for route in witness["routes"]:
        placements = [Placement(**p) for p in route["placements"]]
        unload_steps = [UnloadStep(**s) for s in route["unload_steps"]]
        violations = validate_vehicle_candidate(
            request, route["vehicle_id"], route["store_ids"],
            placements, unload_steps)
        assert violations == [], (
            f"{case_id} 车辆 {route['vehicle_id']} 见证不可行："
            f"{[v.code for v in violations]}")
