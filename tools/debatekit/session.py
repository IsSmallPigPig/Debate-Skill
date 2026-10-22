"""会话目录模型。

    debate-output/<session_id>/
    ├── session.json          元数据 + 进度（编排器维护，见 collab/PROTOCOL.md §1）
    ├── transcript/           每个步骤一个文件：R02-质询-反四质询正一.md
    ├── artifacts/            派生稿件（Word 打印就绪）
    ├── evidence.md           证据台账（templates/evidence_ledger.md）
    └── qa/threads.jsonl      锚定问答（网页提问 / Agent 回写，按 id 合并）
"""

import datetime as _dt
import hashlib
import json
import os
import re
import uuid

from . import lint as _lint
from . import mdblocks, presets

TZ = _dt.timezone(_dt.timedelta(hours=8))


def now_iso():
    return _dt.datetime.now(TZ).replace(microsecond=0).isoformat()


def is_session_dir(path):
    return os.path.isfile(os.path.join(path, "session.json")) or os.path.isdir(os.path.join(path, "transcript"))


def find_sessions(root):
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        return []
    if is_session_dir(root):
        return [Session(root)]
    out = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if not name.startswith(".") and os.path.isdir(p) and is_session_dir(p):
            out.append(Session(p))
    out.sort(key=lambda s: s.updated_ts(), reverse=True)
    return out


class Session(object):
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.id = os.path.basename(self.path.rstrip(os.sep))
        self.meta = {}
        self.reload()
        self._lint_cache = {}

    # ------------------------------------------------------------ meta
    def reload(self):
        p = os.path.join(self.path, "session.json")
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8") as fh:
                    self.meta = json.load(fh)
            except (ValueError, OSError):
                self.meta = {"_error": "session.json 解析失败"}
        else:
            self.meta = {}

    def save_meta(self):
        self.meta["updated"] = now_iso()
        tmp = os.path.join(self.path, "session.json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.meta, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, os.path.join(self.path, "session.json"))

    @property
    def preset(self):
        return self.meta.get("preset") or "full"

    @property
    def user_side(self):
        return self.meta.get("user_side") or "正方"

    @property
    def lineup(self):
        return self.meta.get("lineup") or {}

    @property
    def topic(self):
        return self.meta.get("topic") or self.id

    def updated_ts(self):
        try:
            return max(os.path.getmtime(os.path.join(dp, f))
                       for dp, _, fs in os.walk(self.path) for f in fs)
        except ValueError:
            return 0

    # ------------------------------------------------------------ docs
    def _rel(self, p):
        return os.path.relpath(p, self.path).replace(os.sep, "/")

    def list_docs(self):
        docs = []
        tdir = os.path.join(self.path, "transcript")
        order = {sid: k for k, sid in enumerate(presets.preset_steps(self.preset))}
        if os.path.isdir(tdir):
            for name in sorted(os.listdir(tdir)):
                if not name.endswith(".md") or name.startswith("."):
                    continue
                full = os.path.join(tdir, name)
                step = presets.match_step_id(name)
                key = step if step else "transcript/" + name[:-3]
                spec = presets.step_spec(step, self.user_side) if step else None
                docs.append(self._doc(full, "transcript", key, step, spec, order.get(step, 10000)))
        adir = os.path.join(self.path, "artifacts")
        if os.path.isdir(adir):
            for name in sorted(os.listdir(adir)):
                if name.endswith(".md") and not name.startswith("."):
                    full = os.path.join(adir, name)
                    docs.append(self._doc(full, "artifact", "artifacts/" + name[:-3], None, None, 20000))
        rdir = os.path.join(self.path, "research")
        if os.path.isdir(rdir):
            for name in sorted(os.listdir(rdir)):
                if name.endswith(".md") and not name.startswith("."):
                    full = os.path.join(rdir, name)
                    docs.append(self._doc(full, "research", "research/" + name[:-3], None, None, 25000))
        for name in sorted(os.listdir(self.path)):
            full = os.path.join(self.path, name)
            if name.endswith(".md") and os.path.isfile(full) and not name.startswith("."):
                group = "evidence" if name.startswith("evidence") or "证据台账" in name else "other"
                docs.append(self._doc(full, group, name[:-3], None, None, 30000))
        # 同一步骤出现多个文件时（例如重做），保留最新的作为主文件，其余加后缀 key
        seen = {}
        for d in docs:
            if d["key"] in seen:
                d["key"] = d["key"] + "~" + os.path.basename(d["path"])[:-3]
            seen[d["key"]] = d
        docs.sort(key=lambda d: (d["order"], d["path"]))
        return docs

    def _doc(self, full, group, key, step, spec, order):
        st = os.stat(full)
        title = None
        try:
            with open(full, encoding="utf-8") as fh:
                head = fh.read(4000)
            meta, body, _ = mdblocks.split_front_matter(head)
            title = meta.get("title")
            if not title:
                m = re.search(r"^#{1,3}\s+(.+)$", body, re.M)
                title = m.group(1).strip() if m else None
        except OSError:
            pass
        if not title:
            title = (spec or {}).get("title") or os.path.basename(full)[:-3]
        return {
            "key": key,
            "path": self._rel(full),
            "group": group,
            "step": step,
            "stage": (spec or {}).get("stage"),
            "kind": (spec or {}).get("kind", group),
            "title": title,
            "nav": (spec or {}).get("nav") or title,
            "mtime": st.st_mtime,
            "size": st.st_size,
            "order": order,
        }

    def doc_by_key(self, key):
        for d in self.list_docs():
            if d["key"] == key or d["path"] == key or d["path"] == key + ".md":
                return d
        # 宽松匹配：R2 → R02
        alt = presets.match_step_id(key + "-x.md") if key else None
        if alt:
            for d in self.list_docs():
                if d["key"] == alt:
                    return d
        return None

    def abspath(self, rel):
        full = os.path.abspath(os.path.join(self.path, rel))
        if not (full == self.path or full.startswith(self.path + os.sep)):
            raise ValueError("path escapes session dir")
        return full

    def read(self, doc):
        with open(self.abspath(doc["path"]), encoding="utf-8") as fh:
            return fh.read()

    def parse(self, doc):
        return mdblocks.parse_document(self.read(doc))

    # ------------------------------------------------------------ evidence / lint
    def ledger(self):
        for name in ("evidence.md", "证据台账.md"):
            p = os.path.join(self.path, name)
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as fh:
                    return _lint.parse_ledger(fh.read())
        return None

    def lint_all(self):
        """按预设顺序校验全部 transcript，返回 {doc_key: result}。带缓存。"""
        ver = self.version()
        if self._lint_cache.get("_ver") == ver:
            return self._lint_cache["data"]
        ledger = self.ledger()
        prior = []
        out = {}
        for d in self.list_docs():
            if d["group"] != "transcript":
                continue
            text = self.read(d)
            spec = presets.step_spec(d["step"], self.user_side) if d["step"] else None
            res = _lint.lint_text(text, spec, self.lineup, "\n".join(prior), ledger)
            out[d["key"]] = res
            _, blocks = mdblocks.parse_document(text)
            prior.append("\n".join(mdblocks.block_plain(b) for b in blocks))
        self._lint_cache = {"_ver": ver, "data": out}
        return out

    # ------------------------------------------------------------ progress board
    def steps_view(self):
        docs = {d["key"]: d for d in self.list_docs() if d["group"] == "transcript"}
        lints = self.lint_all()
        progress = (self.meta.get("progress") or {})
        recorded = progress.get("steps") or {}
        current = progress.get("current")
        rows = []
        for sid in presets.preset_steps(self.preset):
            spec = presets.step_spec(sid, self.user_side) or {"title": sid, "stage": "?"}
            d = docs.get(sid)
            res = lints.get(sid)
            rec = recorded.get(sid) or {}
            if d is None:
                status = "in_progress" if current == sid else ("skipped" if rec.get("status") == "skipped" else "pending")
            elif rec.get("status") == "in_progress" or (current == sid and rec.get("status") != "done"):
                status = "in_progress"   # 正在写：不因字数未满判为不通过
            elif res and not res["pass"]:
                status = "issues"
            else:
                status = "done"
            rows.append({
                "id": sid,
                "stage": spec.get("stage"),
                "kind": spec.get("kind"),
                "title": spec.get("title"),
                "nav": spec.get("nav") or sid,
                "duration": spec.get("duration", "—"),
                "timing": spec.get("timing", "—"),
                "prompt": spec.get("prompt", ""),
                "file": spec.get("file", ""),
                "min_chars": int(spec.get("min_chars") or 0),
                "chars": res["metrics"]["chars"] if res else 0,
                "errors": res["errors"] if res else 0,
                "warnings": res["warnings"] if res else 0,
                "status": status,
                "doc": d["key"] if d else None,
                "speakers": presets.speakers_for(spec, self.lineup),
            })
        return rows

    def next_step(self):
        for row in self.steps_view():
            if row["status"] in ("pending", "in_progress", "issues"):
                return row
        return None

    def mark_step(self, step_id, status, note=None):
        prog = self.meta.setdefault("progress", {})
        steps = prog.setdefault("steps", {})
        rec = steps.setdefault(step_id, {})
        rec["status"] = status
        rec["updated"] = now_iso()
        if note:
            rec["note"] = note
        if status == "in_progress":
            prog["current"] = step_id
        elif prog.get("current") == step_id and status in ("done", "skipped"):
            nxt = None
            ids = presets.preset_steps(self.preset)
            if step_id in ids and ids.index(step_id) + 1 < len(ids):
                nxt = ids[ids.index(step_id) + 1]
            prog["current"] = nxt
        self.save_meta()
        return rec

    # ------------------------------------------------------------ version (live refresh)
    def version(self):
        h = hashlib.sha1()
        for dp, dns, fs in os.walk(self.path):
            dns[:] = sorted(d for d in dns if not d.startswith("."))
            for f in sorted(fs):
                if f.startswith(".") or f.endswith(".tmp"):
                    continue
                p = os.path.join(dp, f)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                h.update(("%s|%d|%d;" % (self._rel(p), st.st_mtime_ns, st.st_size)).encode("utf-8"))
        return h.hexdigest()[:16]

    # ------------------------------------------------------------ Q&A threads
    def _qa_path(self):
        return os.path.join(self.path, "qa", "threads.jsonl")

    def threads(self):
        p = self._qa_path()
        merged, order = {}, []
        if not os.path.isfile(p):
            return []
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                qid = rec.get("id") or uuid.uuid4().hex[:8]
                if qid not in merged:
                    merged[qid] = {}
                    order.append(qid)
                base = merged[qid]
                created = base.get("created")
                base.update({k: v for k, v in rec.items() if v not in (None, "")})
                if created:
                    base["created"] = created
        return [merged[q] for q in order]

    def append_thread(self, rec):
        rec = dict(rec)
        rec.setdefault("id", "Q" + _dt.datetime.now(TZ).strftime("%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4])
        rec.setdefault("created", now_iso())
        os.makedirs(os.path.dirname(self._qa_path()), exist_ok=True)
        with open(self._qa_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    # ------------------------------------------------------------ summary
    def summary(self):
        rows = self.steps_view()
        done = sum(1 for r in rows if r["status"] == "done")
        chars = sum(r["chars"] for r in rows)
        need = sum(r["min_chars"] for r in rows)
        return {
            "id": self.id,
            "topic": self.topic,
            "sides": self.meta.get("sides") or {},
            "user_side": self.user_side,
            "preset": self.preset,
            "preset_label": (presets.load()["presets"].get(self.preset) or {}).get("label", self.preset),
            "mode": self.meta.get("mode", ""),
            "output": self.meta.get("output", ""),
            "lineup": self.lineup,
            "created": self.meta.get("created"),
            "updated": self.meta.get("updated"),
            "done": done,
            "total": len(rows),
            "chars": chars,
            "min_chars": need,
            "current": (self.meta.get("progress") or {}).get("current"),
        }


def slugify(text, maxlen=24):
    text = re.sub(r"[\\/:*?\"<>|\s，。！？、；：（）()【】\[\]{}]+", "-", text or "").strip("-")
    return text[:maxlen] or "debate"


def init_session(root, topic, sides=None, user_side="正方", preset="full", mode="isolated",
                 output="web", lineup=None, slug=None):
    os.makedirs(root, exist_ok=True)
    stamp = _dt.datetime.now(TZ).strftime("%Y%m%d-%H%M")
    sid = "%s-%s" % (stamp, slug or slugify(topic))
    path = os.path.join(root, sid)
    k = 2
    while os.path.exists(path):
        path = os.path.join(root, "%s-%d" % (sid, k))
        k += 1
    for sub in ("transcript", "artifacts", "qa"):
        os.makedirs(os.path.join(path, sub), exist_ok=True)
    meta = {
        "schema": "debate-session/1",
        "skill_version": "3.0.0",
        "session_id": os.path.basename(path),
        "created": now_iso(),
        "updated": now_iso(),
        "topic": topic,
        "sides": sides or {},
        "user_side": user_side,
        "preset": preset,
        "mode": mode,
        "output": output,
        "lineup": lineup or {},
        "progress": {"current": presets.preset_steps(preset)[0], "steps": {}},
    }
    with open(os.path.join(path, "session.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(path, "evidence.md"), "w", encoding="utf-8") as fh:
        fh.write(EVIDENCE_HEADER.format(topic=topic))
    open(os.path.join(path, "qa", "threads.jsonl"), "a").close()
    return Session(path)


EVIDENCE_HEADER = """# 证据台账｜{topic}

> 规则（templates/evidence_ledger.md）：URL 只能来自本会话真实的检索/抓取工具返回结果；
> 模型记忆中的数据一律登记为「⚠️待核实」且不写 URL；发言中引用待核实数据须标注【待核实】。

| ID | 状态 | 用途（持方·论点） | 关键摘录 | 来源标题 | URL | 获取方式 | 核验时间 |
|---|---|---|---|---|---|---|---|
"""
