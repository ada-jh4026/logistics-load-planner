"""证据绑定：从模型文本中提取数字，逐个核对是否能在事实表中找到。

匹配规则（AGENT_CONTRACT.md）：允许四舍五入到 1 位小数、百分数与小数互转、分钟与 HH:MM 互转。
带单位的数字只在同类事实里找（「150 元」不能用「150 kg」来圆），不带单位的数字在全部事实里找。

2026-10-10 审查后收紧：
- 紧邻中文的阿拉伯数字（「费用99999元」）同样提取；
- 「万 / 亿」倍率与常见中文数字（「九万九千九百九十九元」「一千二百元」「百分之五十」）先换算再核对，换算不了的记为未匹配；
- 子句里只提到一个车辆 / 门店 ID 时，该子句的费用、里程、重量、分钟、百分数、时刻只在该实体的事实里找，
  不能借用全局合计（「V02 的费用为 2003.2 元」不能用总费用来圆）；件数类（辆 / 站 / 箱 / 个…）仍允许退回全局计数。
核对仍是文本层面的拦截：它证明「每个被识别的数字都出现在事实表里」，不证明句子的语义正确。
"""
from __future__ import annotations

import math
import re
from typing import Any

_UNITS = "元|km|公里|kg|千克|公斤|分钟|箱|件|辆|站|家|处|次|个"
# 时刻 HH:MM；百分数；普通数字（含小数、千分位）+ 可选倍率 + 可选单位
_TIME = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])")
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_NUM = re.compile(rf"(?<![A-Za-z0-9.:])(\d+(?:,\d{{3}})*(?:\.\d+)?)(?![\d:%])\s*(万|亿)?\s*({_UNITS})?")
# 中文数字 + 单位 / 百分之 N；「下一站」「每一站」「第一站」这类不是数量
_CN_CHARS = "零一二两三四五六七八九十百千万亿"
_CN_NUM = re.compile(rf"(?<![下上每第同这那哪某另任])([{_CN_CHARS}]+)\s*({_UNITS}|%)")
_CN_PCT = re.compile(rf"百分之\s*([{_CN_CHARS}\d.]+)")
# 序数/编号类上下文不算「事实数字」：第 N 站、步骤 N、列表序号、ID 里的数字
_ORDINAL = re.compile(
    r"(第\s*[\d一二三四五六七八九十]+\s*[站步次个辆家箱件]|步骤\s*\d+|^\s*\d+\.\s|\n\s*\d+\.\s|[：:]\s*\d+\.\s|[A-Za-z]+\d+)"
)
_ENTITY = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,3}\d{1,4})(?![A-Za-z0-9])")
_CLAUSE = re.compile(r"[。；;，\n]|,(?!\d)")  # ASCII 逗号后紧跟数字视为千分位，不切分

# 单位 → 事实表路径关键字（小写子串匹配）
UNIT_PATHS: dict[str, tuple[str, ...]] = {
    "元": ("cost",),
    "km": ("distance",),
    "公里": ("distance",),
    "kg": ("weight",),
    "千克": ("weight",),
    "公斤": ("weight",),
    "分钟": ("_min",),
    "箱": ("box",),
    "件": ("box",),
    "辆": ("vehicle",),
    "站": ("stop", "store"),
    "家": ("store", "stop"),  # 「V01 送 1 家」对应车辆 stop_count
    "处": ("unload_block", "_count"),
    "次": ("_count",),
    "个": ("_count", "box", "stop", "store", "vehicle"),
}
# 这些单位的数字在只提到一个实体的子句里必须来自该实体，不得退回全局合计
_MEASURE_UNITS = {"元", "km", "公里", "kg", "千克", "公斤", "分钟"}
_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}
_CN_BIG = {"万": 10_000, "亿": 100_000_000}


def cn_to_number(s: str) -> float | None:
    """「九万九千九百九十九」→ 99999，「一千二」→ 1200，「二十五」→ 25，「十」→ 10；解析不了返回 None。"""
    s = s.strip()
    if not s:
        return None
    if s.replace(".", "", 1).isdigit():
        return float(s)
    total = 0
    section = 0
    num = 0
    last_unit = 0
    for ch in s:
        if ch in _CN_DIGIT:
            num = _CN_DIGIT[ch]
            if ch == "零":
                last_unit = 0
        elif ch in _CN_UNIT:
            section += (num if num else 1) * _CN_UNIT[ch]
            last_unit = _CN_UNIT[ch]
            num = 0
        elif ch in _CN_BIG:
            section += num
            total += (section if section else 1) * _CN_BIG[ch]
            section = 0
            num = 0
            last_unit = _CN_BIG[ch]
        else:
            return None
    if num and last_unit:
        num *= last_unit // 10  # 「一千二」= 1200，「三百五」= 350，「一万二」= 12000
    return float(total + section + num)


class FactIndex:
    """把事实表展平为 (路径, 数值) 列表；同时按车辆 / 门店 ID 建子索引。"""

    def __init__(self, facts: dict[str, Any]):
        self.entries: list[tuple[str, float]] = []
        self.by_entity: dict[str, list[tuple[str, float]]] = {}
        self.global_entries: list[tuple[str, float]] = []
        self._walk(facts, "", self.entries)
        for key in ("case", "metrics", "run", "repair"):
            if key in facts:
                self._walk(facts[key], key, self.global_entries)
        for i, v in enumerate(facts.get("vehicles") or []):
            self._bind(v, f"vehicles[{i}]", [v.get("vehicle_id")])
        for i, st in enumerate(facts.get("stops") or []):
            self._bind(st, f"stops[{i}]", [st.get("vehicle_id"), st.get("store_id")])
        for i, u in enumerate(facts.get("unload") or []):
            self._bind(u, f"unload[{i}]", [u.get("vehicle_id")])
        for i, u in enumerate(facts.get("unassigned") or []):
            self._bind(u, f"unassigned[{i}]", [u.get("store_id")])

    def _bind(self, node: Any, path: str, ids: list[Any]) -> None:
        bucket: list[tuple[str, float]] = []
        self._walk(node, path, bucket)
        for id_ in ids:
            if isinstance(id_, str) and id_:
                self.by_entity.setdefault(id_.upper(), []).extend(bucket)

    def _walk(self, node: Any, path: str, out: list[tuple[str, float]]) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                self._walk(v, f"{path}.{k}" if path else k, out)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                self._walk(v, f"{path}[{i}]", out)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)) and math.isfinite(node):
            out.append((path.lower(), float(node)))

    @staticmethod
    def _close(text_val: float, fact: float, decimals: int = 0) -> bool:
        """文本值按其小数位数视为对事实的四舍五入：|fact − text| ≤ 半个最后一位。
        用容差而不是 round()，避免 Python 银行家舍入把 56.25 舍成 56.2 而误判模型写的 56.3。"""
        if abs(text_val - fact) <= 1e-6:
            return True
        tol = 0.5 * 10 ** (-decimals) + 1e-9
        return abs(text_val - fact) <= tol

    def scope(self, entity: str | None, unit: str | None) -> list[tuple[str, float]]:
        """子句绑定了一个实体：度量类单位只看该实体；计数类单位看该实体 + 全局合计；无单位看全部。"""
        if entity is None or unit is None:
            return self.entries
        own = self.by_entity.get(entity.upper(), [])
        if unit in _MEASURE_UNITS or unit in ("%", "time"):
            return own
        return own + self.global_entries

    @staticmethod
    def _filter_unit(entries: list[tuple[str, float]], unit: str | None) -> list[float]:
        if not unit:
            return [v for _, v in entries]
        keys = UNIT_PATHS.get(unit, ())
        return [v for p, v in entries if any(k in p for k in keys)]

    def has_number(self, x: float, unit: str | None, decimals: int = 0, entity: str | None = None) -> bool:
        return any(self._close(x, v, decimals) for v in self._filter_unit(self.scope(entity, unit), unit))

    def has_percent(self, p: float, decimals: int = 0, entity: str | None = None) -> bool:
        # 比率类事实（利用率、完成率、费用变化率）在 [-1, 1]；文本里的百分数不带符号，所以按绝对值匹配
        return any(self._close(p, abs(v) * 100, decimals) for _, v in self.scope(entity, "%") if -1 <= v <= 1)

    def has_time(self, h: int, m: int, entity: str | None = None) -> bool:
        target = h * 60 + m
        return any(round(v) % 1440 == target for p, v in self.scope(entity, "time") if p.endswith("_min"))


def _decimals(token: str) -> int:
    return len(token.split(".", 1)[1]) if "." in token else 0


def check_grounding(text: str, facts: dict[str, Any]) -> tuple[int, list[str]]:
    """返回 (核对数字个数, 未匹配数字列表)。"""
    index = FactIndex(facts)
    checked = 0
    unmatched: list[str] = []

    for clause in _CLAUSE.split(text):
        if not clause.strip():
            continue
        ids = {t.upper() for t in _ENTITY.findall(clause)}
        bound = [i for i in ids if i in index.by_entity]
        entity = bound[0] if len(bound) == 1 else None
        scrubbed = _ORDINAL.sub(" ", clause)

        for mt in _TIME.finditer(scrubbed):
            checked += 1
            if not index.has_time(int(mt.group(1)), int(mt.group(2)), entity):
                unmatched.append(mt.group(0))
        scrubbed = _TIME.sub(" ", scrubbed)

        for mp in _CN_PCT.finditer(scrubbed):
            checked += 1
            val = cn_to_number(mp.group(1))
            if val is None or not index.has_percent(val, 0, entity):
                unmatched.append(mp.group(0))
        scrubbed = _CN_PCT.sub(" ", scrubbed)

        for mp in _PCT.finditer(scrubbed):
            checked += 1
            if not index.has_percent(float(mp.group(1)), _decimals(mp.group(1)), entity):
                unmatched.append(mp.group(0))
        scrubbed = _PCT.sub(" ", scrubbed)

        for mn in _NUM.finditer(scrubbed):
            raw = mn.group(1).replace(",", "")
            val = float(raw)
            decimals = _decimals(raw)
            mult, unit = mn.group(2), mn.group(3)
            if mult:
                val *= _CN_BIG[mult]
                decimals -= len(str(_CN_BIG[mult])) - 1
            checked += 1
            if not index.has_number(val, unit, decimals, entity):
                unmatched.append(mn.group(1) + (f" {mult}" if mult else "") + (f" {unit}" if unit else ""))
        scrubbed = _NUM.sub(" ", scrubbed)

        for mc in _CN_NUM.finditer(scrubbed):
            if mc.group(1) == "一":
                continue  # 「一处」「一个」多为量词而非数量（「没有一处阻挡」），不当作事实数字
            checked += 1
            val = cn_to_number(mc.group(1))
            unit = mc.group(2)
            ok = val is not None and (
                index.has_percent(val, 0, entity) if unit == "%" else index.has_number(val, unit, 0, entity)
            )
            if not ok:
                unmatched.append(mc.group(0))

    return checked, unmatched
