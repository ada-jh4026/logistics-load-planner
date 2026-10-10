"""B11: 统一预算与确定性控制。

遵循 ALGORITHMS.md A8：
- 单调时钟（time.monotonic，可注入便于测试）；
- 截止时刻 = 起点 + time_limit_ms*(1-reserve_ratio)，为最终校验预留约 10%；
- 迭代计数与时间双重上限，expired() 任一到即终止；
- termination_reason 区分 time_limit / iteration_limit / completed。
"""

from __future__ import annotations

import time
from typing import Callable

Clock = Callable[[], float]


class Budget:
    def __init__(self, time_limit_ms: int, max_iterations: int,
                 clock: Clock | None = None, reserve_ratio: float = 0.1):
        self._time_limit_ms = float(time_limit_ms)
        self._max_iterations = int(max_iterations)
        self._clock = clock if clock is not None else time.monotonic
        self._reserve_ratio = reserve_ratio
        self._start = self._clock()
        self._deadline = self._start + (self._time_limit_ms / 1000.0) * (1.0 - reserve_ratio)
        self._iterations = 0

    @property
    def time_limit_ms(self) -> float:
        return self._time_limit_ms

    @property
    def max_iterations(self) -> int:
        return self._max_iterations

    @property
    def iterations(self) -> int:
        return self._iterations

    @property
    def start(self) -> float:
        return self._start

    @property
    def deadline(self) -> float:
        return self._deadline

    def tick(self) -> None:
        self._iterations += 1

    def time_expired(self) -> bool:
        return self._clock() >= self._deadline

    def iteration_expired(self) -> bool:
        return self._iterations >= self._max_iterations

    def expired(self) -> bool:
        return self.time_expired() or self.iteration_expired()

    @property
    def elapsed_ms(self) -> float:
        return (self._clock() - self._start) * 1000.0

    def termination_reason(self) -> str:
        if self.time_expired():
            return "time_limit"
        if self.iteration_expired():
            return "iteration_limit"
        return "completed"


class BudgetSlice:
    """Bound a search phase while charging all work to its parent budget."""

    def __init__(self, parent: Budget, max_elapsed_ms: float, max_iterations: int):
        self.parent = parent
        self._deadline_elapsed = parent.elapsed_ms + max_elapsed_ms
        self._iteration_end = parent.iterations + max_iterations

    @property
    def iterations(self) -> int:
        return self.parent.iterations

    def tick(self) -> None:
        self.parent.tick()

    def expired(self) -> bool:
        return (self.parent.expired()
                or self.parent.elapsed_ms >= self._deadline_elapsed
                or self.parent.iterations >= self._iteration_end)
