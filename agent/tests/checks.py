"""测试与评估共用：按实体 ID 比较 patched_request 与原请求，返回不符项列表。"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "playbook" / "examples"


def load_request(name: str) -> dict[str, Any]:
    """partial / success / partial2v（partial 加一辆 V02）。"""
    base = "request-partial.json" if name.startswith("partial") else "request-success.json"
    r = json.loads((EXAMPLES / base).read_text(encoding="utf-8"))
    if name == "partial2v":
        v = copy.deepcopy(r["vehicles"][0])
        v["id"] = "V02"
        v["fixed_cost"] = 80
        r["vehicles"].append(v)
    return r


def _leaves(obj: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(_leaves(v, f"{prefix}.{k}" if prefix else k))
    else:
        out[prefix] = obj
    return out


def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {it["id"]: it for it in items}


def verify(original: dict[str, Any], patched: dict[str, Any] | None, expect: dict[str, Any], resp: dict[str, Any]) -> list[str]:
    """返回不符项；空列表表示通过。"""
    errs: list[str] = []
    if resp["understood"] != expect["understood"]:
        errs.append(f"understood={resp['understood']}，期望 {expect['understood']}")
    if not expect["understood"]:
        if resp["patch"]:
            errs.append(f"未理解时不应有补丁：{resp['patch']}")
        return errs
    n_rej = len(resp["rejected_ops"])
    if "rejected" in expect and n_rej != expect["rejected"]:
        errs.append(f"rejected_ops 数量 {n_rej}，期望 {expect['rejected']}：{[x['reason'] for x in resp['rejected_ops']]}")
    if "rejected_in" in expect and n_rej not in expect["rejected_in"]:
        errs.append(f"rejected_ops 数量 {n_rej}，期望在 {expect['rejected_in']} 内：{[x['reason'] for x in resp['rejected_ops']]}")
    if patched is None:
        errs.append("patched_request 为空")
        return errs

    exp_changes: dict[str, Any] = dict(expect.get("changes", {}))
    removed = set(expect.get("removed_vehicles", []))
    added = set(expect.get("added_vehicles", []))

    # 逐实体比较
    for coll in ("stores", "boxes"):
        o, p = by_id(original[coll]), by_id(patched[coll])
        if set(o) != set(p):
            errs.append(f"{coll} 集合变化：{sorted(set(o) ^ set(p))}")
            continue
        for id_, item in o.items():
            for field, val in item.items():
                key = f"{coll}.{id_}.{field}"
                got = p[id_][field]
                if key in exp_changes:
                    if not _eq(got, exp_changes.pop(key)):
                        errs.append(f"{key}={got!r}，期望 {expect['changes'][key]!r}")
                elif not _eq(got, val):
                    errs.append(f"{key} 不应改变：{val!r} → {got!r}")
    ov, pv = by_id(original["vehicles"]), by_id(patched["vehicles"])
    if set(ov) - set(pv) != removed:
        errs.append(f"移除的车辆 {sorted(set(ov) - set(pv))}，期望 {sorted(removed)}")
    if set(pv) - set(ov) != added:
        errs.append(f"新增的车辆 {sorted(set(pv) - set(ov))}，期望 {sorted(added)}")
    for id_ in set(ov) & set(pv):
        if ov[id_] != pv[id_]:
            errs.append(f"车辆 {id_} 不应改变")
    for scope in ("depot", "options"):
        for field, val in original[scope].items():
            key = f"{scope}.{field}"
            got = patched[scope][field]
            if key in exp_changes:
                if not _eq(got, exp_changes.pop(key)):
                    errs.append(f"{key}={got!r}，期望 {expect['changes'][key]!r}")
            elif not _eq(got, val):
                errs.append(f"{key} 不应改变：{val!r} → {got!r}")
    for k in ("schema_version", "case_id", "data_source"):
        if original[k] != patched[k]:
            errs.append(f"{k} 不应改变")
    if exp_changes:
        errs.append(f"期望的改动未出现：{exp_changes}")
    return errs


def _eq(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-9
    return a == b
