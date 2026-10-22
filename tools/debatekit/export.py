"""导出：单文档 / 整场实录 / 全部稿件 → md · html · docx · zip。

「清理」(clean=True，默认) 会去掉：front matter、【完成】/【校验】契约行、【编排器·提炼】块，
使文件满足 rules/script_format.md §7「可直接 Word 打印」。
"""

import datetime as _dt
import html
import io
import os
import re
import zipfile

from . import docx, mdblocks, presets

DISCLAIMER = ("本文档由 Debate-Skills 以 AI 模拟生成：辩手为基于公开资料的风格模拟，发言内容不代表所涉真实人物的观点；"
              "标注【待核实】的数据须自行核验后再引用。")

RE_CONTRACT = re.compile(r"【(完成|校验)】")


def clean_markdown(text, strip_contracts=True, strip_extracts=True):
    meta, body, offset = mdblocks.split_front_matter(text)
    lines = body.split("\n")
    blocks = mdblocks.parse_blocks(body, 0)
    kept = []
    for blk in blocks:
        t = blk["type"]
        drop = False
        if strip_contracts:
            if t == "para" and re.match(r"^\s*`{0,3}\s*【(完成|校验)】", blk["text"]):
                drop = True
            if t == "code" and RE_CONTRACT.search(blk["text"]) and len(blk["text"].strip().split("\n")) <= 3:
                drop = True
            if t == "quote" and RE_CONTRACT.search(blk["text"]) and len(blk["text"]) < 300:
                drop = True
        if strip_extracts and t == "quote" and blk.get("extract"):
            drop = True
        if not drop:
            kept.append("\n".join(lines[blk["line_start"] - 1: blk["line_end"]]))
    out = "\n\n".join(kept).strip() + "\n"
    return out


def _lineup_table(session):
    lineup = session.lineup
    if not lineup:
        return ""
    rows = ["| 辩位 | 正方 | 反方 |", "|---|---|---|"]
    for pos in ("一辩", "二辩", "三辩", "四辩"):
        rows.append("| %s | %s | %s |" % (pos, (lineup.get("正方") or {}).get(pos, ""), (lineup.get("反方") or {}).get(pos, "")))
    return "\n".join(rows)


def _threads_md(threads, doc_key=None):
    items = []
    for th in threads:
        refs = th.get("refs") or []
        if doc_key and not any(r.get("key") == doc_key for r in refs):
            continue
        if not th.get("answer"):
            continue
        loc = "；".join("%s %s" % (r.get("key", ""), r.get("anchor", "")) for r in refs)
        quote = refs[0].get("quote", "") if refs else ""
        items.append("### %s（%s · %s）\n\n> 原文：「%s」\n\n**问 · %s**：%s\n\n**答 · %s**：\n\n%s\n" % (
            th.get("id", ""), loc, th.get("intent", "提问"), quote[:160], th.get("target", ""),
            th.get("question", ""), th.get("answered_by", th.get("target", "")), th.get("answer", "")))
    if not items:
        return ""
    return "## 附录 · 协同问答\n\n" + "\n".join(items)


def compile_transcript(session, clean=True, qa=False, evidence=True):
    """把会话中全部 transcript 按预设顺序汇编为一份实录。返回 (title, subtitle, meta_rows, body_md)。"""
    sides = session.meta.get("sides") or {}
    title = "辩论实录｜%s" % session.topic
    subtitle = "正方：%s　｜　反方：%s" % (sides.get("正方", "—"), sides.get("反方", "—"))
    label = (presets.load()["presets"].get(session.preset) or {}).get("label", session.preset)
    meta_rows = [
        ("辩题", session.topic),
        ("用户持方", session.user_side),
        ("赛制预设", label),
        ("运行模式", session.meta.get("mode", "—")),
        ("会话", session.id),
        ("导出时间", _dt.datetime.now().strftime("%Y-%m-%d %H:%M")),
    ]
    parts = []
    lt = _lineup_table(session)
    has_a = any(d.get("step") == "A" for d in session.list_docs())
    if lt and not has_a:
        parts.append("## 阵容\n\n" + lt)
    for d in session.list_docs():
        if d["group"] != "transcript":
            continue
        text = session.read(d)
        parts.append(clean_markdown(text) if clean else mdblocks.split_front_matter(text)[1])
    if evidence:
        for d in session.list_docs():
            if d["group"] == "evidence":
                ev = clean_markdown(session.read(d))
                ev = re.sub(r"^#\s+", "## 附录 · ", ev, count=1, flags=re.M)
                parts.append(ev)
    if qa:
        tq = _threads_md(session.threads())
        if tq:
            parts.append(tq)
    return title, subtitle, meta_rows, "\n\n---\n\n".join(p.strip() for p in parts if p.strip()) + "\n"


# ---------------------------------------------------------------- html

HTML_CSS = """
body{font-family:"Songti SC","Noto Serif CJK SC","Source Han Serif SC","SimSun",serif;max-width:820px;margin:40px auto;padding:0 28px;
color:#1f2328;line-height:1.85;font-size:16px}
h1,h2,h3,h4{font-family:"PingFang SC","Noto Sans CJK SC","Microsoft YaHei",sans-serif;line-height:1.4}
h1{font-size:26px;text-align:center;margin:8px 0 6px}h2{font-size:20px;margin-top:34px;border-bottom:1px solid #e5e7eb;padding-bottom:6px}
.subtitle{text-align:center;color:#555;margin:0 0 6px}.disclaimer{text-align:center;color:#888;font-size:12px;margin-bottom:24px}
blockquote{margin:12px 0;padding:6px 14px;border-left:4px solid #cfd5de;color:#555;background:#fafbfc}
.turn{margin:10px 0}.turn-label{font-weight:700;margin-right:2px}.turn.pro .turn-label{color:#9b2c2c}.turn.con .turn-label{color:#1f4e8c}
.turn-label:after{content:"："}.turn-note{color:#888;font-size:.9em}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}th,td{border:1px solid #c8ccd2;padding:6px 8px;vertical-align:top}
th{background:#eef1f5}.li{display:flex;gap:6px;margin:4px 0 4px calc(var(--indent,0)*1.4em + .4em)}.li-marker{color:#666;min-width:1.2em}
pre{background:#f4f5f7;padding:10px;overflow:auto;font-size:13px}code{font-family:Consolas,monospace}
hr{border:none;border-top:1px solid #e5e7eb;margin:28px 0}a{color:#1f4e8c}
@media print{body{margin:0;max-width:none}a{color:inherit;text-decoration:none}}
"""


def markdown_to_html(md_text, title="", subtitle="", disclaimer="", meta_rows=None):
    _, blocks = mdblocks.parse_document(md_text)
    head = []
    if title:
        head.append("<h1>%s</h1>" % html.escape(title))
    if subtitle:
        head.append('<p class="subtitle">%s</p>' % html.escape(subtitle))
    if disclaimer:
        head.append('<p class="disclaimer">%s</p>' % html.escape(disclaimer))
    if meta_rows:
        head.append("<table>%s</table>" % "".join(
            "<tr><th>%s</th><td>%s</td></tr>" % (html.escape(k), html.escape(str(v))) for k, v in meta_rows))
    body = "\n".join(mdblocks.block_html(b) for b in blocks)
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>%s</title><style>%s</style></head>'
            "<body>%s\n%s</body></html>" % (html.escape(title or "Debate"), HTML_CSS, "\n".join(head), body))


# ---------------------------------------------------------------- 单文档 / 整场

def _safe_name(name):
    return re.sub(r"[\\/:*?\"<>|\n]+", "-", name).strip() or "export"


def export_doc(session, doc, fmt="docx", clean=True, qa=False, disclaimer=True):
    text = session.read(doc)
    md = clean_markdown(text) if clean else mdblocks.split_front_matter(text)[1]
    if qa:
        tq = _threads_md(session.threads(), doc["key"])
        if tq:
            md = md.rstrip() + "\n\n---\n\n" + tq
    base = _safe_name(os.path.basename(doc["path"])[:-3])
    disc = DISCLAIMER if disclaimer and doc["group"] in ("transcript", "artifact") else ""
    if fmt == "md":
        if disc:
            md = "> %s\n\n%s" % (disc, md)
        return base + ".md", md.encode("utf-8"), "text/markdown; charset=utf-8"
    if fmt == "html":
        return base + ".html", markdown_to_html(md, disclaimer=disc).encode("utf-8"), "text/html; charset=utf-8"
    data = docx.markdown_to_docx(md, disclaimer=disc)
    return base + ".docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def export_transcript(session, fmt="docx", clean=True, qa=False, disclaimer=True):
    title, subtitle, meta_rows, body = compile_transcript(session, clean=clean, qa=qa)
    disc = DISCLAIMER if disclaimer else ""
    base = _safe_name("辩论实录-" + session.topic)
    if fmt == "md":
        meta = "\n".join("| %s | %s |" % (k, v) for k, v in meta_rows)
        md = "# %s\n\n> %s\n\n%s| 项目 | 内容 |\n|---|---|\n%s\n\n%s" % (
            title, subtitle, ("> %s\n\n" % disc) if disc else "", meta, body)
        return base + ".md", md.encode("utf-8"), "text/markdown; charset=utf-8"
    if fmt == "html":
        return base + ".html", markdown_to_html(body, title, subtitle, disc, meta_rows).encode("utf-8"), "text/html; charset=utf-8"
    data = docx.markdown_to_docx(body, title=title, subtitle=subtitle, disclaimer=disc, meta_rows=meta_rows)
    return base + ".docx", data, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def export_zip(session, clean=True, qa=False, disclaimer=True):
    buf = io.BytesIO()
    root = _safe_name(session.id)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for fmt in ("docx", "md"):
            name, data, _ = export_transcript(session, fmt, clean, qa, disclaimer)
            z.writestr("%s/%s" % (root, name), data)
        for d in session.list_docs():
            if d["group"] == "artifact":
                for fmt in ("docx", "md"):
                    name, data, _ = export_doc(session, d, fmt, clean, qa, disclaimer)
                    z.writestr("%s/稿件/%s" % (root, name), data)
            elif d["group"] == "transcript":
                name, data, _ = export_doc(session, d, "docx", clean, qa, disclaimer)
                z.writestr("%s/逐轮实录/%s" % (root, name), data)
            elif d["group"] == "evidence":
                z.writestr("%s/%s" % (root, os.path.basename(d["path"])), session.read(d).encode("utf-8"))
    return _safe_name(session.id) + ".zip", buf.getvalue(), "application/zip"
