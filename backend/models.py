"""B02: 输入输出模型与非法数据处理。

遵循 docs/playbook/CONTRACT.md v0.1。所有模型基于 pydantic v2；字段级
约束（正尺寸、有限数、时间范围、options 范围）由 Field 与 validator 落实，
跨字段约束（重复 ID、未知门店引用、每店至少一箱）由 model_validator 落实。

本模块只负责解析与拒绝非法输入；HTTP 422 的错误外壳（{schema_version,
error:{code:"INVALID_INPUT", message, details}}）由 B13 的 API 层组装。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1"

Method = Literal["greedy", "sequential", "coupled"]
JobStatus = Literal["queued", "running", "succeeded", "partial", "failed"]
TerminationReason = Literal["completed", "time_limit", "iteration_limit", "internal_error"]


# --------------------------------------------------------------------------
# 输入模型（SolveRequest）
# --------------------------------------------------------------------------

class Depot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    x_km: float = Field(allow_inf_nan=False)
    y_km: float = Field(allow_inf_nan=False)
    departure_min: float = Field(ge=0, le=1440, allow_inf_nan=False)


class Store(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    x_km: float = Field(allow_inf_nan=False)
    y_km: float = Field(allow_inf_nan=False)
    window_start_min: float = Field(ge=0, le=1440, allow_inf_nan=False)
    window_end_min: float = Field(ge=0, le=1440, allow_inf_nan=False)
    service_min: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _window_order(self) -> "Store":
        if self.window_start_min > self.window_end_min:
            raise ValueError(
                f"时间窗颠倒：window_start_min={self.window_start_min} "
                f"大于 window_end_min={self.window_end_min}"
            )
        return self


class Vehicle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    length_mm: int = Field(gt=0)
    width_mm: int = Field(gt=0)
    height_mm: int = Field(gt=0)
    max_weight_kg: float = Field(gt=0, allow_inf_nan=False)
    fixed_cost: float = Field(ge=0, allow_inf_nan=False)
    cost_per_km: float = Field(ge=0, allow_inf_nan=False)


class Box(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    length_mm: int = Field(gt=0)
    width_mm: int = Field(gt=0)
    height_mm: int = Field(gt=0)
    weight_kg: float = Field(gt=0, allow_inf_nan=False)
    fragile: bool
    allow_rotate_xy: bool


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: Method = "coupled"
    seed: int = 42
    time_limit_ms: int = Field(default=10000, ge=100, le=60000)
    max_iterations: int = Field(default=200, ge=1, le=10000)
    speed_kmph: float = Field(default=30, gt=0, allow_inf_nan=False)


class SolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"]
    case_id: str = Field(min_length=1)
    data_source: Literal["synthetic"]
    depot: Depot
    stores: list[Store] = Field(min_length=1)
    vehicles: list[Vehicle] = Field(min_length=1)
    boxes: list[Box] = Field(min_length=1)
    options: Options = Field(default_factory=Options)

    @model_validator(mode="after")
    def _cross_field(self) -> "SolveRequest":
        # 各类型内部 ID 唯一（含 depot）
        ids = {
            "depot": [self.depot.id],
            "stores": [s.id for s in self.stores],
            "vehicles": [v.id for v in self.vehicles],
            "boxes": [b.id for b in self.boxes],
        }
        for kind, values in ids.items():
            if len(values) != len(set(values)):
                raise ValueError(f"{kind} 中存在重复 ID")

        # 未知门店引用：不得静默修正
        store_ids = {s.id for s in self.stores}
        for box in self.boxes:
            if box.store_id not in store_ids:
                raise ValueError(
                    f"box {box.id} 引用了未知 store_id: {box.store_id}"
                )

        # 每个门店至少一箱
        boxed_store_ids = {b.store_id for b in self.boxes}
        unboxed = store_ids - boxed_store_ids
        if unboxed:
            raise ValueError(f"以下门店没有任何箱件：{sorted(unboxed)}")

        return self


# --------------------------------------------------------------------------
# 响应模型（JobResponse）
# --------------------------------------------------------------------------

class Stop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str
    arrival_min: float
    service_start_min: float
    departure_min: float


class Placement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    box_id: str
    x_mm: int
    y_mm: int
    z_mm: int
    rotation_xy: Literal[0, 90]


class UnloadStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int
    store_id: str
    box_id: str


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: str
    store_ids: list[str]
    stops: list[Stop]
    return_min: float
    distance_km: float
    cost: float
    box_ids: list[str]
    placements: list[Placement]
    unload_steps: list[UnloadStep]


class Unassigned(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: str
    box_ids: list[str]
    reason_code: str
    message: str


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    vehicle_id: Optional[str] = None
    box_ids: list[str] = Field(default_factory=list)
    store_id: Optional[str] = None
    message: str


class Validation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    violations: list[Violation] = Field(default_factory=list)


class Metrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_stores: int
    served_stores: int
    total_boxes: int
    served_boxes: int
    completion_rate: float
    used_vehicles: int
    total_distance_km: float
    total_cost: float
    on_time_rate: Optional[float] = None
    volume_utilization: Optional[float] = None
    weight_utilization: Optional[float] = None
    unload_block_count: int


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    iteration: int
    action: str
    reason_code: str
    message: str


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routes: list[Route]
    unassigned: list[Unassigned]
    validation: Validation
    metrics: Metrics
    diagnostics: list[Diagnostic] = Field(default_factory=list)


class ErrorInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"]
    run_id: str
    case_id: str
    status: JobStatus
    data_source: Literal["synthetic"]
    is_mock: bool
    method: Method
    termination_reason: Optional[TerminationReason] = None
    elapsed_ms: float = Field(ge=0)
    result: Optional[Result] = None
    error: Optional[ErrorInfo] = None
