"""纯标准库 .docx 写出器（OOXML，Word / WPS / LibreOffice 均可打开）。

- 中文排版：正文 宋体 小四（12pt）1.5 倍行距；标题 黑体；引用 楷体；A4；页脚「第 X 页 / 共 Y 页」
- 支持：标题、段落（含发言标签着色）、列表、引用、表格、代码块、分隔线、超链接、粗体/斜体/行内代码
"""

import datetime as _dt
import io
import re
import zipfile
from xml.sax.saxutils import escape as _esc

from . import mdblocks

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RE_BAD_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")

PAGE_W, PAGE_H, MARGIN_LR, MARGIN_TB = 11906, 16838, 1588, 1440
TEXT_W = PAGE_W - 2 * MARGIN_LR
SIDE_COLOR = {"正方": "9B2C2C", "反方": "1F4E8C"}


def x(s):
    return _esc(RE_BAD_XML.sub("", s or ""), {'"': "&quot;"})


def _t(text):
    return '<w:t xml:space="preserve">%s</w:t>' % x(text)


class DocxBuilder(object):
    def __init__(self, title="", author="Debate-Skills"):
        self.title = title
        self.author = author
        self.body = []
        self.links = []  # (rid, url)

    # ------------------------------------------------------------ runs
    def _rid_for(self, url):
        for rid, u in self.links:
            if u == url:
                return rid
        rid = "rIdL%d" % (len(self.links) + 1)
        self.links.append((rid, url))
        return rid

    def runs_xml(self, runs, base_rpr=""):
        out = []
        for r in runs:
            if r.get("br"):
                out.append("<w:r><w:br/></w:r>")
                continue
            # rPr 子元素必须按 OOXML 规定顺序：rFonts → b → i → color → sz → u → shd
            rpr = ""
            if r.get("code"):
                rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="等线"/>'
            if r.get("b"):
                rpr += "<w:b/><w:bCs/>"
            if r.get("i"):
                rpr += "<w:i/><w:iCs/>"
            rpr += base_rpr
            if r.get("code"):
                rpr += '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>'
            href = r.get("href")
            if href and not href.startswith("debate://"):
                rid = self._rid_for(href)
                out.append('<w:hyperlink r:id="%s" w:history="1"><w:r><w:rPr><w:rStyle w:val="Hyperlink"/>%s</w:rPr>%s</w:r></w:hyperlink>'
                           % (rid, rpr, _t(r["t"])))
            else:
                out.append("<w:r>%s%s</w:r>" % ("<w:rPr>%s</w:rPr>" % rpr if rpr else "", _t(r["t"])))
        return "".join(out)

    # ------------------------------------------------------------ paragraphs
    def para(self, runs, style=None, align=None, extra_ppr="", base_rpr=""):
        if isinstance(runs, str):
            runs = mdblocks.inline_runs(runs)
        ppr = ""
        if style:
            ppr += '<w:pStyle w:val="%s"/>' % style
        ppr += extra_ppr
        if align:
            ppr += '<w:jc w:val="%s"/>' % align
        self.body.append("<w:p>%s%s</w:p>" % ("<w:pPr>%s</w:pPr>" % ppr if ppr else "", self.runs_xml(runs, base_rpr)))

    def heading(self, text, level):
        level = min(max(int(level), 1), 4)
        self.para(mdblocks.inline_runs(text), style="Heading%d" % level)

    def turn(self, turn):
        color = SIDE_COLOR.get(turn.get("side"), "333333")
        label = turn["label"] + ("（%s）" % turn["note"] if turn.get("note") else "") + "："
        head = '<w:r><w:rPr><w:b/><w:bCs/><w:color w:val="%s"/></w:rPr>%s</w:r>' % (color, _t(label))
        body = self.runs_xml(mdblocks.inline_runs(turn["body"]))
        self.body.append('<w:p><w:pPr><w:pStyle w:val="Turn"/></w:pPr>%s%s</w:p>' % (head, body))

    def list_item(self, text, marker, indent=0):
        left = 420 + 420 * int(indent or 0)
        ppr = '<w:ind w:left="%d" w:hanging="300"/>' % left
        runs = [{"t": marker + " ", "b": False, "i": False}] + mdblocks.inline_runs(text)
        self.para(runs, style="ListPara", extra_ppr=ppr)

    def quote(self, text):
        self.para(mdblocks.inline_runs(text), style="QuoteBlock")

    def code(self, text):
        runs = []
        for k, line in enumerate(text.split("\n")):
            if k:
                runs.append({"t": "", "br": True})
            runs.append({"t": line, "b": False, "i": False})
        self.para(runs, style="CodeBlock")

    def hr(self):
        self.body.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" w:sz="6" w:space="1" w:color="BFBFBF"/></w:pBdr>'
                         '<w:spacing w:before="0" w:after="120"/></w:pPr></w:p>')

    def page_break(self):
        self.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    def table(self, rows):
        if not rows:
            return
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        widths = _column_widths(rows, ncol)
        grid = "".join('<w:gridCol w:w="%d"/>' % w for w in widths)
        border = "".join('<w:%s w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>' % b
                         for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
        out = ['<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:tblBorders>%s</w:tblBorders>'
               '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
               '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr>'
               '<w:tblGrid>%s</w:tblGrid>' % (sum(widths), border, grid)]
        for ri, row in enumerate(rows):
            trpr = "<w:trPr><w:tblHeader/><w:cantSplit/></w:trPr>" if ri == 0 else "<w:trPr><w:cantSplit/></w:trPr>"
            cells = []
            for ci, cell in enumerate(row):
                shd = '<w:shd w:val="clear" w:color="auto" w:fill="E8ECF2"/>' if ri == 0 else ""
                runs = mdblocks.inline_runs(cell)
                if ri == 0:
                    for r in runs:
                        r["b"] = True
                cells.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s</w:tcPr>'
                             '<w:p><w:pPr><w:pStyle w:val="TableText"/></w:pPr>%s</w:p></w:tc>'
                             % (widths[ci], shd, self.runs_xml(runs)))
            out.append("<w:tr>%s%s</w:tr>" % (trpr, "".join(cells)))
        out.append("</w:tbl>")
        self.body.append("".join(out))
        self.body.append('<w:p><w:pPr><w:spacing w:before="0" w:after="60"/></w:pPr></w:p>')

    # ------------------------------------------------------------ markdown
    def add_markdown(self, md_text, heading_shift=0):
        _, blocks = mdblocks.parse_document(md_text)
        for blk in blocks:
            t = blk["type"]
            if t == "heading":
                self.heading(blk["title"], blk["level"] + heading_shift)
            elif t == "para":
                if blk.get("turn"):
                    self.turn(blk["turn"])
                else:
                    self.para(mdblocks.inline_runs(blk["text"]), style="BodyText")
            elif t == "list_item":
                self.list_item(blk["text"], blk["marker"] if blk["ordered"] else "•", blk.get("indent", 0))
            elif t == "quote":
                self.quote(blk["text"])
            elif t == "table":
                self.table(blk.get("rows") or [])
            elif t == "code":
                self.code(blk["text"])
            elif t == "hr":
                self.hr()

    # ------------------------------------------------------------ package
    def _document_xml(self):
        sect = ('<w:sectPr><w:footerReference w:type="default" r:id="rIdFooter1"/>'
                '<w:pgSz w:w="%d" w:h="%d"/><w:pgMar w:top="%d" w:right="%d" w:bottom="%d" w:left="%d" '
                'w:header="851" w:footer="851" w:gutter="0"/><w:cols w:space="425"/></w:sectPr>'
                % (PAGE_W, PAGE_H, MARGIN_TB, MARGIN_LR, MARGIN_TB, MARGIN_LR))
        body = "".join(self.body) or "<w:p/>"
        if not body.endswith("</w:p>"):
            body += "<w:p/>"
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="%s" xmlns:r="%s"><w:body>%s%s</w:body></w:document>'
                % (W_NS, R_NS, body, sect))

    def _rels_xml(self):
        rels = [
            '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rIdSettings" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>',
            '<Relationship Id="rIdFooter1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>',
        ]
        for rid, url in self.links:
            rels.append('<Relationship Id="%s" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                        'Target="%s" TargetMode="External"/>' % (rid, x(url)))
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>' % "".join(rels))

    def build(self):
        now = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", CONTENT_TYPES)
            z.writestr("_rels/.rels", ROOT_RELS)
            z.writestr("word/document.xml", self._document_xml())
            z.writestr("word/styles.xml", STYLES)
            z.writestr("word/settings.xml", SETTINGS)
            z.writestr("word/footer1.xml", FOOTER)
            z.writestr("word/_rels/document.xml.rels", self._rels_xml())
            z.writestr("docProps/core.xml", CORE % (x(self.title), x(self.author), now, now))
            z.writestr("docProps/app.xml", APP)
        return buf.getvalue()


def _em(text):
    """估算文本在 10.5pt 下的宽度（单位：em）：中文 1.0，ASCII 0.55。"""
    w = 0.0
    for ch in text:
        w += 0.55 if ord(ch) < 0x2E80 else 1.0
    return w


def _column_widths(rows, ncol):
    """按内容估算列宽：短列（ID、状态等）给足自然宽度，长列按比例分配剩余宽度。"""
    em = 210  # 10.5pt ≈ 210 twips
    pad = 1.2
    natural = []
    for c in range(ncol):
        need = 0.0
        for r in rows:
            txt = mdblocks.plain_text(r[c])
            longest_line = max((_em(line) for line in txt.split("\n")), default=0.0)
            need = max(need, min(longest_line, 22.0))
        natural.append(max(need, 2.0) + pad)
    total = sum(natural) * em
    if total <= TEXT_W:
        scale = TEXT_W / float(total)
        return [int(n * em * scale) for n in natural]
    short = [n <= 6.5 for n in natural]
    fixed = sum(n * em for n, sh in zip(natural, short) if sh)
    flex_total = sum(n for n, sh in zip(natural, short) if not sh) or 1.0
    remain = max(TEXT_W - fixed, TEXT_W * 0.35)
    widths = []
    for n, sh in zip(natural, short):
        widths.append(int(n * em) if sh else int(remain * n / flex_total))
    k = TEXT_W / float(sum(widths))
    if k < 1:
        widths = [int(w * k) for w in widths]
    return widths


def markdown_to_docx(md_text, title="", subtitle="", disclaimer="", meta_rows=None):
    b = DocxBuilder(title=title)
    if title:
        b.para([{"t": title, "b": False, "i": False}], style="Title")
    if subtitle:
        b.para([{"t": subtitle, "b": False, "i": False}], style="Subtitle")
    if disclaimer:
        b.para([{"t": disclaimer, "b": False, "i": False}], style="Disclaimer")
    if meta_rows:
        b.table([["项目", "内容"]] + [[k, v] for k, v in meta_rows])
    b.add_markdown(md_text)
    return b.build()


# ---------------------------------------------------------------- static parts

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

SETTINGS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:defaultTabStop w:val="420"/><w:characterSpacingControl w:val="compressPunctuation"/>
<w:compat><w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/></w:compat>
</w:settings>"""

FOOTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:p><w:pPr><w:pStyle w:val="Footer"/><w:jc w:val="center"/></w:pPr>
<w:r><w:t xml:space="preserve">第 </w:t></w:r><w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>
<w:r><w:t xml:space="preserve"> 页 / 共 </w:t></w:r><w:fldSimple w:instr=" NUMPAGES "><w:r><w:t>1</w:t></w:r></w:fldSimple>
<w:r><w:t xml:space="preserve"> 页</w:t></w:r></w:p>
</w:ftr>"""

CORE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>%s</dc:title><dc:creator>%s</dc:creator>
<dcterms:created xsi:type="dcterms:W3CDTF">%s</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">%s</dcterms:modified>
</cp:coreProperties>"""

APP = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Debate-Skills collab</Application></Properties>"""


def _style(sid, name, ppr="", rpr="", based="Normal", typ="paragraph", nxt=None, extra=""):
    return ('<w:style w:type="%s" w:styleId="%s"><w:name w:val="%s"/>%s%s%s<w:qFormat/>%s%s</w:style>'
            % (typ, sid, name, '<w:basedOn w:val="%s"/>' % based if based else "",
               '<w:next w:val="%s"/>' % nxt if nxt else "", extra,
               "<w:pPr>%s</w:pPr>" % ppr if ppr else "", "<w:rPr>%s</w:rPr>" % rpr if rpr else ""))


_HEI = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="黑体" w:cs="Arial"/>'
_KAI = '<w:rFonts w:eastAsia="楷体"/>'

STYLES = ("""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体" w:cs="Times New Roman"/>
<w:sz w:val="24"/><w:szCs w:val="24"/><w:lang w:val="en-US" w:eastAsia="zh-CN"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="both"/></w:pPr></w:style>
""" + _style("BodyText", "Body Text", ppr='<w:ind w:firstLineChars="200" w:firstLine="480"/>')
    + _style("Turn", "Debate Turn", ppr='<w:spacing w:after="100"/>')
    + _style("ListPara", "List Paragraph", ppr='<w:spacing w:after="60"/>')
    + _style("Title", "Title", ppr='<w:spacing w:before="120" w:after="200"/><w:jc w:val="center"/>',
             rpr=_HEI + '<w:b/><w:bCs/><w:sz w:val="40"/><w:szCs w:val="40"/>', nxt="Normal")
    + _style("Subtitle", "Subtitle", ppr='<w:spacing w:after="160"/><w:jc w:val="center"/>',
             rpr=_KAI + '<w:color w:val="595959"/><w:sz w:val="24"/>', nxt="Normal")
    + _style("Disclaimer", "Disclaimer", ppr='<w:spacing w:after="240"/><w:jc w:val="center"/>',
             rpr=_KAI + '<w:color w:val="7F7F7F"/><w:sz w:val="18"/><w:szCs w:val="18"/>')
    + _style("Heading1", "heading 1", ppr='<w:keepNext/><w:keepLines/><w:spacing w:before="360" w:after="160"/><w:jc w:val="left"/><w:outlineLvl w:val="0"/>',
             rpr=_HEI + '<w:b/><w:bCs/><w:sz w:val="32"/><w:szCs w:val="32"/>', nxt="Normal")
    + _style("Heading2", "heading 2", ppr='<w:keepNext/><w:keepLines/><w:spacing w:before="300" w:after="120"/><w:jc w:val="left"/><w:outlineLvl w:val="1"/>',
             rpr=_HEI + '<w:b/><w:bCs/><w:sz w:val="28"/><w:szCs w:val="28"/>', nxt="Normal")
    + _style("Heading3", "heading 3", ppr='<w:keepNext/><w:keepLines/><w:spacing w:before="200" w:after="80"/><w:jc w:val="left"/><w:outlineLvl w:val="2"/>',
             rpr=_HEI + '<w:b/><w:bCs/><w:sz w:val="24"/><w:szCs w:val="24"/>', nxt="Normal")
    + _style("Heading4", "heading 4", ppr='<w:keepNext/><w:spacing w:before="160" w:after="60"/><w:jc w:val="left"/><w:outlineLvl w:val="3"/>',
             rpr=_HEI + '<w:sz w:val="24"/><w:szCs w:val="24"/>', nxt="Normal")
    + _style("QuoteBlock", "Quote Block",
             ppr='<w:pBdr><w:left w:val="single" w:sz="18" w:space="8" w:color="C9CED6"/></w:pBdr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/><w:ind w:left="300"/>',
             rpr=_KAI + '<w:color w:val="555555"/><w:sz w:val="21"/><w:szCs w:val="21"/>')
    + _style("CodeBlock", "Code Block",
             ppr='<w:shd w:val="clear" w:color="auto" w:fill="F4F5F7"/><w:spacing w:after="120" w:line="260" w:lineRule="auto"/><w:jc w:val="left"/>',
             rpr='<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:eastAsia="等线"/><w:sz w:val="18"/><w:szCs w:val="18"/>')
    + _style("TableText", "Table Text", ppr='<w:spacing w:after="0" w:line="300" w:lineRule="auto"/><w:jc w:val="left"/>',
             rpr='<w:sz w:val="21"/><w:szCs w:val="21"/>')
    + _style("Footer", "footer", ppr='<w:jc w:val="center"/>', rpr='<w:color w:val="7F7F7F"/><w:sz w:val="18"/>')
    + _style("Hyperlink", "Hyperlink", typ="character", based=None,
             rpr='<w:color w:val="1F4E8C"/><w:u w:val="single"/>')
    + "</w:styles>")
