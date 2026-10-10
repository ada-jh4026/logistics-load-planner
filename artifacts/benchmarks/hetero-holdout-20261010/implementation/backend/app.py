"""FastAPI 应用：城市配送智能配载后端。

B13 提供的接口（CONTRACT.md）：
- GET  /api/health
- GET  /api/examples
- GET  /api/examples/{case_id}
- POST /api/solve
- GET  /api/jobs/{run_id}
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from backend.jobs import MAX_QUEUE, Job, JobManager
from backend.models import JobResponse, SolveRequest

SCHEMA_VERSION = "0.1"
CASES_DIR = Path("data/cases")

app = FastAPI(title="city-delivery-load-planner", version=SCHEMA_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = JobManager(max_queue=MAX_QUEUE)


def _valid_case_id(case_id: str) -> bool:
    """case_id 白名单：仅允许安全字符且文件确实存在，防路径穿越。"""
    if not case_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in case_id):
        return False
    return (CASES_DIR / f"{case_id}.json").is_file()


@app.exception_handler(RequestValidationError)
async def _validation_handler(request, exc: RequestValidationError):
    details = [
        {"path": ".".join(str(x) for x in err["loc"]), "message": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={
        "schema_version": SCHEMA_VERSION,
        "error": {"code": "INVALID_INPUT", "message": "输入非法", "details": details},
    })


def _job_response(job: Job) -> JobResponse:
    return JobResponse(
        schema_version=SCHEMA_VERSION,
        run_id=job.run_id,
        case_id=job.request.case_id,
        status=job.status,
        data_source="synthetic",
        is_mock=False,
        method=job.request.options.method,
        termination_reason=job.termination_reason,
        elapsed_ms=job.elapsed_ms,
        result=job.result,
        error=job.error,
    )


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={
        "schema_version": SCHEMA_VERSION,
        "error": {"code": code, "message": message, "details": []},
    })


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "schema_version": SCHEMA_VERSION}


@app.get("/api/examples")
def list_examples() -> list[dict]:
    """列举 data/cases 下实际存在的案例。"""
    items = []
    if CASES_DIR.is_dir():
        for p in sorted(CASES_DIR.glob("*.json")):
            case_id = p.stem
            items.append({"case_id": case_id, "label": case_id,
                          "description": "synthetic"})
    return items


@app.get("/api/examples/{case_id}")
def get_example(case_id: str):
    if not _valid_case_id(case_id):
        return _error_response(404, "NOT_FOUND", f"未知案例 {case_id}")
    data = json.loads((CASES_DIR / f"{case_id}.json").read_text(encoding="utf-8"))
    return data


@app.post("/api/solve", status_code=202)
def solve_endpoint(request: SolveRequest):
    job = jobs.submit(request)
    if job is None:
        return _error_response(429, "QUEUE_FULL",
                               f"任务队列已满（上限 {MAX_QUEUE}）")
    return {"schema_version": SCHEMA_VERSION, "run_id": job.run_id,
            "status": "queued"}


@app.get("/api/jobs/{run_id}")
def get_job(run_id: str):
    job = jobs.get(run_id)
    if job is None:
        return _error_response(404, "NOT_FOUND", f"未知任务 {run_id}")
    return _job_response(job)
