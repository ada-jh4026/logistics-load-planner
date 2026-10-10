"""B13: 内存任务存储与单工作线程串行执行。

- 任务队列上限 MAX_QUEUE（默认 8）；
- 单工作线程串行执行 solve，避免耗时求解阻塞 FastAPI 事件循环；
- 状态流转 queued → running → succeeded/partial/failed；
- 内存存储，重启即丢（CONTRACT 约定，不声称生产高可用）。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.models import Result, SolveRequest
from backend.solver import solve

MAX_QUEUE = 8


@dataclass
class Job:
    run_id: str
    request: SolveRequest
    status: str = "queued"
    result: Optional[Result] = None
    error: Optional[dict] = None
    termination_reason: Optional[str] = None
    elapsed_ms: float = 0.0
    created_at: float = field(default_factory=time.monotonic)


class JobManager:
    def __init__(self, max_queue: int = MAX_QUEUE):
        self._jobs: dict[str, Job] = {}
        self._queue: list[Job] = []
        self._lock = threading.Lock()
        self._max_queue = max_queue
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def submit(self, request: SolveRequest) -> Optional[Job]:
        with self._lock:
            if len(self._queue) >= self._max_queue:
                return None
            job = Job(run_id=uuid.uuid4().hex, request=request)
            self._jobs[job.run_id] = job
            self._queue.append(job)
            return job

    def get(self, run_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(run_id)

    def _worker_loop(self) -> None:
        while True:
            with self._lock:
                job = self._queue.pop(0) if self._queue else None
                if job is not None:
                    job.status = "running"
            if job is None:
                time.sleep(0.01)
                continue
            self._execute(job)

    def _execute(self, job: Job) -> None:
        start = time.monotonic()
        try:
            result = solve(job.request)
            job.result = result
            job.elapsed_ms = (time.monotonic() - start) * 1000.0
            job.termination_reason = "completed"
            m = result.metrics
            if result.validation.valid and m.served_stores == m.total_stores:
                job.status = "succeeded"
            else:
                job.status = "partial"
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.termination_reason = "internal_error"
            job.error = {"code": "INTERNAL_ERROR", "message": str(exc)}
            job.elapsed_ms = (time.monotonic() - start) * 1000.0
