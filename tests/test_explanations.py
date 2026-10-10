"""B14 解释测试。"""

import json
from pathlib import Path

from backend.explanations import generate_explanation, loading_guide
from backend.models import SolveRequest
from backend.solver import solve


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def test_explanation_matches_metrics():
    req = _load_case("c01")
    result = solve(req)
    text = generate_explanation(req, result)
    assert "1/1 家门店" in text
    assert "2/2 箱" in text
    assert "120.00 元" in text


def test_explanation_unassigned_reason():
    req = _load_case("c02")
    result = solve(req)
    text = generate_explanation(req, result)
    assert "未配送 S01" in text
    assert "BOX_TOO_LARGE" in text


def test_no_fake_savings():
    req = _load_case("c01")
    result = solve(req)
    text = generate_explanation(req, result)
    assert "节省" not in text
    assert "降本" not in text


def test_no_fake_repair_claim():
    req = _load_case("c01")
    result = solve(req)
    text = generate_explanation(req, result)
    assert "修复" not in text


def test_loading_guide_reverse_order():
    req = _load_case("c01")
    result = solve(req)
    route = result.routes[0]
    guide = loading_guide(route)
    # 装货 = 卸货逆序
    assert "装货顺序" in guide
    assert guide.count("→") == len(route.unload_steps) - 1


def test_explanation_deterministic():
    req = _load_case("c01")
    r1 = solve(req)
    r2 = solve(req)
    assert generate_explanation(req, r1) == generate_explanation(req, r2)
