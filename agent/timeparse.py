"""中文/数字时刻解析 → 当天零点起分钟数。支持 "14:00"、"下午两点"、"9点半"、"840"。"""
from __future__ import annotations

import re

_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_number(s: str) -> int | None:
    """「十一」→11，「二十四」→24，「两」→2，纯数字直接转。"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    if not s:
        return None
    if s == "十":
        return 10
    total = 0
    if "十" in s:
        tens, _, ones = s.partition("十")
        t = _CN_DIGITS.get(tens, 1) if tens else 1
        o = _CN_DIGITS.get(ones, 0) if ones else 0
        if (tens and tens not in _CN_DIGITS) or (ones and ones not in _CN_DIGITS):
            return None
        return t * 10 + o
    for ch in s:
        if ch not in _CN_DIGITS:
            return None
        total = total * 10 + _CN_DIGITS[ch]
    return total


_HHMM = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?![\d:])")
_CN_TIME = re.compile(
    r"(上午|早上|早晨|中午|下午|晚上|傍晚|夜里)?\s*"
    r"(\d{1,2}|[一二两三四五六七八九十]{1,3})\s*[点时]\s*"
    r"(半|(?:(\d{1,2}|[一二两三四五六七八九十]{1,3})\s*分?))?"
)
_PERIOD_PM = {"下午", "晚上", "傍晚", "夜里"}


def find_time(text: str) -> tuple[int, str] | None:
    """在文本中找第一个时刻表达，返回 (分钟数, 匹配原文)。找不到返回 None。"""
    m = _HHMM.search(text)
    c = _CN_TIME.search(text)
    # 取出现更早的那个
    cands = [x for x in (m, c) if x]
    if not cands:
        return None
    first = min(cands, key=lambda x: x.start())
    if first is m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 24 or mi > 59:
            return None
        return h * 60 + mi, m.group(0)
    period, hour_s, half_or_min, min_s = c.group(1), c.group(2), c.group(3), c.group(4)
    hour = cn_number(hour_s)
    if hour is None or hour > 24:
        return None
    minute = 0
    if half_or_min == "半":
        minute = 30
    elif min_s:
        minute = cn_number(min_s) or 0
    if period in _PERIOD_PM and hour < 12:
        hour += 12
    if period == "中午" and hour < 6:
        hour += 12
    return hour * 60 + minute, c.group(0)


def to_minutes(value) -> float | None:
    """把模型或规则给出的时刻值统一为分钟：数字直接返回；字符串尝试解析。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        v = value.strip()
        if re.fullmatch(r"\d+(?:\.\d+)?", v):
            return float(v)
        t = find_time(v)
        return float(t[0]) if t else None
    return None


def hhmm(minutes: float) -> str:
    t = int(round(minutes))
    if t == 1440:
        return "24:00"  # 当天结束，与页面和模板一致
    return f"{(t // 60) % 24:02d}:{t % 60:02d}"
