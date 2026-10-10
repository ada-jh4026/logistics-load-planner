"""规则解析器（模板模式）：覆盖调度员常见句式，输出 IntentOp。覆盖不到的返回空列表。"""
from __future__ import annotations

import re

from .schemas import IntentOp, SolveRequest
from .timeparse import cn_number, find_time

_SPLIT = re.compile(r"[，,；;。\n]|(?:\s*(?:同时|另外|并且|然后)\s*)")
_ID_TOKEN = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,3}\d{1,4})(?![A-Za-z0-9])")
_SECONDS = re.compile(r"(\d+(?:\.\d+)?)\s*秒")
_MS = re.compile(r"(\d+)\s*毫秒")
_MINUTES = re.compile(r"(\d+(?:\.\d+)?)\s*分钟")
_SPEED = re.compile(r"(\d+(?:\.\d+)?)\s*(?:km/h|公里每小时|公里/小时|千米每小时|码)")
_INT = re.compile(r"(\d+)")

_METHOD_WORDS = {
    "greedy": ("贪心", "greedy", "基线"),
    "sequential": ("先路线后装载", "顺序", "sequential", "不反馈"),
    "coupled": ("协同", "coupled", "反馈"),
}
_DIM_WORDS = {"载重": "max_weight_kg", "长度": "length_mm", "长": "length_mm", "宽度": "width_mm", "宽": "width_mm", "高度": "height_mm", "高": "height_mm", "重量": "weight_kg", "重": "weight_kg"}
# 门店的坐标 / 位置类修改不在白名单；仍生成一个会被拒绝的 set，让用户看到「x_km 不在允许修改范围」而不是被静默忽略
_STORE_FORBIDDEN = re.compile(r"坐标|位置|地址|x_km|y_km|经纬|地方")


def parse_rules(instruction: str, r: SolveRequest) -> tuple[list[IntentOp], list[str]]:
    known_stores = {s.id.upper(): s.id for s in r.stores}
    known_vehicles = {v.id.upper(): v.id for v in r.vehicles}
    known_boxes = {b.id.upper(): b.id for b in r.boxes}
    ops: list[IntentOp] = []
    notes: list[str] = []
    last: tuple[str, str] | None = None  # (target, id) 供无 ID 的后续子句沿用

    for clause in [c.strip() for c in _SPLIT.split(instruction) if c and c.strip()]:
        ids = [t.upper() for t in _ID_TOKEN.findall(clause)]
        ent: tuple[str, str] | None = None
        unknown: list[str] = []
        for t in ids:
            if t in known_stores:
                ent = ("store", known_stores[t])
            elif t in known_vehicles:
                ent = ("vehicle", known_vehicles[t])
            elif t in known_boxes:
                ent = ("box", known_boxes[t])
            else:
                unknown.append(t)
            if ent:
                break
        if ent is None and unknown:
            # 明确指向了不存在的实体：生成一个会被拒绝的占位操作，让用户看到「S99 不存在」
            uid = unknown[0]
            target = "store" if uid.startswith("S") else "vehicle" if uid.startswith("V") else "box"
            if target == "vehicle":
                ops.append(IntentOp(action="remove_vehicle", target="vehicle", id=uid))
            else:
                ops.append(IntentOp(action="set", target=target, id=uid, field="window_start_min" if target == "store" else "fragile", value=None))
            notes.append(f"指令提到的 {uid} 不在当前案例中。")
            continue
        if ent is None:
            ent = last

        new_ops = _clause_ops(clause, ent, r)
        if new_ops:
            ops.extend(new_ops)
            if ent:
                last = ent
        else:
            if ent:
                last = ent
            # 没生成任何操作的子句必须显式告知，不能让「部分理解」看起来像「完整理解」
            notes.append(f"未识别子句「{clause}」，未生成修改。")
    return ops, notes


def _clause_ops(c: str, ent: tuple[str, str] | None, r: SolveRequest) -> list[IntentOp]:
    ops: list[IntentOp] = []

    # --- 求解选项（与实体无关） ---
    if re.search(r"时间预算|求解时间|算\s*\d+\s*秒|限时", c):
        ms = _MS.search(c)
        sec = _SECONDS.search(c)
        if ms:
            ops.append(IntentOp(action="set", target="options", field="time_limit_ms", value=int(ms.group(1))))
        elif sec:
            ops.append(IntentOp(action="set", target="options", field="time_limit_ms", value=int(float(sec.group(1)) * 1000)))
    if "车速" in c or _SPEED.search(c):
        m = _SPEED.search(c) or (_INT.search(c.split("车速", 1)[1]) if "车速" in c else None)
        if m:
            ops.append(IntentOp(action="set", target="options", field="speed_kmph", value=float(m.group(1))))
    if re.search(r"方法|算法|改用|换成|用", c) and not ent:
        for method, words in _METHOD_WORDS.items():
            if any(w in c for w in words):
                ops.append(IntentOp(action="set", target="options", field="method", value=method))
                break
    if re.search(r"种子|seed", c, re.I):
        m = _INT.search(c)
        if m:
            ops.append(IntentOp(action="set", target="options", field="seed", value=int(m.group(1))))
    if re.search(r"迭代", c):
        m = _INT.search(c)
        if m:
            ops.append(IntentOp(action="set", target="options", field="max_iterations", value=int(m.group(1))))
    if re.search(r"仓库|出发", c) and not ent:
        t = find_time(c)
        if t:
            ops.append(IntentOp(action="set", target="depot", field="departure_min", value=t[0]))
    # 新增车辆：再加一辆和 V01 一样的车（叫 V03）
    m = re.search(r"(?:再)?(?:加|增加|添加|补)\s*一辆(?:和|跟|与|同)\s*([A-Za-z]{1,3}\d{1,4})\s*(?:一样|相同|同款)的车(?:[，,]?\s*(?:叫|编号|编号为|ID|id|命名为)\s*([A-Za-z]{1,3}\d{1,4}))?", c)
    if m:
        src = next((v for v in r.vehicles if v.id.upper() == m.group(1).upper()), None)
        if src:
            new_id = m.group(2) or _next_vehicle_id(r)
            v = src.model_dump()
            v["id"] = new_id
            ops.append(IntentOp(action="add_vehicle", target="vehicle", value=v))
    if ops and ent is None:
        return ops

    if ent is None:
        return ops
    target, id_ = ent

    # --- 车辆 ---
    if target == "vehicle":
        if re.search(r"不出车|不可用|停用|去掉|移除|删掉|删除|维修|坏了|不用|不派|不能用|没法用|不参与", c):
            ops.append(IntentOp(action="remove_vehicle", target="vehicle", id=id_))
        else:
            for w, f in _DIM_WORDS.items():
                if w in c:
                    m = _INT.search(c.split(w, 1)[1])
                    if m:
                        ops.append(IntentOp(action="set", target="vehicle", id=id_, field=f, value=int(m.group(1))))
                        break
        return ops

    # --- 箱件 ---
    if target == "box":
        if "易碎" in c:
            neg = re.search(r"(不|非|取消|去掉).{0,3}易碎", c) is not None
            ops.append(IntentOp(action="set", target="box", id=id_, field="fragile", value=not neg))
        if re.search(r"旋转|转向|横放|竖放", c):
            neg = re.search(r"(不能|不可|不允许|禁止|别)", c) is not None
            ops.append(IntentOp(action="set", target="box", id=id_, field="allow_rotate_xy", value=not neg))
        for w, f in _DIM_WORDS.items():
            if w in c and f != "max_weight_kg":
                m = _INT.search(c.split(w, 1)[1])
                if m:
                    ops.append(IntentOp(action="set", target="box", id=id_, field=f, value=int(m.group(1))))
                    break
        return ops

    # --- 门店 ---
    if target == "store":
        if _STORE_FORBIDDEN.search(c):
            m = _INT.search(_ID_TOKEN.sub(" ", c))  # 先去掉 S01 这类 ID，免得把 01 当成数值
            ops.append(IntentOp(action="set", target="store", id=id_, field="x_km", value=int(m.group(1)) if m else None))
            return ops
        if re.search(r"服务时长|卸货时间|服务时间|卸货要|停留", c):
            m = _MINUTES.search(c)
            if m:
                ops.append(IntentOp(action="set", target="store", id=id_, field="service_min", value=float(m.group(1))))
                return ops
        t = find_time(c)
        if t:
            minutes, _ = t
            if re.search(r"最晚|之前|以前|截止|前(?!后)|不晚于|结束|关门", c):
                ops.append(IntentOp(action="set", target="store", id=id_, field="window_end_min", value=minutes))
            elif re.search(r"最早|之后|以后|起|开始|不早于|才|后", c):
                ops.append(IntentOp(action="set", target="store", id=id_, field="window_start_min", value=minutes))
            else:
                # 只给了一个时刻、没说早晚：按「最早」处理并在摘要里体现
                ops.append(IntentOp(action="set", target="store", id=id_, field="window_start_min", value=minutes))
        return ops
    return ops


def _next_vehicle_id(r: SolveRequest) -> str:
    nums = [int(m.group(1)) for v in r.vehicles if (m := re.search(r"(\d+)$", v.id))]
    n = (max(nums) + 1) if nums else len(r.vehicles) + 1
    return f"V{n:02d}"
