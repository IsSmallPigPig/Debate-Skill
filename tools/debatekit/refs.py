"""「定位引用」——网页「复制位置并提问」与 Agent 端定位之间的契约。

URI：  debate://<session_id>/<doc_key>#b<N>
        doc_key = 步骤 ID（R02、B0-正方、J、S…）或相对路径去掉 .md（artifacts/正方-一辩稿）

剪贴板文本（网页生成，用户粘贴给 Agent）：

    【辩论协同·提问】
    会话：<topic>（<session_id>）
    提问对象：教练（跳出角色）｜意图：补强

    [1] debate://<sid>/R02#b5
        位置：第 2 轮 · 质询｜反方四辩 → 正方一辩 › ¶5 · 反方四辩 · 陈铭
        原文：「……」

    问题：……

解析时以「原文」为准、锚点为辅：块编号可能因重写而漂移，原文匹配可自动纠偏。
"""

import re

from . import mdblocks

RE_URI = re.compile(r"debate://(?P<sid>[^/\s#]+)/(?P<key>[^#\s]+)#(?P<anchor>b\d+)")
RE_QUOTE_LINE = re.compile(r"^\s*原文[：:]\s*[「“\"]?(?P<q>.*?)[」”\"]?\s*$")
RE_HEADER_LINE = re.compile(r"^\s*(提问对象|意图)[：:]\s*(.+)$")


def make_uri(session_id, doc_key, block_i):
    return "debate://%s/%s#b%d" % (session_id, doc_key, int(block_i))


def parse_refs(text):
    """从粘贴文本中提取所有引用：[{sid, key, anchor, block, quote}]，以及 target / intent / question。"""
    refs = []
    lines = (text or "").split("\n")
    for idx, line in enumerate(lines):
        for m in RE_URI.finditer(line):
            ref = {
                "uri": m.group(0),
                "sid": m.group("sid"),
                "key": m.group("key"),
                "anchor": m.group("anchor"),
                "block": int(m.group("anchor")[1:]),
                "quote": "",
            }
            for nxt in lines[idx + 1: idx + 5]:
                if RE_URI.search(nxt):
                    break
                qm = RE_QUOTE_LINE.match(nxt)
                if qm:
                    ref["quote"] = qm.group("q").strip().rstrip("…").strip()
                    break
            refs.append(ref)
    info = {"target": "", "intent": "", "question": ""}
    for line in lines:
        for part in re.split(r"[｜|]", line):
            hm = RE_HEADER_LINE.match(part)
            if hm:
                info["target" if hm.group(1) == "提问对象" else "intent"] = hm.group(2).strip()
    qm = re.search(r"问题[：:]\s*(.+?)(?:\n（Agent|\Z)", text or "", re.S)
    if qm:
        info["question"] = qm.group(1).strip()
    return refs, info


def _norm(s):
    return re.sub(r"[\s\u3000]+", "", s or "")


def locate_in_blocks(blocks, block_i=None, quote=""):
    """返回 (block, method)。优先用原文精确定位（最接近锚点的命中），否则用块编号。"""
    nq = _norm(quote)
    if nq:
        probe = nq[:60]
        hits = [b for b in blocks if probe and probe in _norm(mdblocks.block_plain(b) if b["type"] != "para" else (
            mdblocks.plain_text(b["turn"]["body"]) if b.get("turn") else mdblocks.plain_text(b["text"])))]
        if not hits and len(nq) > 12:
            probe = nq[:12]
            hits = [b for b in blocks if probe in _norm(mdblocks.block_plain(b))]
        if hits:
            if block_i:
                hits.sort(key=lambda b: abs(b["i"] - block_i))
            method = "quote" if (not block_i or hits[0]["i"] == block_i) else "quote(drift %+d)" % (hits[0]["i"] - block_i)
            return hits[0], method
    if block_i and 1 <= block_i <= len(blocks):
        return blocks[block_i - 1], "anchor"
    return None, "not_found"


def describe_block(blk):
    if blk is None:
        return ""
    label = "¶%d" % blk["i"]
    if blk["type"] == "para" and blk.get("turn"):
        label += " · " + blk["turn"]["label"]
        if blk["turn"].get("note"):
            label += "（%s）" % blk["turn"]["note"]
    elif blk["type"] == "heading":
        label += " · 标题"
    elif blk["type"] == "table":
        label += " · 表格"
    return label
