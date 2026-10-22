"""读取 rules/presets.json（单一事实来源），并把模板步骤实例化。"""

import copy
import json
import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PRESETS_PATH = os.path.join(REPO_ROOT, "rules", "presets.json")

SIDES = ("正方", "反方")
_CACHE = {}


def load(path=None):
    path = path or PRESETS_PATH
    mtime = os.path.getmtime(path)
    hit = _CACHE.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    _CACHE[path] = (mtime, data)
    return data


def _split_side(step_id):
    m = re.match(r"^(.+)-(正方|反方)$", step_id)
    if m:
        return m.group(1), m.group(2)
    return step_id, None


def _fill(value, side, user_side):
    if isinstance(value, str):
        return value.replace("{side}", side or "").replace("{user_side}", user_side or "")
    if isinstance(value, list):
        return [_fill(v, side, user_side) for v in value]
    if isinstance(value, dict):
        return {k: _fill(v, side, user_side) for k, v in value.items()}
    return value


def step_spec(step_id, user_side="正方", data=None):
    """返回实例化后的步骤规格（dict），未知步骤返回 None。"""
    data = data or load()
    steps = data["steps"]
    base, side = _split_side(step_id)
    if step_id in steps:
        spec = copy.deepcopy(steps[step_id])
        side = None
    elif base in steps and steps[base].get("per_side") and side:
        spec = copy.deepcopy(steps[base])
    else:
        return None
    spec = _fill(spec, side, user_side)
    spec["id"] = step_id
    spec["side"] = side or spec.get("side")
    if side is None and spec.get("stage") == "H" and spec.get("kind") not in ("judge",):
        spec["side"] = user_side
    return spec


def all_step_ids(data=None):
    data = data or load()
    ids = []
    for sid, spec in data["steps"].items():
        if spec.get("per_side"):
            ids.extend("%s-%s" % (sid, s) for s in SIDES)
        else:
            ids.append(sid)
    return ids


def preset_names(data=None):
    return list((data or load())["presets"].keys())


def preset_steps(name, data=None):
    data = data or load()
    preset = data["presets"].get(name) or data["presets"]["full"]
    return list(preset["steps"])


def match_step_id(filename, data=None):
    """根据文件名识别步骤：`R02-质询-xxx.md` → R02；`B0-正方-xx.md` → B0-正方。"""
    name = os.path.basename(filename)
    if name.lower().endswith(".md"):
        name = name[:-3]
    best = None
    for sid in all_step_ids(data):
        if name == sid or name.startswith(sid + "-") or name.startswith(sid + "_") or name.startswith(sid + " "):
            if best is None or len(sid) > len(best):
                best = sid
    if best is None:
        # 兼容 R1 / R2 这类不补零写法
        m = re.match(r"^R(\d)(?:[-_ ]|$)", name)
        if m:
            cand = "R%02d" % int(m.group(1))
            if cand in all_step_ids(data):
                return cand
    return best


def speakers_for(spec, lineup):
    """根据阵容给出该步骤涉及的辩手 [{role, name}]。lineup: {"正方": {"一辩": "胡渐彪", ...}, ...}"""
    lineup = lineup or {}

    def who(role):
        if not role or len(role) < 4:
            return {"role": role, "name": ""}
        side, pos = role[:2], role[2:]
        return {"role": role, "name": (lineup.get(side) or {}).get(pos, "")}

    kind = spec.get("kind")
    if kind == "speech" and spec.get("speaker"):
        return [who(spec["speaker"])]
    if kind == "cross_exam":
        return [who(spec["questioner"]), who(spec["respondent"])]
    if kind == "self_proof":
        return [who(spec["prover"]), {"role": spec["interrupter_side"] + "（打岔方）", "name": ""}]
    if kind in ("meeting", "research") and spec.get("side") in SIDES:
        side = spec["side"]
        return [who(side + p) for p in ("一辩", "二辩", "三辩", "四辩")]
    if kind == "speech" and spec.get("side") in SIDES:
        # 赛前/赛后彩排：从标题里推断辩位
        m = re.search(r"([一二三四])辩", spec.get("title", ""))
        if m:
            return [who(spec["side"] + m.group(1) + "辩")]
    return []


def budget(name="full", data=None):
    """返回 (rows, total)。rows: [(step_id, title, duration, min_chars)]"""
    data = data or load()
    rows = []
    total = 0
    for sid in preset_steps(name, data):
        spec = step_spec(sid, data=data) or {}
        mc = int(spec.get("min_chars") or 0)
        total += mc
        rows.append((sid, spec.get("title", sid), spec.get("duration", "—"), mc))
    return rows, total
