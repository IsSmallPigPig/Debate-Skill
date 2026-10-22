"""机器校验「完成契约」。

v2.x 的【完成】契约行由模型自报（字数、回合数……），而大模型并不能可靠地数汉字，
所以 v3 由本模块**实测**：字数、动作括号、小说旁白、元说明、占位符、回合数、打岔次数、
自由辩交替、URL 与证据台账、对方原话引用是否真实存在（反稻草人）。

严重级别：
- error：违反硬规则（字数不足、回合不足、动作括号、占位符……）→ 必须重做
- warn ：软规则（缺套语、URL 少、引用找不到原文……）→ 建议修正
"""

import re

from . import mdblocks

# ---------------------------------------------------------------- 字数

_CJK = "\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
_CJK_PUNCT = "\u3000-\u303f\uff00-\uffef\u2018\u2019\u201c\u201d\u2014\u2026\u00b7"
RE_URL = re.compile(r"https?://[^\s<>（）()「」\"“”'，。；！？、]+")
RE_COUNT = re.compile(
    r"[%s]|[\U00020000-\U0002ffff]|[%s]|[A-Za-z0-9]+(?:[.'%%-][A-Za-z0-9]+)*" % (_CJK, _CJK_PUNCT)
)


def count_chars(text):
    """中文字符与全角标点各计 1；英文/数字串计 1；URL 不计。"""
    if not text:
        return 0
    text = RE_URL.sub(" ", text)
    return len(RE_COUNT.findall(text))


# ---------------------------------------------------------------- 违规模式

ACTION_WORDS = (
    "起立|站起|起身|坐下|拍桌|拍案|深呼吸|吸气|停顿|顿了顿|沉吟|沉默|微笑|苦笑|冷笑|大笑|笑着|笑了|轻笑|"
    "叹气|叹息|转向|看向|望向|扫视|环顾|举手|摊手|挥手|点头|摇头|皱眉|眉头|目光|眼神|语速|语气|声音|"
    "音量|压低|提高声|加重语气|放缓|哽咽|激动地|愤怒地|平静地|严肃地|掌声|鼓掌|全场|观众|翻开|拿起|"
    "推了推|稿纸|手势|稍作|片刻|稍顿|笑"
)
RE_BRACKET = re.compile(r"[（(]([^（）()\n]{1,30})[）)]")
RE_ACTION = re.compile(ACTION_WORDS)
RE_BRACKET_OK = re.compile(
    r"^(打岔\s*\d\s*/\s*\d|小结|兼.*|来源.*|出处.*|见.*|注.*|待核实|即.*|E\d+.*|R\d+.*|第\s*\d+\s*轮.*|"
    r"[\d\s.,%年月日万亿元~\-—–/]+|[A-Za-z][A-Za-z0-9 .&'\-]*)$"
)
PERSONAS = "黄执中|胡渐彪|马薇薇|庞颖|周玄毅|颜如晶|陈铭|詹青云"
RE_NARRATIVE = re.compile(
    r"(?:^|[。！？\n])\s*(?:%s|[正反]方[一二三四]辩)[^，。！？：:\n]{0,8}?"
    r"(站起|起身|起立|笑了|微笑着|看向|望向|扫视|环顾|沉默了|顿了顿|走到|拿起|推了推|整理了|清了清嗓子)" % PERSONAS
)
RE_ENV = re.compile(r"(现场|全场|会场|台下|观众席)[^，。！？]{0,4}(气氛|一片|鸦雀无声|掌声雷动|哗然|安静下来|笑声四起|沸腾)")
RE_META = re.compile(
    r"作为(一名|一个)?(AI|人工智能|语言模型)|作为[正反]方[一二三四]辩[，,]\s*我(现在)?(开始|来)|"
    r"以下是我的(申论|发言|质询|总结)|(下面|接下来)我(将|会)?(开始|进行)我的(申论|发言)"
)
RE_PLACEHOLDER = re.compile(r"\{[^{}\n]{1,40}\}|_{3,}|\bTODO\b|\bTBD\b|待补充|此处(填写|插入|补充)|XXX")
RE_CONTRACT_LINE = re.compile(r"【完成】([^\n`]*)")
RE_KV = re.compile(r"([^\s=]+)=([^\s]+)")
RE_QUOTE_SPAN = re.compile(r"“([^”\n]{8,80})”|「([^」\n]{8,80})」|\"([^\"\n]{8,80})\"")
RE_ATTRIB = re.compile(r"(对方|您方|贵方|反方|正方|刚才|刚刚|说|提到|认为|主张|讲)")
RE_NORM = re.compile(r"[\s，。！？、；：,.!?;:“”\"'‘’「」『』（）()《》\-—…·]+")


def _norm(s):
    return RE_NORM.sub("", s or "")


# ---------------------------------------------------------------- 块 → 发言

def _is_meta_quote(blk, idx, blocks):
    """标题下第一行 `> 时长 …` 之类的副标题不计入正文。"""
    if blk["type"] != "quote":
        return False
    t = blk["text"].strip()
    if blk.get("extract") or "【完成】" in t or "【校验】" in t:
        return True
    if re.match(r"^(时长|真实开会|计时|> ?时长)", t) or ("计时" in t and len(t) < 60):
        return True
    return False


def content_blocks(blocks):
    """返回参与计数/校验的块（剔除标题、分隔线、代码块、副标题、契约行、编排器提炼块）。"""
    out = []
    for idx, blk in enumerate(blocks):
        t = blk["type"]
        if t in ("heading", "hr", "code"):
            continue
        if _is_meta_quote(blk, idx, blocks):
            continue
        if t == "para" and re.match(r"^\s*`{0,3}\s*【(完成|校验)】", blk["text"]):
            continue
        out.append(blk)
    return out


def block_body(blk):
    if blk["type"] == "para" and blk.get("turn"):
        return mdblocks.plain_text(blk["turn"]["body"])
    if blk["type"] == "table":
        return "\n".join(" ".join(mdblocks.plain_text(c) for c in row) for row in blk.get("rows") or [])
    return mdblocks.plain_text(blk["text"])


def resolve_role(turn, doc_side, lineup):
    """把发言标签解析成 (side, pos)。标签缺阵营时用文档阵营 / 阵容表补全。"""
    side, pos = turn.get("side") or "", turn.get("pos") or ""
    if (not side or not pos) and lineup:
        name = turn.get("persona") or turn.get("label")
        for s, seats in lineup.items():
            for p, person in (seats or {}).items():
                if person and person in (name or ""):
                    side = side or s
                    pos = pos or p
    if not side and doc_side in ("正方", "反方"):
        side = doc_side
    return side, pos


def group_turns(blocks, doc_side=None, lineup=None):
    """把块序列合并成发言序列：带标签的段落开启新发言，紧随其后的无标签段落并入。"""
    turns = []
    for blk in content_blocks(blocks):
        turn = blk.get("turn") if blk["type"] == "para" else None
        if turn:
            side, pos = resolve_role(turn, doc_side, lineup)
            turns.append({
                "side": side, "pos": pos, "role": side + pos, "label": turn["label"],
                "note": turn.get("note", ""), "text": block_body(blk), "blocks": [blk["i"]],
            })
        elif turns and blk["type"] in ("para", "list_item", "quote"):
            turns[-1]["text"] += "\n" + block_body(blk)
            turns[-1]["blocks"].append(blk["i"])
    for t in turns:
        t["chars"] = count_chars(t["text"])
    return turns


# ---------------------------------------------------------------- 证据台账

def parse_ledger(text):
    """解析 evidence.md 表格 → {"verified": set(urls), "pending": set(urls), "rows": n}"""
    verified, pending, rows = set(), set(), 0
    if not text:
        return None
    for line in text.split("\n"):
        if not line.strip().startswith("|") or re.match(r"^\s*\|?\s*:?-{2,}", line):
            continue
        urls = RE_URL.findall(line)
        status_ok = ("✅" in line) or ("已核验" in line)
        if "状态" in line and "URL" in line.upper():
            continue
        rows += 1
        for u in urls:
            (verified if status_ok else pending).add(_url_key(u))
    return {"verified": verified, "pending": pending, "rows": rows}


def _url_key(u):
    u = u.strip().rstrip("/").rstrip("。，；：、！？.,;:!?）)」』】]")
    u = re.sub(r"^http://", "https://", u)
    return u


# ---------------------------------------------------------------- 主入口

def _chk(checks, level, code, msg, blocks=None):
    checks.append({"level": level, "code": code, "msg": msg, "blocks": sorted(set(blocks or []))})


def _chip(chips, label, value, ok):
    chips.append({"label": label, "value": value, "ok": ok})


def lint_text(text, spec=None, lineup=None, prior_text="", ledger=None):
    """校验一份 transcript。spec 为 presets.step_spec() 的结果（可为 None → 只做通用检查）。"""
    spec = spec or {}
    meta, blocks = mdblocks.parse_document(text)
    kind = spec.get("kind", meta.get("kind", "other"))
    doc_side = spec.get("side") or meta.get("side")
    checks, chips = [], []
    cblocks = content_blocks(blocks)
    body_text = "\n".join(block_body(b) for b in cblocks)
    chars = count_chars(body_text)
    min_chars = int(spec.get("min_chars") or 0)
    metrics = {"chars": chars, "min_chars": min_chars, "blocks": len(blocks)}

    # ---- 字数
    if min_chars:
        ok = chars >= min_chars
        _chip(chips, "字数", "%d/%d" % (chars, min_chars), ok)
        if not ok:
            _chk(checks, "error", "min_chars", "实测字数 %d < 下限 %d（%s）" % (chars, min_chars, spec.get("duration", "")))

    # ---- 通用违规（逐块）
    n_action = n_placeholder = 0
    for blk in blocks:
        raw = blk["text"] if blk["type"] != "table" else "\n".join(" ".join(r) for r in blk.get("rows") or [])
        if blk["type"] == "code":
            continue
        for m in RE_PLACEHOLDER.finditer(raw):
            n_placeholder += 1
            _chk(checks, "error", "placeholder", "未替换的占位符：%s" % m.group(0), [blk["i"]])
    for blk in cblocks:
        body = block_body(blk)
        for m in RE_BRACKET.finditer(body):
            inner = m.group(1).strip()
            if RE_BRACKET_OK.match(inner) or "http" in inner or "来源" in inner or "数据" in inner:
                continue
            if RE_ACTION.search(inner):
                n_action += 1
                _chk(checks, "error", "action_bracket", "动作/表情/语气括号：%s" % m.group(0), [blk["i"]])
        m = RE_NARRATIVE.search(body)
        if m:
            _chk(checks, "error", "narrative", "小说式旁白：…%s…" % body[max(0, m.start()):m.end() + 6].strip(), [blk["i"]])
        m = RE_META.search(body)
        if m:
            _chk(checks, "error", "meta_statement", "元说明：%s" % m.group(0), [blk["i"]])
        m = RE_ENV.search(body)
        if m:
            _chk(checks, "warn", "environment", "疑似环境描写：%s" % m.group(0), [blk["i"]])
    _chip(chips, "动作括号", str(n_action), n_action == 0)
    _chip(chips, "占位符", str(n_placeholder), n_placeholder == 0)

    # ---- URL / 证据台账
    urls = RE_URL.findall(text)
    metrics["urls"] = len(urls)
    min_urls = int(spec.get("min_urls") or 0)
    if min_urls:
        _chip(chips, "URL", "%d/%d" % (len(urls), min_urls), len(urls) >= min_urls)
        if len(urls) < min_urls:
            _chk(checks, "warn", "min_urls", "证据 URL %d 条，少于建议的 %d 条（无法检索的请标注【待核实】，不要编造）" % (len(urls), min_urls))
    elif urls:
        _chip(chips, "URL", str(len(urls)), True)
    if ledger is not None and urls:
        unknown = [u for u in urls if _url_key(u) not in ledger["verified"]]
        pending = [u for u in unknown if _url_key(u) in ledger["pending"]]
        missing = [u for u in unknown if _url_key(u) not in ledger["pending"]]
        if missing:
            _chk(checks, "warn", "ledger_missing", "%d 条 URL 未登记在证据台账 evidence.md：%s" % (len(missing), "；".join(missing[:3])))
        if pending:
            _chk(checks, "warn", "ledger_pending", "%d 条 URL 在台账中仍是「待核实」" % len(pending))
        metrics["urls_verified"] = len(urls) - len(unknown)

    # ---- 必备套语
    for phrase in spec.get("required_phrases") or []:
        alts = phrase.split("|")
        if not any(a in body_text for a in alts):
            _chk(checks, "warn", "phrase", "缺少真实辩场套语：%s" % " / ".join(alts))

    # ---- 分环节校验
    lineup = lineup or {}
    turns = group_turns(blocks, doc_side, lineup)
    metrics["turns"] = len(turns)

    if kind == "cross_exam":
        q_role, a_role = spec["questioner"], spec["respondent"]
        rounds, q_chars, short_answers = 0, 0, []
        pending_q = False
        for t in turns:
            if t["role"] == q_role:
                q_chars += t["chars"]
                if "小结" in t["note"] or "小结" in t["label"]:
                    pending_q = False
                    continue
                pending_q = True
            elif t["role"] == a_role:
                if pending_q:
                    rounds += 1
                    pending_q = False
                if t["chars"] < int(spec.get("answer_min_chars", 0)):
                    short_answers.extend(t["blocks"])
        metrics.update(rounds=rounds, questioner_chars=q_chars)
        need_r = int(spec.get("min_rounds", 0))
        need_q = int(spec.get("questioner_min_chars", 0))
        _chip(chips, "完整回合", "%d/%d" % (rounds, need_r), rounds >= need_r)
        _chip(chips, q_role + "字数", "%d/%d" % (q_chars, need_q), q_chars >= need_q)
        if rounds < need_r:
            _chk(checks, "error", "rounds", "完整问答回合 %d < %d（%s 问 → %s 答 计 1 回合）" % (rounds, need_r, q_role, a_role))
        if q_chars < need_q:
            _chk(checks, "error", "questioner_chars", "%s 发言字数 %d < %d" % (q_role, q_chars, need_q))
        if short_answers:
            _chk(checks, "warn", "short_answer", "%s 有 %d 次回答少于 %d 字（须实质回答）" % (a_role, len(short_answers), spec.get("answer_min_chars", 0)), short_answers)
        if turns and not any(t["role"] == q_role for t in turns):
            _chk(checks, "error", "roles", "没有识别到 %s 的发言（发言标签须形如 **%s · 姓名**：）" % (q_role, q_role))

    elif kind == "self_proof":
        prover, inter_side = spec["prover"], spec["interrupter_side"]
        segs = [t for t in turns if t["role"] == prover]
        inters = [t for t in turns if t["side"] == inter_side]
        p_chars = sum(t["chars"] for t in segs)
        short = [b for t in segs if t["chars"] < int(spec.get("segment_min_chars", 0)) for b in t["blocks"]]
        long_i = [b for t in inters if t["chars"] > int(spec.get("interrupt_max_chars", 999)) for b in t["blocks"]]
        metrics.update(segments=len(segs), prover_chars=p_chars, interrupts=len(inters))
        need_s, max_i = int(spec.get("min_segments", 0)), int(spec.get("interrupt_max", 99))
        _chip(chips, "自证段", "%d/%d" % (len(segs), need_s), len(segs) >= need_s)
        _chip(chips, "打岔", "%d/≤%d" % (len(inters), max_i), len(inters) <= max_i)
        if len(segs) < need_s:
            _chk(checks, "error", "segments", "自证段 %d < %d" % (len(segs), need_s))
        if short:
            _chk(checks, "warn", "short_segment", "%d 段自证少于 %d 字（≈30 秒）" % (len(set(short)), spec.get("segment_min_chars")), short)
        if len(inters) > max_i:
            _chk(checks, "error", "interrupts", "打岔 %d 次，超过上限 %d 次" % (len(inters), max_i), [b for t in inters for b in t["blocks"]])
        if long_i:
            _chk(checks, "error", "interrupt_len", "有打岔超过 %d 字（≈20 秒）" % spec.get("interrupt_max_chars"), long_i)

    elif kind == "free_debate":
        sides = [t["side"] for t in turns if t["side"] in ("正方", "反方")]
        n = len(sides)
        same = [turns[k]["blocks"][0] for k in range(1, len(turns))
                if turns[k]["side"] and turns[k]["side"] == turns[k - 1]["side"]]
        short = [t["blocks"][0] for t in turns if t["chars"] < int(spec.get("turn_min_chars", 0))]
        long_t = [t["blocks"][0] for t in turns if t["chars"] > int(spec.get("turn_max_chars", 9999))]
        metrics.update(free_turns=n, pro_turns=sides.count("正方"), con_turns=sides.count("反方"))
        lo, hi = int(spec.get("min_turns", 0)), int(spec.get("max_turns", 999))
        _chip(chips, "发言次数", "%d（%d–%d）" % (n, lo, hi), lo <= n <= hi)
        _chip(chips, "交替违规", str(len(same)), not same)
        if n < lo:
            _chk(checks, "error", "free_turns", "自由辩发言 %d 次 < %d 次" % (n, lo))
        if n > hi:
            _chk(checks, "warn", "free_turns_max", "自由辩发言 %d 次 > 上限 %d 次" % (n, hi))
        if same and spec.get("alternate"):
            _chk(checks, "error", "alternate", "自由辩须正反交替发言，有 %d 处同方连续发言" % len(same), same)
        if sides and spec.get("first_side") and sides[0] != spec["first_side"]:
            _chk(checks, "warn", "first_side", "自由辩应由%s先发言" % spec["first_side"])
        if short:
            _chk(checks, "warn", "turn_short", "%d 次发言少于 %d 字" % (len(short), spec.get("turn_min_chars")), short)
        if long_t:
            _chk(checks, "warn", "turn_long", "%d 次发言超过 %d 字（≈45 秒）" % (len(long_t), spec.get("turn_max_chars")), long_t)

    elif kind in ("meeting", "research"):
        need_t = int(spec.get("each_speaker_min_turns", 0))
        min_c = int(spec.get("turn_min_chars", 0))
        if need_t:
            counts = {}
            for t in turns:
                if t["pos"] and t["chars"] >= min_c:
                    counts[t["pos"]] = counts.get(t["pos"], 0) + 1
            lacking = [p for p in ("一辩", "二辩", "三辩", "四辩") if counts.get(p, 0) < need_t]
            metrics["speaker_turns"] = counts
            _chip(chips, "四人发言", "缺 %d 人" % len(lacking) if lacking else "齐", not lacking)
            if lacking:
                _chk(checks, "error", "speakers", "%s 实质发言（≥%d 字）不足 %d 次" % ("、".join(lacking), min_c, need_t))

    elif kind == "judge":
        if re.search(r"平局|难分伯仲|不分胜负|双方都很(好|精彩)", body_text):
            _chk(checks, "warn", "judge_draw", "评委必须判出胜负，不得和稀泥")

    # ---- 反稻草人：引用对方原话须能在前序发言中找到
    if prior_text and kind in ("speech", "cross_exam", "self_proof", "free_debate", "judge"):
        prior_norm = _norm(prior_text)
        bad = []
        for blk in cblocks:
            body = block_body(blk)
            for m in RE_QUOTE_SPAN.finditer(body):
                q = next(g for g in m.groups() if g)
                ctx = body[max(0, m.start() - 24):m.start()]
                if not RE_ATTRIB.search(ctx):
                    continue
                nq = _norm(q)
                if len(nq) >= 8 and nq not in prior_norm:
                    bad.append((blk["i"], q))
        if bad:
            _chk(checks, "warn", "quote_not_found",
                 "%d 处「对方原话」在前序发言中找不到（可能是稻草人或改写）：%s" % (len(bad), "；".join("「%s」" % q[:24] for _, q in bad[:3])),
                 [b for b, _ in bad])

    # ---- 自报契约 vs 实测
    m = RE_CONTRACT_LINE.search(text)
    if m:
        kv = dict(RE_KV.findall(m.group(1)))
        for key in ("字数", "总字数"):
            if key in kv and kv[key].isdigit():
                claimed = int(kv[key])
                if abs(claimed - chars) > max(30, chars * 0.1):
                    _chk(checks, "warn", "contract_mismatch", "【完成】自报%s=%d，实测 %d（以实测为准）" % (key, claimed, chars))
                break

    errors = sum(1 for c in checks if c["level"] == "error")
    warns = sum(1 for c in checks if c["level"] == "warn")
    verified = "【校验】%s 实测字数=%d/%d%s %s" % (
        spec.get("id", "?"), chars, min_chars, " ✓" if chars >= min_chars else " ✗",
        " ".join("%s=%s%s" % (c["label"], c["value"], "✓" if c["ok"] else "✗") for c in chips if c["label"] != "字数"),
    )
    verified += "  →  %s" % ("通过" if errors == 0 else "不通过（%d 项硬性问题）" % errors)
    return {
        "step": spec.get("id"),
        "kind": kind,
        "metrics": metrics,
        "chips": chips,
        "checks": checks,
        "errors": errors,
        "warnings": warns,
        "pass": errors == 0,
        "verified_line": verified,
    }
