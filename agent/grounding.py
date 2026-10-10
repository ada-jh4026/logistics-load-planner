"""证据绑定：从模型文本中提取数字，逐个核对是否能在事实表中找到。

匹配规则（AGENT_CONTRACT.md）：允许四舍五入到 1 位小数、百分数与小数互转、分钟与 HH:MM 互转。
带单位的数字只在同类事实里找（「150 元」不能用「150 kg」来圆），不带单位的数字在全部事实里找。
"""
from __future__ import annotations

import math
import re
from typing import Any

# 时刻 HH:MM；百分数；普通数字（含小数、千分位）+ 可选单位
_TIME = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])")
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_NUM = re.compile(
    r"(?<![\w.:])(\d+(?:,\d{3})*(?:\.\d+)?)(?![\d:%])\s*(元|km|公里|kg|千克|公斤|分钟|箱|件|辆|站|家|处)?"
)
# 序数/编号类上下文不算「事实数字」：第 N 站、步骤 N、列表序号、ID 里的数字
_ORDINAL = re.compile(r"(第\s*\d+\s*站|第\s*\d+\s*步|步骤\s*\d+|^\s*\d+\.\s|\n\s*\d+\.\s|[A-Za-z]+\d+)")

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
    "家": ("store",),
    "处": ("unload_block",),
}


class FactIndex:
    """把事实表展平为 (路径, 数值) 列表。"""

    def __init__(self, facts: dict[str, Any]):
        self.entries: list[tuple[str, float]] = []
        self._walk(facts, "")

    def _walk(self, node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                self._walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                self._walk(v, f"{path}[{i}]")
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)) and math.isfinite(node):
            self.entries.append((path.lower(), float(node)))

    @staticmethod
    def _close(text_val: float, fact: float, decimals: int = 0) -> bool:
        """文本值按其小数位数视为对事实的四舍五入：|fact − text| ≤ 半个最后一位。
        用容差而不是 round()，避免 Python 银行家舍入把 56.25 舍成 56.2 而误判模型写的 56.3。"""
        if abs(text_val - fact) <= 1e-6:
            return True
        tol = 0.5 * 10 ** (-decimals) + 1e-9
        return abs(text_val - fact) <= tol

    def _candidates(self, unit: str | None) -> list[float]:
        if not unit:
            return [v for _, v in self.entries]
        keys = UNIT_PATHS.get(unit, ())
        return [v for p, v in self.entries if any(k in p for k in keys)]

    def has_number(self, x: float, unit: str | None, decimals: int = 0) -> bool:
        return any(self._close(x, v, decimals) for v in self._candidates(unit))

    def has_percent(self, p: float, decimals: int = 0) -> bool:
        # 比率类事实（利用率、完成率、费用变化率）在 [-1, 1]；文本里的百分数不带符号，所以按绝对值匹配
        return any(self._close(p, abs(v) * 100, decimals) for _, v in self.entries if -1 <= v <= 1)

    def has_time(self, h: int, m: int) -> bool:
        target = h * 60 + m
        return any(round(v) % 1440 == target for p, v in self.entries if p.endswith("_min"))


def _decimals(token: str) -> int:
    return len(token.split(".", 1)[1]) if "." in token else 0


def check_grounding(text: str, facts: dict[str, Any]) -> tuple[int, list[str]]:
    """返回 (核对数字个数, 未匹配数字列表)。"""
    index = FactIndex(facts)
    checked = 0
    unmatched: list[str] = []

    scrubbed = _ORDINAL.sub(" ", text)

    for mt in _TIME.finditer(scrubbed):
        checked += 1
        if not index.has_time(int(mt.group(1)), int(mt.group(2))):
            unmatched.append(mt.group(0))
    scrubbed = _TIME.sub(" ", scrubbed)

    for mp in _PCT.finditer(scrubbed):
        checked += 1
        if not index.has_percent(float(mp.group(1)), _decimals(mp.group(1))):
            unmatched.append(mp.group(0))
    scrubbed = _PCT.sub(" ", scrubbed)

    for mn in _NUM.finditer(scrubbed):
        raw = mn.group(1).replace(",", "")
        val = float(raw)
        unit = mn.group(2)
        checked += 1
        if not index.has_number(val, unit, _decimals(raw)):
            unmatched.append(mn.group(1) + (f" {unit}" if unit else ""))

    return checked, unmatched
