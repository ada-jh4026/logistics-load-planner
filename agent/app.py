"""调度助手智能体服务（FastAPI）。接口见 docs/playbook/AGENT_CONTRACT.md。

启动：.venv\\Scripts\\python.exe -m uvicorn agent.app:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .compare import compare
from .config import load_settings
from .explain import explain
from .interpret import interpret
from .llm import build_llm
from .schemas import (
    CompareRequest,
    CompareResponse,
    ErrorBody,
    ErrorDetail,
    ErrorEnvelope,
    ExplainRequest,
    ExplainResponse,
    HealthResponse,
    InterpretRequest,
    InterpretResponse,
)

log = logging.getLogger("agent")

settings = load_settings()
llm = build_llm(settings)

app = FastAPI(title="调度助手智能体服务", version="0.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _error(status: int, code: str, message: str, details: list[ErrorDetail] | None = None) -> JSONResponse:
    body = ErrorEnvelope(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def _on_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [ErrorDetail(path=".".join(str(p) for p in e.get("loc", ())), message=str(e.get("msg", ""))) for e in exc.errors()]
    return _error(422, "INVALID_INPUT", "请求不符合协议 v0.1。", details)


@app.exception_handler(Exception)
async def _on_error(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error")
    return _error(500, "INTERNAL_ERROR", "服务内部错误，详情见服务日志。")


@app.get("/agent/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        llm={
            "provider": settings.provider if settings.configured else None,
            "model": settings.model if settings.configured else None,
            "configured": settings.configured,
        }
    )


@app.post("/agent/explain", response_model=ExplainResponse)
def post_explain(body: ExplainRequest) -> ExplainResponse | JSONResponse:
    if body.response.status not in ("succeeded", "partial") or body.response.result is None:
        return _error(
            422,
            "INVALID_INPUT",
            "只能解释 succeeded 或 partial 状态且带 result 的响应。",
            [ErrorDetail(path="response.status", message=f"当前为 {body.response.status}")],
        )
    if body.focus == "vehicle" and not body.vehicle_id:
        return _error(422, "INVALID_INPUT", "focus=vehicle 时必须提供 vehicle_id。", [ErrorDetail(path="vehicle_id", message="缺失")])
    return explain(body, llm)


@app.post("/agent/interpret", response_model=InterpretResponse)
def post_interpret(body: InterpretRequest) -> InterpretResponse:
    return interpret(body, llm)


@app.post("/agent/compare", response_model=CompareResponse)
def post_compare(body: CompareRequest) -> CompareResponse | JSONResponse:
    for name, pair in (("baseline", body.baseline), ("candidate", body.candidate)):
        if pair.response.status not in ("succeeded", "partial") or pair.response.result is None:
            return _error(
                422,
                "INVALID_INPUT",
                f"{name} 必须是 succeeded 或 partial 状态且带 result。",
                [ErrorDetail(path=f"{name}.response.status", message=f"当前为 {pair.response.status}")],
            )
    return compare(body, llm)
