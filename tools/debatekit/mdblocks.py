"""Markdown → 块（block）切分 + 行内渲染。

设计目标：
1. **稳定锚点**：每个块按出现顺序编号 b1, b2, ...；网页、定位 CLI、lint、导出共用本模块，
   因此网页上「复制位置」得到的 R02#b5 与 Agent 端 `debate_ctl.py locate` 解析出的位置严格一致。
2. **发言识别**：形如 `**反方四辩 · 马薇薇**：……` 或 `**正方二辩 · 庞颖**（打岔 1/3）：……`
   的段落被识别为「发言」（turn），带 side / pos / persona / note 字段。
3. 只覆盖辩论稿件实际用到的 Markdown 子集：标题、段落、列表项、引用、表格、代码块、分隔线。
"""

import html
import re

# ---------------------------------------------------------------- front matter

def split_front_matter(text):
    """返回 (meta: dict, body: str, body_line_offset: int)。

    只支持简单的 `key: value` 与 `key: [a, b]`，足够 transcript 文件使用。
    """
    if not text.startswith("---"):
        return {}, text, 0
    lines = text.split("\n")
    if lines[0].strip() != "---":
        return {}, text, 0
    for idx in range(1, min(len(lines), 60)):
        if lines[idx].strip() == "---":
            meta = {}
            for raw in lines[1:idx]:
                if ":" not in raw or raw.lstrip().startswith("#"):
                    continue
                key, val = raw.split(":", 1)
                key, val = key.strip(), val.strip()
                if val.startswith("[") and val.endswith("]"):
                    val = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]
                else:
                    val = val.strip("'\"")
                meta[key] = val
            body = "\n".join(lines[idx + 1:])
            return meta, body, idx + 1
    return {}, text, 0


# ---------------------------------------------------------------- block parsing

RE_FENCE = re.compile(r"^\s*(```|~~~)")
RE_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
RE_HR = re.compile(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$")
RE_LIST = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)、])\s+(.*)$")
RE_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
RE_QUOTE = re.compile(r"^\s{0,3}>\s?(.*)$")

# 发言标签：**标签**（可选备注）：正文
RE_TURN = re.compile(
    r"^\*\*(?P<label>[^*\n]{1,48}?)\*\*\s*(?:[（(](?P<note>[^）)\n]{1,24})[）)])?\s*[：:]\s*(?P<text>.*)$",
    re.S,
)
RE_SIDE = re.compile(r"(正方|反方)")
RE_POS = re.compile(r"([一二三四])辩")
RE_NOTE_IN_LABEL = re.compile(r"[（(]([^）)]{1,24})[）)]")
ROLE_WORDS = ("主席", "评委", "主持人", "编排器", "教练", "裁判", "计时员", "观众")

# 会被导出时清理的契约 / 编排器块
RE_CONTRACT = re.compile(r"^\s*(?:`{0,3})\s*【(完成|校验)】")
RE_EXTRACT = re.compile(r"^\**\s*【编排器[·・]?提炼】")


def _is_table_start(lines, i):
    return (
        i + 1 < len(lines)
        and lines[i].lstrip().startswith("|")
        and RE_TABLE_SEP.match(lines[i + 1] or "") is not None
    )


def _starts_block(line, lines, i):
    if not line.strip():
        return True
    return bool(
        RE_FENCE.match(line)
        or RE_HEADING.match(line)
        or RE_HR.match(line)
        or RE_LIST.match(line)
        or RE_QUOTE.match(line)
        or _is_table_start(lines, i)
    )


def parse_turn(text):
    """若段落是一条发言，返回 dict(label, side, pos, persona, note, body)，否则 None。"""
    m = RE_TURN.match(text.strip())
    if not m:
        return None
    label = m.group("label").strip()
    notes = []
    for nm in RE_NOTE_IN_LABEL.finditer(label):
        notes.append(nm.group(1).strip())
    clean_label = RE_NOTE_IN_LABEL.sub("", label).strip()
    if m.group("note"):
        notes.append(m.group("note").strip())
    side_m = RE_SIDE.search(clean_label)
    pos_m = RE_POS.search(clean_label)
    is_role = any(w in clean_label for w in ROLE_WORDS)
    if not (side_m or pos_m or is_role or "·" in clean_label or "・" in clean_label):
        return None  # 例如 **判断标准**：…… 只是加粗小标题，不是发言
    persona = ""
    for sep in ("·", "・", "•", "|", "｜"):
        if sep in clean_label:
            persona = clean_label.split(sep, 1)[1].strip()
            break
    return {
        "label": clean_label,
        "side": side_m.group(1) if side_m else "",
        "pos": (pos_m.group(1) + "辩") if pos_m else "",
        "persona": persona,
        "note": "；".join(notes),
        "body": m.group("text").strip(),
    }


def parse_blocks(body, line_offset=0):
    """把 Markdown 正文切成块列表。

    每个块：{i, type, text, line_start, line_end, ...}
      type ∈ heading | para | list_item | quote | table | code | hr
      heading: level, title
      list_item: ordered, indent, marker
      table: rows (list[list[str]])，首行为表头
      code: lang
      para: turn (dict|None)
      quote: extract (bool) —— 是否【编排器·提炼】块
    """
    lines = body.split("\n")
    blocks = []
    i = 0
    n = len(lines)

    def add(btype, start, end, text, **extra):
        blk = {
            "i": len(blocks) + 1,
            "type": btype,
            "text": text,
            "line_start": start + 1 + line_offset,
            "line_end": end + 1 + line_offset,
        }
        blk.update(extra)
        blocks.append(blk)

    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        # fenced code
        fm = RE_FENCE.match(line)
        if fm:
            fence = fm.group(1)
            lang = line.strip()[3:].strip()
            j = i + 1
            while j < n and not lines[j].strip().startswith(fence):
                j += 1
            content = "\n".join(lines[i + 1:j])
            add("code", i, min(j, n - 1), content, lang=lang)
            i = j + 1
            continue

        hm = RE_HEADING.match(line)
        if hm:
            add("heading", i, i, line.strip(), level=len(hm.group(1)), title=hm.group(2).strip())
            i += 1
            continue

        if RE_HR.match(line):
            add("hr", i, i, line.strip())
            i += 1
            continue

        if _is_table_start(lines, i):
            j = i
            rows = []
            while j < n and lines[j].lstrip().startswith("|"):
                if j != i + 1:  # 跳过分隔行
                    raw = lines[j].strip()
                    if raw.startswith("|"):
                        raw = raw[1:]
                    if raw.endswith("|") and not raw.endswith("\\|"):
                        raw = raw[:-1]
                    cells = [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", raw)]
                    rows.append(cells)
                j += 1
            add("table", i, j - 1, "\n".join(lines[i:j]), rows=rows)
            i = j
            continue

        qm = RE_QUOTE.match(line)
        if qm:
            j = i
            inner = []
            while j < n and RE_QUOTE.match(lines[j]):
                inner.append(RE_QUOTE.match(lines[j]).group(1))
                j += 1
            inner_text = "\n".join(inner).strip("\n")
            add("quote", i, j - 1, inner_text, extract=bool(RE_EXTRACT.match(inner_text.strip())))
            i = j
            continue

        lm = RE_LIST.match(line)
        if lm:
            indent = len(lm.group(1).replace("\t", "    "))
            marker = lm.group(2)
            j = i + 1
            content = [lm.group(3)]
            while j < n and lines[j].strip() and not _starts_block(lines[j], lines, j):
                content.append(lines[j].strip())
                j += 1
            # 缩进的续行（非新列表项）也并入
            add(
                "list_item", i, j - 1, "\n".join(content),
                ordered=marker[0].isdigit(), indent=indent // 2, marker=marker,
            )
            i = j
            continue

        # paragraph
        j = i + 1
        content = [line.rstrip()]
        while j < n and lines[j].strip() and not _starts_block(lines[j], lines, j):
            content.append(lines[j].rstrip())
            j += 1
        text = "\n".join(content).strip()
        add("para", i, j - 1, text, turn=parse_turn(text))
        i = j

    return blocks


def parse_document(text):
    """便捷函数：返回 (front_matter, blocks)。"""
    meta, body, offset = split_front_matter(text)
    return meta, parse_blocks(body, offset)


# ---------------------------------------------------------------- inline runs

RE_INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)"
    r"|(?P<link>\[(?P<ltext>[^\]\n]+)\]\((?P<lurl>[^)\s]+)\))"
    r"|(?P<auto>(?:https?|debate)://[^\s<>（）()「」\"“”'，。；！？、]+)"
    r"|(?P<bold>\*\*)"
    r"|(?P<em>\*)"
    r"|(?P<br>\n)"
)

_TRAIL = "。，；：、！？.,;:!?）)」』】]"


def inline_runs(text):
    """把一段行内 Markdown 转成 runs：[{t, b, i, code, href, br}]。"""
    runs = []
    bold = False
    italic = False
    # 不成对的 ** / * 视为字面量
    allow_bold = text.count("**") % 2 == 0
    single = len(re.findall(r"(?<!\*)\*(?!\*)", text))
    allow_em = single % 2 == 0
    pos = 0

    def push(t, **kw):
        if not t and not kw.get("br"):
            return
        run = {"t": t, "b": bold, "i": italic}
        run.update(kw)
        runs.append(run)

    for m in RE_INLINE.finditer(text):
        if m.start() > pos:
            push(text[pos:m.start()])
        kind = m.lastgroup
        if m.group("code"):
            push(m.group("code")[1:-1], code=True)
        elif m.group("link"):
            push(m.group("ltext"), href=m.group("lurl"))
        elif m.group("auto"):
            url = m.group("auto")
            tail = ""
            while url and url[-1] in _TRAIL:
                tail = url[-1] + tail
                url = url[:-1]
            push(url, href=url)
            if tail:
                push(tail)
        elif m.group("bold"):
            if allow_bold:
                bold = not bold
            else:
                push("**")
        elif m.group("em"):
            if allow_em:
                italic = not italic
            else:
                push("*")
        elif m.group("br"):
            push("", br=True)
        else:  # pragma: no cover
            push(m.group(0))
        pos = m.end()
        del kind
    if pos < len(text):
        push(text[pos:])
    return runs


def runs_to_html(runs):
    out = []
    for r in runs:
        if r.get("br"):
            out.append("<br>")
            continue
        t = html.escape(r["t"])
        if r.get("code"):
            t = "<code>%s</code>" % t
        if r.get("href"):
            href = r["href"]
            if href.startswith("debate://"):
                t = '<a class="dref" href="#" data-ref="%s">%s</a>' % (html.escape(href, quote=True), t)
            else:
                t = '<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (
                    html.escape(href, quote=True), t)
        if r.get("i"):
            t = "<em>%s</em>" % t
        if r.get("b"):
            t = "<strong>%s</strong>" % t
        out.append(t)
    return "".join(out)


def inline_html(text):
    return runs_to_html(inline_runs(text))


def plain_text(text):
    """去掉行内 Markdown 标记，得到纯文本（用于引用、搜索、字数）。"""
    return "".join("\n" if r.get("br") else r["t"] for r in inline_runs(text))


# ---------------------------------------------------------------- block → html

def block_html(blk):
    t = blk["type"]
    if t == "heading":
        lv = min(max(blk["level"], 1), 6)
        return "<h%d>%s</h%d>" % (lv, inline_html(blk["title"]), lv)
    if t == "para":
        turn = blk.get("turn")
        if turn:
            note = ('<span class="turn-note">（%s）</span>' % html.escape(turn["note"])) if turn["note"] else ""
            side_cls = {"正方": "pro", "反方": "con"}.get(turn["side"], "neutral")
            return (
                '<div class="turn %s"><span class="turn-label">%s</span>%s'
                '<span class="turn-body">%s</span></div>'
                % (side_cls, html.escape(turn["label"]), note, inline_html(turn["body"]))
            )
        return "<p>%s</p>" % inline_html(blk["text"])
    if t == "list_item":
        marker = blk["marker"] if blk["ordered"] else "•"
        return '<div class="li" style="--indent:%d"><span class="li-marker">%s</span><span>%s</span></div>' % (
            blk.get("indent", 0), html.escape(marker), inline_html(blk["text"]))
    if t == "quote":
        cls = "quote extract" if blk.get("extract") else "quote"
        return '<blockquote class="%s">%s</blockquote>' % (cls, inline_html(blk["text"]))
    if t == "table":
        rows = blk.get("rows") or []
        if not rows:
            return ""
        head = "".join("<th>%s</th>" % inline_html(c) for c in rows[0])
        body = "".join(
            "<tr>%s</tr>" % "".join("<td>%s</td>" % inline_html(c) for c in row) for row in rows[1:]
        )
        return '<div class="table-wrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, body)
    if t == "code":
        return "<pre><code>%s</code></pre>" % html.escape(blk["text"])
    if t == "hr":
        return "<hr>"
    return "<p>%s</p>" % html.escape(blk.get("text", ""))


def block_plain(blk):
    """块的纯文本（引用 / 搜索用）。"""
    t = blk["type"]
    if t == "heading":
        return plain_text(blk["title"])
    if t == "para" and blk.get("turn"):
        return plain_text(blk["turn"]["body"])
    if t == "table":
        return "\n".join(" | ".join(plain_text(c) for c in row) for row in blk.get("rows") or [])
    if t == "code":
        return blk["text"]
    if t == "hr":
        return ""
    return plain_text(blk["text"])
