"""B11 预算测试（ALGORITHMS A8 + ACCEPTANCE C11）。"""

import json
from pathlib import Path

from backend.baselines import solve_greedy
from backend.budget import Budget
from backend.budget import BudgetSlice
from backend.models import SolveRequest


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _fake_clock(state):
    def clock():
        return state[0]
    return clock


def test_budget_not_expired():
    b = Budget(time_limit_ms=10000, max_iterations=1000)
    assert b.expired() is False
    assert b.termination_reason() == "completed"


def test_budget_time_expired_with_fake_clock():
    state = [0.0]
    b = Budget(time_limit_ms=1000, max_iterations=100000,
               clock=_fake_clock(state))
    assert b.expired() is False
    state[0] = 5.0  # 超过 deadline（1000ms * 0.9 = 0.9s）
    assert b.time_expired() is True
    assert b.expired() is True
    assert b.termination_reason() == "time_limit"


def test_budget_iteration_expired():
    b = Budget(time_limit_ms=100000, max_iterations=5)
    for _ in range(5):
        b.tick()
    assert b.iteration_expired() is True
    assert b.expired() is True
    assert b.termination_reason() == "iteration_limit"


def test_budget_elapsed_ms():
    state = [10.0]
    b = Budget(time_limit_ms=1000, max_iterations=1000,
               clock=_fake_clock(state))
    state[0] = 10.5
    assert b.elapsed_ms == 500.0


def test_budget_reserve_ratio():
    state = [0.0]
    b = Budget(time_limit_ms=1000, max_iterations=100000,
               clock=_fake_clock(state), reserve_ratio=0.1)
    # deadline = 0 + 1.0s * 0.9 = 0.9s
    assert b.deadline == 0.9


def test_baseline_terminates_on_time_budget():
    req = _load_case("small-11")
    state = [0.0]
    b = Budget(time_limit_ms=1000, max_iterations=100000,
               clock=_fake_clock(state))
    state[0] = 10.0  # 创建后推进到超过 deadline（0.9s）
    result = solve_greedy(req, budget=b)
    # 不无限循环，返回结果（路线构造阶段因超时全部 unassigned）
    assert result is not None
    assert result.metrics.served_stores == 0


def test_baseline_terminates_on_iteration_budget():
    req = _load_case("small-11")
    b = Budget(time_limit_ms=100000, max_iterations=2)
    result = solve_greedy(req, budget=b)
    assert result is not None


def test_same_seed_enough_budget_stable():
    req = _load_case("small-11")
    r1 = solve_greedy(req)
    r2 = solve_greedy(req)
    assert r1.metrics.total_cost == r2.metrics.total_cost
    assert r1.metrics.served_stores == r2.metrics.served_stores


def test_search_slice_charges_parent_and_leaves_recovery_budget():
    clock = [0.0]
    parent = Budget(10000, 100, clock=lambda: clock[0])
    phase = BudgetSlice(parent, 1000, 2)
    phase.tick()
    phase.tick()
    assert phase.expired()
    assert parent.iterations == 2
    assert not parent.expired()
    timed = BudgetSlice(parent, 1000, 50)
    clock[0] = 1.1
    assert timed.expired()
    assert not parent.expired()
