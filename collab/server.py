#!/usr/bin/env python3
"""辩论协同台 · Debate Collab Server（纯标准库）

    python3 collab/server.py --root debate-output            # 默认 0.0.0.0:8765
    python3 collab/server.py --root collab/demo --port 8770  # 打开示例会话

功能：实时展示 Agent 写入 debate-output/<session>/ 的内容；单文档/整场导出 Word·Markdown·HTML·ZIP；
每段可「复制位置并提问」，生成 Agent 可解析的【辩论协同·提问】文本；问答回写后在原文锚点处显示。

前端只使用相对 URL（/api/...），可直接放在反向代理 / 预览域名之后。
"""

import argparse
import json
import mimetypes
import os
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

from debatekit import export as dexport  # noqa: E402
from debatekit import mdblocks, presets, refs  # noqa: E402
from debatekit import session as dsession  # noqa: E402

WEB = os.path.join(HERE, "web")
MAX_POST = 256 * 1024


class App(object):
    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.cache = {}

    def sessions(self):
        found = dsession.find_sessions(self.root)
        fresh = {}
        for s in found:
            old = self.cache.get(s.id)
            if old is not None and old.path == s.path:
                old.reload()
                fresh[s.id] = old
            else:
                fresh[s.id] = s
        self.cache = fresh
        return [fresh[s.id] for s in found]

    def get(self, sid):
        s = self.cache.get(sid)
        if s is None:
            self.sessions()
            s = self.cache.get(sid)
        if s is not None:
            s.reload()
        return s


def threads_for(session, key=None):
    out = []
    for th in session.threads():
        if key and not any(r.get("key") == key for r in th.get("refs") or []):
            continue
        th = dict(th)
        if th.get("answer"):
            _, blocks = mdblocks.parse_document(th["answer"])
            th["answer_html"] = "".join(mdblocks.block_html(b) for b in blocks)
        out.append(th)
    return out


def doc_payload(session, doc):
    text = session.read(doc)
    meta, blocks = mdblocks.parse_document(text)
    lint = session.lint_all().get(doc["key"]) if doc["group"] == "transcript" else None
    spec = presets.step_spec(doc["step"], session.user_side) if doc.get("step") else None
    out_blocks = []
    for b in blocks:
        item = {
            "i": b["i"], "type": b["type"], "html": mdblocks.block_html(b),
            "plain": mdblocks.block_plain(b), "lines": [b["line_start"], b["line_end"]],
        }
        if b["type"] == "heading":
            item["level"] = b["level"]
        if b.get("turn"):
            t = b["turn"]
            item["turn"] = {k: t[k] for k in ("label", "side", "pos", "persona", "note")}
        if b.get("extract"):
            item["extract"] = True
        out_blocks.append(item)
    return {
        "doc": doc,
        "front_matter": meta,
        "blocks": out_blocks,
        "lint": lint,
        "spec": spec,
        "speakers": presets.speakers_for(spec, session.lineup) if spec else [],
        "threads": threads_for(session, doc["key"]),
        "uri_prefix": "debate://%s/%s" % (session.id, doc["key"]),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "DebateCollab/3.0"
    app = None
    verbose = False

    # ------------------------------------------------------------ helpers
    def log_message(self, fmt, *args):
        if self.verbose:
            sys.stderr.write("[collab] " + (fmt % args) + "\n")

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _err(self, code, msg):
        self._json({"error": msg}, code)

    def _query(self):
        parsed = urllib.parse.urlparse(self.path)
        return parsed.path, {k: v[-1] for k, v in urllib.parse.parse_qs(parsed.query).items()}

    def _session(self, q):
        sid = q.get("id")
        s = self.app.get(sid) if sid else None
        if s is None:
            sessions = self.app.sessions()
            if not sid and sessions:
                return sessions[0]
            self._err(404, "session not found: %s" % sid)
            return None
        return s

    # ------------------------------------------------------------ routes
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            path, q = self._query()
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path in ("/app.js", "/app.css"):
                return self._static(path[1:])
            if path == "/favicon.ico":
                return self._send(204, b"", "image/x-icon")
            if path == "/api/health":
                return self._json({"ok": True, "root": self.app.root})
            if path == "/api/sessions":
                return self._json({"root": self.app.root, "sessions": [s.summary() for s in self.app.sessions()]})
            if path == "/api/session":
                s = self._session(q)
                if s is None:
                    return None
                docs = s.list_docs()
                return self._json({
                    "summary": s.summary(),
                    "steps": s.steps_view(),
                    "docs": docs,
                    "stages": presets.load()["stages"],
                    "threads": threads_for(s),
                    "version": s.version(),
                })
            if path == "/api/version":
                s = self._session(q)
                if s is None:
                    return None
                return self._json({"version": s.version()})
            if path == "/api/doc":
                s = self._session(q)
                if s is None:
                    return None
                d = s.doc_by_key(q.get("key", ""))
                if not d:
                    return self._err(404, "doc not found")
                return self._json(doc_payload(s, d))
            if path == "/api/search":
                s = self._session(q)
                if s is None:
                    return None
                return self._json({"hits": self._search(s, q.get("q", ""))})
            if path == "/api/threads":
                s = self._session(q)
                if s is None:
                    return None
                return self._json({"threads": threads_for(s, q.get("key"))})
            if path == "/api/locate":
                s = self._session(q)
                if s is None:
                    return None
                found, info = refs.parse_refs(q.get("text", ""))
                return self._json({"refs": found, "info": info})
            if path == "/api/export":
                return self._export(q)
            return self._err(404, "not found")
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            return self._err(500, "%s: %s" % (type(exc).__name__, exc))

    def do_POST(self):
        try:
            path, q = self._query()
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_POST:
                return self._err(413, "payload too large")
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
            if path == "/api/threads":
                s = self._session(q)
                if s is None:
                    return None
                refs_in = data.get("refs") or []
                if not refs_in:
                    return self._err(400, "refs required")
                rec = {
                    "refs": [{k: str(r.get(k, ""))[:600] for k in ("uri", "key", "anchor", "quote", "where")} for r in refs_in[:12]],
                    "intent": str(data.get("intent", "提问"))[:20],
                    "target": str(data.get("target", "教练"))[:20],
                    "question": str(data.get("question", ""))[:4000],
                    "status": "pending",
                    "source": "web",
                }
                rec = s.append_thread(rec)
                return self._json({"ok": True, "thread": rec})
            return self._err(404, "not found")
        except ValueError:
            return self._err(400, "invalid json")
        except Exception as exc:  # pragma: no cover
            traceback.print_exc()
            return self._err(500, "%s: %s" % (type(exc).__name__, exc))

    # ------------------------------------------------------------ impl
    def _static(self, name):
        full = os.path.join(WEB, name)
        if not os.path.isfile(full):
            return self._err(404, "missing web asset")
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(full, "rb") as fh:
            return self._send(200, fh.read(), ctype)

    def _search(self, s, needle):
        needle = (needle or "").strip()
        if not needle:
            return []
        low = needle.lower()
        hits = []
        for d in s.list_docs():
            try:
                _, blocks = s.parse(d)
            except OSError:
                continue
            for b in blocks:
                plain = mdblocks.block_plain(b)
                pos = plain.lower().find(low)
                if pos < 0:
                    continue
                lo = max(0, pos - 28)
                hits.append({
                    "key": d["key"], "title": d["title"], "nav": d["nav"], "i": b["i"],
                    "label": refs.describe_block(b),
                    "snippet": ("…" if lo else "") + plain[lo:pos + len(needle) + 40].replace("\n", " "),
                })
                if len(hits) >= 60:
                    return hits
        return hits

    def _export(self, q):
        s = self._session(q)
        if s is None:
            return None
        fmt = q.get("fmt", "docx")
        if fmt not in ("docx", "md", "html", "zip"):
            return self._err(400, "bad fmt")
        clean = q.get("clean", "1") != "0"
        qa = q.get("qa", "0") == "1"
        disc = q.get("disclaimer", "1") != "0"
        key = q.get("key", "__all__")
        if fmt == "zip":
            name, data, ctype = dexport.export_zip(s, clean, qa, disc)
        elif key in ("", "__all__"):
            name, data, ctype = dexport.export_transcript(s, fmt, clean, qa, disc)
        else:
            d = s.doc_by_key(key)
            if not d:
                return self._err(404, "doc not found")
            name, data, ctype = dexport.export_doc(s, d, fmt, clean, qa, disc)
        ascii_name = "export." + name.rsplit(".", 1)[-1]
        disp = "attachment; filename=\"%s\"; filename*=UTF-8''%s" % (ascii_name, urllib.parse.quote(name))
        if q.get("inline") == "1" and fmt == "html":
            disp = "inline"
        return self._send(200, data, ctype, {"Content-Disposition": disp})


def main(argv=None):
    p = argparse.ArgumentParser(description="辩论协同台 · Debate Collab Server")
    p.add_argument("--root", default=os.environ.get("DEBATE_OUTPUT", "debate-output"),
                   help="会话根目录（包含若干 <session>/ 子目录，或本身就是一个会话目录）")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    p.add_argument("--verbose", action="store_true")
    a = p.parse_args(argv)
    os.makedirs(a.root, exist_ok=True)
    Handler.app = App(a.root)
    Handler.verbose = a.verbose
    httpd = ThreadingHTTPServer((a.host, a.port), Handler)
    httpd.daemon_threads = True
    n = len(Handler.app.sessions())
    print("辩论协同台已启动：http://%s:%d   （root=%s，%d 个会话）" % (
        "localhost" if a.host in ("0.0.0.0", "") else a.host, a.port, Handler.app.root, n), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
