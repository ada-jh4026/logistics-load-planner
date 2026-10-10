"""B15 基准测试（EVALUATION 口径 + 不可比保护）。"""

from pathlib import Path

import pytest

from scripts.benchmark import cost_improvement, run_benchmark


def test_run_benchmark_small():
    out = Path("artifacts/benchmarks/test_tmp")
    summary = run_benchmark("small", out)
    # small 3 seed × 3 method = 9 runs
    assert summary["total_runs"] == 9
    assert (out / "runs.json").is_file()
    assert (out / "summary.json").is_file()


def test_cost_improvement_comparable():
    baseline = {"valid": True, "metrics": {"served_stores": 5, "total_cost": 100.0}}
    candidate = {"valid": True, "metrics": {"served_stores": 5, "total_cost": 80.0}}
    imp, reason = cost_improvement(baseline, candidate)
    assert imp == pytest.approx(0.2)
    assert reason is None


def test_cost_improvement_incomparable_store_set():
    baseline = {"valid": True, "metrics": {"served_stores": 5, "total_cost": 100.0}}
    candidate = {"valid": True, "metrics": {"served_stores": 4, "total_cost": 80.0}}
    imp, reason = cost_improvement(baseline, candidate)
    assert imp is None
    assert "门店" in reason


def test_cost_improvement_incomparable_zero_cost():
    baseline = {"valid": True, "metrics": {"served_stores": 5, "total_cost": 0.0}}
    candidate = {"valid": True, "metrics": {"served_stores": 5, "total_cost": 80.0}}
    imp, reason = cost_improvement(baseline, candidate)
    assert imp is None


def test_cost_improvement_incomparable_invalid():
    baseline = {"valid": False, "metrics": {"served_stores": 5, "total_cost": 100.0}}
    candidate = {"valid": True, "metrics": {"served_stores": 5, "total_cost": 80.0}}
    imp, reason = cost_improvement(baseline, candidate)
    assert imp is None
    assert "验证" in reason
