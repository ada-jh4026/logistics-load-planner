"""自然语言指令 → 意图（按 ID）→ RFC 6902 补丁 → 协议校验。

模型（或规则解析器）只产出 IntentOp；下标解析、白名单、补丁生成与校验全部在这里，
保证模型写不出越权的修改。
"""
from __future__ import annotations

import copy
import json
import logging
from typing import Any

from .llm import LLM, NullLLM
from .rules import parse_rules
from .schemas import IntentOp, InterpretRequest, InterpretResponse, PatchOp, RejectedOp, SolveRequest, Vehicle
from .timeparse import hhmm, to_minutes

log = logging.getLogger("agent.interpret")

# 白名单：target → 允许 set 的字段及其类型/归一化
WHITELIST: dict[str, dict[str, str]] = {
    "depot": {"departure_min": "minutes"},
    "store": {"window_start_min": "minutes", "window_end_min": "minutes", "service_min": "number"},
    "box": {"fragile": "bool", "allow_rotate_xy": "bool"},
    "options": {"method": "method", "seed": "int", "time_limit_ms": "int", "max_iterations": "int", "speed_kmph": "number"},
}
FIELD_LABEL = {
    "departure_min": "仓库出发时间",
    "window_start_min": "最早收货时间",
    "window_end_min": "最晚收货时间",
    "service_min": "服务时长",
    "fragile": "易碎标记",
    "allow_rotate_xy": "允许水平旋转",
    "method": "求解方法",
    "seed": "随机种子",
    "time_limit_ms": "时间预算",
    "max_iterations": "最大迭代次数",
    "speed_kmph": "车速",
}

SYSTEM_PROMPT = """你是城市配送调度系统的指令解析器。把调度员的一句中文指令翻译成结构化操作列表，输出 JSON。
只允许这些操作：
- set：修改 depot.departure_min；stores[id].window_start_min / window_end_min / service_min；boxes[id].fragile / allow_rotate_xy；options.method / seed / time_limit_ms / max_iterations / speed_kmph。
- remove_vehicle：按 id 移除一辆车。
- add_vehicle：value 为完整车辆对象 {id,length_mm,width_mm,height_mm,max_weight_kg,fixed_cost,cost_per_km}。
规则：
1. 实体一律用 id 指代（如 S07、V02、B03），不要写数组下标，不要输出完整请求。
2. 时刻一律换算为当天零点起的分钟数（14:00 → 840，上午 9 点半 → 570）。时间预算单位毫秒（20 秒 → 20000）。
3. 调度员要求修改不在白名单里的字段（如箱件尺寸、车辆载重），也要如实输出该 set 操作，由系统拒绝并说明；不要替换成别的字段。
4. 指令里提到的 id 在实体清单里找不到，就不要为它生成操作，并在 summary 里说明。
5. 与调度无关或无法映射的内容：intent_ops 为空数组，summary 说明需要澄清。
输出格式：{"intent_ops":[{"action":"set","target":"store","id":"S07","field":"window_start_min","value":840}, ...], "summary":"一句话概述"}"""


def interpret(req: InterpretRequest, llm: LLM) -> InterpretResponse:
    warnings: list[str] = []
    ops: list[IntentOp] | None = None
    summary_hint = ""
    mode = "template"
    model = None

    if not isinstance(llm, NullLLM):
        try:
            raw = llm.complete(SYSTEM_PROMPT, _user_prompt(req), json_mode=True, temperature=0.0)
            ops, summary_hint = _parse_llm(raw)
            mode, model = "llm", llm.model
        except Exception as e:
            warnings.append(f"模型解析失败（{type(e).__name__}），使用规则模式。")
            log.warning("llm interpret failed: %s", e)
            ops = None
    else:
        warnings.append("未配置模型密钥，使用规则模式。")

    if ops is None:
        ops, rule_notes = parse_rules(req.instruction, req.request)
        warnings.extend(rule_notes)
        mode, model = "template", None

    patch, patched, rejected, accepted = apply_ops(req.request, ops)
    understood = bool(ops) and not _all_unknown_entities(ops, req.request)
    summary = _summary(accepted, rejected, understood, summary_hint, req.request)
    return InterpretResponse(
        mode=mode,
        model=model,
        warnings=warnings,
        understood=understood,
        intent_ops=ops,
        patch=patch,
        patched_request=patched,
        rejected_ops=rejected,
        summary=summary,
    )


# ---------- 补丁生成与校验 ----------
def apply_ops(request: SolveRequest, ops: list[IntentOp]) -> tuple[list[PatchOp], SolveRequest | None, list[RejectedOp], list[IntentOp]]:
    """逐个应用：每个 op 先在当前状态上解析下标，生成补丁并校验；失败进 rejected，其余继续。"""
    state: dict[str, Any] = request.model_dump()
    patch: list[PatchOp] = []
    rejected: list[RejectedOp] = []
    accepted: list[IntentOp] = []
    for op in ops:
        try:
            new_state, p = _apply_one(state, op)
            _validate(new_state)
        except ValueError as e:
            rejected.append(RejectedOp(intent=op, reason=str(e)))
            continue
        state = new_state
        patch.extend(p)
        accepted.append(op)
    patched = SolveRequest(**state) if accepted else SolveRequest(**request.model_dump())
    return patch, patched, rejected, accepted


def _index_of(items: list[dict[str, Any]], id_: str | None, what: str) -> int:
    if not id_:
        raise ValueError(f"缺少{what} ID")
    for i, it in enumerate(items):
        if it["id"] == id_:
            return i
    raise ValueError(f"{what} {id_} 不存在")


def _apply_one(state: dict[str, Any], op: IntentOp) -> tuple[dict[str, Any], list[PatchOp]]:
    s = copy.deepcopy(state)
    if op.action == "set":
        allowed = WHITELIST.get(op.target)
        if allowed is None:
            raise ValueError(f"目标 {op.target} 不支持 set")
        if op.field not in allowed:
            raise ValueError(f"字段 {op.field} 不在允许修改范围")
        if op.target in ("depot", "options"):
            value = _normalize(op.value, allowed[op.field], op.field)
            s[op.target][op.field] = value
            return s, [PatchOp(op="replace", path=f"/{op.target}/{op.field}", value=value)]
        coll = "stores" if op.target == "store" else "boxes"
        idx = _index_of(s[coll], op.id, "门店" if coll == "stores" else "箱件")
        value = _normalize(op.value, allowed[op.field], op.field)
        s[coll][idx][op.field] = value
        return s, [PatchOp(op="replace", path=f"/{coll}/{idx}/{op.field}", value=value)]
    if op.action == "remove_vehicle":
        idx = _index_of(s["vehicles"], op.id, "车辆")
        if len(s["vehicles"]) <= 1:
            raise ValueError("至少保留一辆车，不能移除最后一辆")
        del s["vehicles"][idx]
        return s, [PatchOp(op="remove", path=f"/vehicles/{idx}")]
    if op.action == "add_vehicle":
        if not isinstance(op.value, dict):
            raise ValueError("add_vehicle 需要完整车辆对象")
        try:
            v = Vehicle(**op.value)
        except Exception as e:
            raise ValueError(f"车辆对象不合法：{e.__class__.__name__}") from e
        if any(x["id"] == v.id for x in s["vehicles"]):
            raise ValueError(f"车辆 ID {v.id} 已存在")
        s["vehicles"].append(v.model_dump())
        return s, [PatchOp(op="add", path="/vehicles/-", value=v.model_dump())]
    raise ValueError(f"未知操作 {op.action}")


def _normalize(value: Any, kind: str, field: str) -> Any:
    if kind == "minutes":
        m = to_minutes(value)
        if m is None:
            raise ValueError(f"{FIELD_LABEL[field]} 的时刻无法解析：{value!r}")
        return m
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false", "是", "否"):
            return value.strip().lower() in ("true", "是")
        raise ValueError(f"{FIELD_LABEL[field]} 需要布尔值")
    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{FIELD_LABEL[field]} 需要整数")
        try:
            return int(float(value))
        except ValueError as e:
            raise ValueError(f"{FIELD_LABEL[field]} 需要整数") from e
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{FIELD_LABEL[field]} 需要数值")
        try:
            return float(value)
        except ValueError as e:
            raise ValueError(f"{FIELD_LABEL[field]} 需要数值") from e
    if kind == "method":
        if value in ("greedy", "sequential", "coupled"):
            return value
        raise ValueError(f"求解方法只能是 greedy / sequential / coupled，收到 {value!r}")
    raise ValueError(kind)


def _validate(state: dict[str, Any]) -> None:
    """协议模型 + CONTRACT 写明的范围/引用规则。失败抛 ValueError。"""
    try:
        r = SolveRequest(**state)
    except Exception as e:
        raise ValueError(f"不符合协议：{e.__class__.__name__}") from e
    if not r.vehicles:
        raise ValueError("至少保留一辆车")
    if not (0 <= r.depot.departure_min <= 1440):
        raise ValueError("仓库出发时间须在 0..1440 分钟内")
    for s in r.stores:
        if s.window_end_min < s.window_start_min:
            raise ValueError(f"门店 {s.id} 时间窗颠倒（{hhmm(s.window_start_min)} > {hhmm(s.window_end_min)}）")
        if s.window_start_min < 0 or s.window_end_min > 1440:
            raise ValueError(f"门店 {s.id} 时间窗须在 0..1440 分钟内")
        if s.service_min < 0:
            raise ValueError(f"门店 {s.id} 服务时长不能为负")
    ids = [v.id for v in r.vehicles]
    if len(ids) != len(set(ids)):
        raise ValueError("车辆 ID 重复")
    for v in r.vehicles:
        if min(v.length_mm, v.width_mm, v.height_mm, v.max_weight_kg) <= 0:
            raise ValueError(f"车辆 {v.id} 尺寸或载重必须为正")
        if v.fixed_cost < 0 or v.cost_per_km < 0:
            raise ValueError(f"车辆 {v.id} 费用不能为负")
    o = r.options
    if o.speed_kmph <= 0:
        raise ValueError("车速必须为正")
    if not (100 <= o.time_limit_ms <= 60000):
        raise ValueError("时间预算须在 100..60000 毫秒")
    if not (1 <= o.max_iterations <= 10000):
        raise ValueError("迭代次数须在 1..10000")


# ---------- 模型 I/O ----------
def _entity_summary(r: SolveRequest) -> dict[str, Any]:
    """发给模型的实体清单：只有 ID 与必要属性，不含坐标。"""
    return {
        "depot": {"departure_min": r.depot.departure_min},
        "stores": [{"id": s.id, "window_start_min": s.window_start_min, "window_end_min": s.window_end_min, "service_min": s.service_min} for s in r.stores],
        "vehicles": [{"id": v.id, "length_mm": v.length_mm, "width_mm": v.width_mm, "height_mm": v.height_mm, "max_weight_kg": v.max_weight_kg, "fixed_cost": v.fixed_cost, "cost_per_km": v.cost_per_km} for v in r.vehicles],
        "boxes": [{"id": b.id, "store_id": b.store_id, "fragile": b.fragile, "allow_rotate_xy": b.allow_rotate_xy} for b in r.boxes],
        "options": r.options.model_dump(),
    }


def _user_prompt(req: InterpretRequest) -> str:
    return "实体清单（JSON）：\n" + json.dumps(_entity_summary(req.request), ensure_ascii=False) + "\n\n调度员指令：" + req.instruction


def _parse_llm(raw: str) -> tuple[list[IntentOp], str]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("intent_ops"), list):
        raise ValueError("模型输出缺少 intent_ops 数组")
    ops = [IntentOp(**o) for o in data["intent_ops"]]
    return ops, str(data.get("summary") or "")


# ---------- 摘要 ----------
def _all_unknown_entities(ops: list[IntentOp], r: SolveRequest) -> bool:
    """所有操作都指向不存在的实体 → 视为未理解。"""
    known = {s.id for s in r.stores} | {v.id for v in r.vehicles} | {b.id for b in r.boxes}
    checks = [op.id in known for op in ops if op.id is not None and op.action != "add_vehicle"]
    return bool(checks) and not any(checks)


def _describe(op: IntentOp) -> str:
    if op.action == "remove_vehicle":
        return f"移除车辆 {op.id}"
    if op.action == "add_vehicle":
        vid = op.value.get("id") if isinstance(op.value, dict) else "?"
        return f"新增车辆 {vid}"
    label = FIELD_LABEL.get(op.field or "", op.field)
    who = {"depot": "仓库", "options": "求解选项"}.get(op.target, op.id)
    v = op.value
    if op.field in ("departure_min", "window_start_min", "window_end_min"):
        m = to_minutes(v)
        v = hhmm(m) if m is not None else v
    elif op.field == "time_limit_ms":
        try:
            v = f"{int(float(v)) / 1000:g} 秒"
        except (TypeError, ValueError):
            pass
    elif op.field == "service_min":
        v = f"{v} 分钟"
    elif op.field == "speed_kmph":
        v = f"{v} km/h"
    elif isinstance(v, bool):
        v = "是" if v else "否"
    return f"将 {who} 的{label}改为 {v}"


def _summary(accepted: list[IntentOp], rejected: list[RejectedOp], understood: bool, hint: str, r: SolveRequest) -> str:
    if not understood:
        return hint or "无法把这句指令对应到门店、车辆、箱件或求解选项，请换一种说法或指明 ID。"
    parts = [_describe(op) for op in accepted]
    if rejected:
        parts.append("未采纳：" + "；".join(f"{_describe(x.intent)}（{x.reason}）" for x in rejected))
    return "；".join(parts) + "。" if parts else (hint or "没有可执行的修改。")
