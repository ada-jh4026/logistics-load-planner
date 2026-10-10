"""CONTRACT v0.1 的 pydantic 镜像（SolveRequest / JobResponse）与 AGENT_CONTRACT 的请求响应模型。

字段名、单位、枚举与 docs/playbook/CONTRACT.md 完全一致；这里不做求解器那样严格的业务校验，
只保证结构正确，便于事实表推导。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- SolveRequest ----------
class Depot(_Model):
    id: str
    x_km: float
    y_km: float
    departure_min: float


class Store(_Model):
    id: str
    x_km: float
    y_km: float
    window_start_min: float
    window_end_min: float
    service_min: float


class Vehicle(_Model):
    id: str
    length_mm: float
    width_mm: float
    height_mm: float
    max_weight_kg: float
    fixed_cost: float
    cost_per_km: float


class Box(_Model):
    id: str
    store_id: str
    length_mm: float
    width_mm: float
    height_mm: float
    weight_kg: float
    fragile: bool
    allow_rotate_xy: bool


Method = Literal["greedy", "sequential", "coupled"]


class Options(_Model):
    method: Method
    seed: int
    time_limit_ms: int
    max_iterations: int
    speed_kmph: float


class SolveRequest(_Model):
    schema_version: Literal["0.1"]
    case_id: str = Field(min_length=1)
    data_source: str
    depot: Depot
    stores: list[Store] = Field(min_length=1)
    vehicles: list[Vehicle] = Field(min_length=1)
    boxes: list[Box] = Field(min_length=1)
    options: Options


# ---------- JobResponse ----------
class Stop(_Model):
    store_id: str
    arrival_min: float
    service_start_min: float
    departure_min: float


class Placement(_Model):
    box_id: str
    x_mm: float
    y_mm: float
    z_mm: float
    rotation_xy: Literal[0, 90]


class UnloadStep(_Model):
    step: int
    store_id: str
    box_id: str


class Route(_Model):
    vehicle_id: str
    store_ids: list[str]
    stops: list[Stop]
    return_min: float
    distance_km: float
    cost: float
    box_ids: list[str]
    placements: list[Placement]
    unload_steps: list[UnloadStep]


ReasonCode = Literal["BOX_TOO_LARGE", "CAPACITY_LIMIT", "TIME_WINDOW", "SEARCH_EXHAUSTED", "TIME_LIMIT"]


class Unassigned(_Model):
    store_id: str
    box_ids: list[str]
    reason_code: ReasonCode
    message: str


class Violation(_Model):
    code: str
    vehicle_id: str | None
    box_ids: list[str]
    store_id: str | None
    message: str


class Validation(_Model):
    valid: bool
    violations: list[Violation]


class Metrics(_Model):
    total_stores: int
    served_stores: int
    total_boxes: int
    served_boxes: int
    completion_rate: float
    used_vehicles: int
    total_distance_km: float
    total_cost: float
    on_time_rate: float | None
    volume_utilization: float | None
    weight_utilization: float | None
    unload_block_count: int


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="allow")
    iteration: int
    action: str
    reason_code: str | None = None
    message: str


RepairAction = Literal["pack_failed", "relocate"]
RepairOutcome = Literal["detected", "rejected", "accepted"]
RepairStatus = Literal["not_needed", "repaired", "partially_repaired", "unresolved", "budget_exhausted"]


class RepairEvent(_Model):
    """CONTRACT v0.1 RepairEvent：只有 accepted 事件带 before/after 已验证快照。"""

    event_id: int = Field(ge=1)
    iteration: int = Field(ge=0)
    action: RepairAction
    outcome: RepairOutcome
    store_ids: list[str]
    box_ids: list[str]
    source_vehicle_id: str | None
    target_vehicle_id: str | None
    reason_code: str | None
    message: str
    metrics_before: Metrics | None = None
    metrics_after: Metrics | None = None
    routes_before: list[Route] | None = None
    routes_after: list[Route] | None = None


class RepairTrace(_Model):
    """CONTRACT v0.1 RepairTrace v1。缺失（旧响应）与 null 都表示「未提供记录」，与 not_needed 不同。"""

    version: Literal[1] = 1
    status: RepairStatus
    initial_metrics: Metrics
    final_metrics: Metrics
    initial_routes: list[Route]
    attempted_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    events: list[RepairEvent]
    truncated: bool
    omitted_count: int = Field(ge=0)


class Result(_Model):
    routes: list[Route]
    unassigned: list[Unassigned]
    validation: Validation
    metrics: Metrics
    diagnostics: list[Diagnostic]
    repair_trace: RepairTrace | None = None


JobStatus = Literal["queued", "running", "succeeded", "partial", "failed"]
Termination = Literal["completed", "time_limit", "iteration_limit", "internal_error"]


class JobError(_Model):
    code: str
    message: str


class JobResponse(_Model):
    schema_version: Literal["0.1"]
    run_id: str
    case_id: str
    status: JobStatus
    data_source: str
    is_mock: bool
    method: Method
    termination_reason: Termination | None
    elapsed_ms: float
    result: Result | None
    error: JobError | None


# ---------- Agent API ----------
Mode = Literal["llm", "template"]
Focus = Literal["overview", "unassigned", "unload", "vehicle"]


class ExplainRequest(_Model):
    schema_version: Literal["0.1"]
    request: SolveRequest
    response: JobResponse
    focus: Focus = "overview"
    vehicle_id: str | None = None
    question: str | None = None


class Grounding(_Model):
    checked_numbers: int
    unmatched_numbers: list[str]
    passed: bool


class ExplainResponse(_Model):
    schema_version: Literal["0.1"] = "0.1"
    mode: Mode
    model: str | None
    warnings: list[str]
    text: str
    facts: dict[str, Any]
    grounding: Grounding


class HealthResponse(_Model):
    status: Literal["ok"] = "ok"
    schema_version: Literal["0.1"] = "0.1"
    llm: dict[str, Any]


class ErrorDetail(_Model):
    path: str
    message: str


class ErrorBody(_Model):
    code: str
    message: str
    details: list[ErrorDetail]


class ErrorEnvelope(_Model):
    schema_version: Literal["0.1"] = "0.1"
    error: ErrorBody


# ---------- interpret ----------
Action = Literal["set", "remove_vehicle", "add_vehicle"]
Target = Literal["store", "box", "vehicle", "depot", "options"]


class IntentOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Action
    target: Target | None = None
    id: str | None = None
    field: str | None = None
    value: Any = None

    @model_validator(mode="after")
    def _infer_target(self) -> "IntentOp":
        if self.action in ("remove_vehicle", "add_vehicle"):
            self.target = "vehicle"
        elif self.target is None:
            raise ValueError("set 操作必须给出 target")
        return self


class RejectedOp(_Model):
    intent: IntentOp
    reason: str


class PatchOp(_Model):
    op: Literal["replace", "remove", "add"]
    path: str
    value: Any = None


class InterpretRequest(_Model):
    schema_version: Literal["0.1"]
    request: SolveRequest
    instruction: str = Field(min_length=1, max_length=2000)


class InterpretResponse(_Model):
    schema_version: Literal["0.1"] = "0.1"
    mode: Mode
    model: str | None
    warnings: list[str]
    understood: bool
    intent_ops: list[IntentOp]
    patch: list[PatchOp]
    patched_request: SolveRequest | None
    rejected_ops: list[RejectedOp]
    summary: str


# ---------- compare ----------
class RunPair(_Model):
    request: SolveRequest
    response: JobResponse


class CompareRequest(_Model):
    schema_version: Literal["0.1"]
    baseline: RunPair
    candidate: RunPair
    instruction: str | None = None


class MetricDelta(_Model):
    baseline: float | None
    candidate: float | None
    delta: float | None


class CompareResponse(_Model):
    schema_version: Literal["0.1"] = "0.1"
    mode: Mode
    model: str | None
    warnings: list[str]
    deltas: dict[str, MetricDelta]
    same_served_set: bool
    both_valid: bool
    comparable_cost: bool
    cost_change_rate: float | None
    text: str
    grounding: Grounding

