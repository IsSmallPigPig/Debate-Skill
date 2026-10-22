#!/usr/bin/env python3
"""debate_ctl · Debate-Skills v3 编排器命令行（纯标准库）。

常用：
  python3 tools/debate_ctl.py init --topic "年轻人该不该回老家发展" --pro "年轻人应该回老家发展" \
          --con "年轻人不应该回老家发展" --side 正方 --preset full
  python3 tools/debate_ctl.py next   <session>          # 下一步该跑什么（prompt 小节、下限、输出文件）
  python3 tools/debate_ctl.py step   <session> R02 --status done   # 校验通过才允许标记完成
  python3 tools/debate_ctl.py lint   <session|file.md>  # 机器校验完成契约
  python3 tools/debate_ctl.py status <session>          # 进度看板（Markdown，可直接贴进对话）
  python3 tools/debate_ctl.py locate "<粘贴的【辩论协同·提问】块>"   # 或从 stdin 读取
  python3 tools/debate_ctl.py ask list|answer|new <session> ...      # 网页提问队列 / 回写答案
  python3 tools/debate_ctl.py export <session> --doc all --format docx
  python3 tools/debate_ctl.py budget --preset full

<session> 可以是会话目录路径、会话 ID（在 --root 下查找），或 latest。
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from debatekit import export as dexport  # noqa: E402
from debatekit import lint as dlint  # noqa: E402
from debatekit import mdblocks, presets, refs  # noqa: E402
from debatekit import session as dsession  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass

STATUS_ICON = {"done": "✅", "issues": "⚠️", "in_progress": "▶️", "pending": "⬜", "skipped": "⏭️"}


def default_root(args=None):
    return (getattr(args, "root", None) or os.environ.get("DEBATE_OUTPUT") or "debate-output")


def find_session(ref, root):
    if ref and os.path.isdir(ref) and dsession.is_session_dir(ref):
        return dsession.Session(ref)
    sessions = dsession.find_sessions(root)
    if not ref or ref == "latest":
        if sessions:
            return sessions[0]
        sys.exit("未在 %s 下找到任何会话（可用 --root 指定，或先 init）" % os.path.abspath(root))
    for s in sessions:
        if s.id == ref:
            return s
    # 在常见位置继续找（便于 locate 粘贴引用时自动发现）
    for base in (".", "debate-output", os.path.join(HERE, "..", "collab", "demo")):
        p = os.path.join(base, ref)
        if os.path.isdir(p) and dsession.is_session_dir(p):
            return dsession.Session(p)
    sys.exit("找不到会话：%s（root=%s）" % (ref, os.path.abspath(root)))


def parse_lineup(text):
    out = {}
    if not text:
        return out
    for part in text.replace("；", ";").split(";"):
        if "=" not in part:
            continue
        side, names = part.split("=", 1)
        names = [n.strip() for n in names.replace("，", ",").split(",")]
        out[side.strip()] = {p: n for p, n in zip(("一辩", "二辩", "三辩", "四辩"), names) if n}
    return out


# ---------------------------------------------------------------- commands

def cmd_init(a):
    lineup = parse_lineup(a.lineup)
    sides = {"正方": a.pro or "", "反方": a.con or ""}
    s = dsession.init_session(default_root(a), a.topic, sides, a.side, a.preset, a.mode, a.output, lineup, a.slug)
    print("✅ 已创建会话：%s" % s.path)
    print("   session_id = %s" % s.id)
    print("   预设 = %s（%d 步）  模式 = %s  输出 = %s" % (a.preset, len(presets.preset_steps(a.preset)), a.mode, a.output))
    print("   协同台：python3 %s --root %s" % (os.path.normpath(os.path.join(HERE, "..", "collab", "server.py")), os.path.abspath(default_root(a))))
    _print_next(s)


def _speaker_text(spec, lineup):
    sp = presets.speakers_for(spec, lineup)
    return "、".join("%s%s" % (x["role"], (" · " + x["name"]) if x["name"] else "") for x in sp) or "—"


def _print_next(s, as_json=False):
    row = s.next_step()
    if not row:
        print("🎉 本预设的全部步骤都已完成。可运行 export 导出整场实录。")
        return
    spec = presets.step_spec(row["id"], s.user_side)
    out_path = os.path.join(s.path, "transcript", spec.get("file", row["id"] + ".md"))
    if as_json:
        print(json.dumps({"step": row, "spec": spec, "output": out_path}, ensure_ascii=False, indent=2))
        return
    print("\n▶ 下一步：%s　%s" % (row["id"], spec.get("title")))
    print("  状态：%s %s" % (STATUS_ICON.get(row["status"], ""), row["status"]))
    print("  Prompt：%s" % spec.get("prompt", "—"))
    if spec.get("knowledge"):
        print("  必读：%s" % "、".join(spec["knowledge"]))
    print("  参与：%s" % _speaker_text(spec, s.lineup))
    print("  时长：%s · 计时：%s · 字数下限：%s" % (spec.get("duration", "—"), spec.get("timing", "—"), spec.get("min_chars", 0)))
    extras = []
    for k, label in (("min_rounds", "完整回合≥"), ("questioner_min_chars", "质询方字数≥"), ("answer_min_chars", "每次回答≥"),
                     ("min_segments", "自证段≥"), ("segment_min_chars", "每段≥"), ("interrupt_max", "打岔≤"),
                     ("interrupt_max_chars", "每次打岔≤"), ("min_turns", "发言次数≥"), ("max_turns", "发言次数≤"),
                     ("turn_min_chars", "单次≥"), ("turn_max_chars", "单次≤"), ("each_speaker_min_turns", "每人发言≥"),
                     ("min_urls", "证据URL≥")):
        if spec.get(k):
            extras.append("%s%s" % (label, spec[k]))
    if extras:
        print("  校验项：%s" % "  ".join(extras))
    print("  输出文件：%s" % out_path)
    if row["status"] == "issues":
        res = s.lint_all().get(row["id"])
        if res:
            print("  ⚠️ 已有文件但未通过校验：")
            for c in res["checks"]:
                if c["level"] == "error":
                    print("     ✗ %s" % c["msg"])


def cmd_next(a):
    s = find_session(a.session, default_root(a))
    _print_next(s, a.json)


def cmd_status(a):
    s = find_session(a.session, default_root(a))
    sm = s.summary()
    rows = s.steps_view()
    if a.json:
        print(json.dumps({"summary": sm, "steps": rows}, ensure_ascii=False, indent=2))
        return
    print("## 进度看板｜%s" % sm["topic"])
    print("> 预设：%s · 完成 %d/%d · 实测 %s 字 / 下限合计 %s 字 · 会话 %s\n" % (
        sm["preset_label"], sm["done"], sm["total"], format(sm["chars"], ","), format(sm["min_chars"], ","), s.id))
    print("| 阶段 | 步骤 | 时长 | 下限 | 实测 | 状态 | 问题 |")
    print("|---|---|---|---:|---:|:---:|---|")
    for r in rows:
        issues = ("✗%d" % r["errors"] if r["errors"] else "") + (" ⚠%d" % r["warnings"] if r["warnings"] else "")
        print("| %s | %s %s | %s | %s | %s | %s | %s |" % (
            r["stage"], r["id"], r["title"], r["duration"], r["min_chars"] or "—", r["chars"] or "—",
            STATUS_ICON.get(r["status"], r["status"]), issues.strip() or "—"))
    _print_next(s)


def cmd_step(a):
    s = find_session(a.session, default_root(a))
    sid = a.step
    if presets.step_spec(sid, s.user_side) is None:
        sys.exit("未知步骤：%s（可选：%s）" % (sid, " ".join(presets.preset_steps(s.preset))))
    if a.status == "done":
        res = s.lint_all().get(sid)
        if res is None:
            sys.exit("✗ 找不到 %s 的 transcript 文件，无法标记完成（应写入 transcript/%s）" % (
                sid, presets.step_spec(sid, s.user_side).get("file")))
        print(res["verified_line"])
        if not res["pass"] and not a.force:
            for c in res["checks"]:
                if c["level"] == "error":
                    print("  ✗ %s%s" % (c["msg"], ("（¶%s）" % ",".join(map(str, c["blocks"]))) if c["blocks"] else ""))
            sys.exit("✗ 未通过校验，按 prompts/round_prompts.md §9 重做该步骤（或 --force 强制标记）")
    s.mark_step(sid, a.status, a.note)
    print("✓ %s → %s" % (sid, a.status))
    if a.status in ("done", "skipped"):
        _print_next(s)


def _print_lint(res, title, path=None, verbose=True):
    print("\n■ %s%s" % (title, ("  [%s]" % path) if path else ""))
    print("  " + res["verified_line"])
    if verbose:
        for c in res["checks"]:
            mark = "✗" if c["level"] == "error" else "⚠"
            where = ("（¶%s）" % ",".join(map(str, c["blocks"][:8]))) if c["blocks"] else ""
            print("  %s %s%s" % (mark, c["msg"], where))


def cmd_lint(a):
    target = a.target or "latest"
    if os.path.isfile(target):
        path = os.path.abspath(target)
        parent = os.path.dirname(os.path.dirname(path))
        step = presets.match_step_id(path)
        if os.path.basename(os.path.dirname(path)) == "transcript" and dsession.is_session_dir(parent):
            s = dsession.Session(parent)
            res = None
            for d in s.list_docs():
                if os.path.abspath(s.abspath(d["path"])) == path:
                    res = s.lint_all().get(d["key"])
            if res is None:
                res = dlint.lint_text(open(path, encoding="utf-8").read(), presets.step_spec(step, s.user_side) if step else None, s.lineup)
        else:
            res = dlint.lint_text(open(path, encoding="utf-8").read(), presets.step_spec(step) if step else None)
        if a.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            _print_lint(res, step or os.path.basename(path), path)
        sys.exit(0 if res["pass"] else 1)
    s = find_session(target, default_root(a))
    results = s.lint_all()
    docs = {d["key"]: d for d in s.list_docs()}
    if a.step:
        results = {k: v for k, v in results.items() if k == a.step}
    if a.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for key, res in results.items():
            _print_lint(res, key, docs.get(key, {}).get("path"))
        n_err = sum(r["errors"] for r in results.values())
        n_warn = sum(r["warnings"] for r in results.values())
        print("\n合计：%d 份文件 · %d 项硬性问题 · %d 项建议" % (len(results), n_err, n_warn))
    sys.exit(0 if all(r["pass"] for r in results.values()) else 1)


def _read_text_arg(text):
    if text and text != "-":
        if os.path.isfile(text):
            return open(text, encoding="utf-8").read()
        return text
    return sys.stdin.read()


def _locate_one(ref, root, context=2):
    s = find_session(ref["sid"], root)
    d = s.doc_by_key(ref["key"])
    if not d:
        return {"ref": ref, "error": "会话 %s 中找不到文档 %s" % (s.id, ref["key"])}
    meta, blocks = s.parse(d)
    blk, method = refs.locate_in_blocks(blocks, ref["block"], ref.get("quote", ""))
    if not blk:
        return {"ref": ref, "error": "文档 %s 中找不到 %s" % (d["path"], ref["anchor"])}
    lo, hi = max(0, blk["i"] - 1 - context), min(len(blocks), blk["i"] + context)
    ctx = []
    for b in blocks[lo:hi]:
        ctx.append({"i": b["i"], "label": refs.describe_block(b), "text": b["text"], "target": b["i"] == blk["i"]})
    return {
        "ref": ref, "session": s.id, "session_path": s.path, "doc": d["key"], "path": os.path.join(s.path, d["path"]),
        "title": d["title"], "block": blk["i"], "method": method, "lines": [blk["line_start"], blk["line_end"]],
        "label": refs.describe_block(blk), "text": blk["text"], "context": ctx,
    }


def cmd_locate(a):
    text = _read_text_arg(a.text)
    found, info = refs.parse_refs(text)
    if not found:
        sys.exit("没有在输入中找到 debate://<session>/<doc>#b<N> 形式的定位引用")
    results = [_locate_one(r, default_root(a), a.context) for r in found]
    if a.json:
        print(json.dumps({"info": info, "results": results}, ensure_ascii=False, indent=2))
        return
    if info.get("target") or info.get("intent"):
        print("提问对象：%s｜意图：%s" % (info.get("target") or "—", info.get("intent") or "—"))
    for k, r in enumerate(results, 1):
        if r.get("error"):
            print("\n[%d] %s  ✗ %s" % (k, r["ref"]["uri"], r["error"]))
            continue
        print("\n[%d] %s" % (k, r["ref"]["uri"]))
        print("    文件：%s  第 %d–%d 行（定位方式：%s）" % (r["path"], r["lines"][0], r["lines"][1], r["method"]))
        print("    位置：%s › %s" % (r["title"], r["label"]))
        for c in r["context"]:
            prefix = "  ▶ " if c["target"] else "    "
            snippet = c["text"].replace("\n", " ")
            if not c["target"] and len(snippet) > 120:
                snippet = snippet[:120] + "…"
            print("%s%s｜%s" % (prefix, c["label"], snippet))
    if info.get("question"):
        print("\n问题：%s" % info["question"])


def cmd_ask(a):
    s = find_session(a.session, default_root(a))
    if a.action == "list":
        pend = [t for t in s.threads() if (a.all or t.get("status") != "answered")]
        if not pend:
            print("（没有待处理的提问）")
            return
        for t in pend:
            print("\n● %s  [%s]  %s → %s" % (t.get("id"), t.get("status", "pending"), t.get("intent", "提问"), t.get("target", "")))
            for r in t.get("refs") or []:
                loc = _locate_one({"sid": s.id, "key": r.get("key"), "block": int(str(r.get("anchor", "b0"))[1:] or 0),
                                   "anchor": r.get("anchor"), "quote": r.get("quote", ""), "uri": r.get("uri", "")}, default_root(a), 0)
                if loc.get("error"):
                    print("   - %s ✗ %s" % (r.get("uri"), loc["error"]))
                else:
                    print("   - %s → %s 第 %d 行 · %s" % (r.get("uri"), loc["path"], loc["lines"][0], loc["label"]))
                    print("     原文：%s" % (r.get("quote") or loc["text"])[:200].replace("\n", " "))
            print("   问题：%s" % t.get("question", ""))
        return
    if a.action == "answer":
        if not a.id:
            sys.exit("需要 --id")
        answer = _read_text_arg(a.answer_file) if a.answer_file else (a.answer or "")
        if not answer.strip():
            sys.exit("答案为空（用 --answer 或 --answer-file）")
        rec = {"id": a.id, "answer": answer.strip(), "answered_by": a.by or "教练", "answered": dsession.now_iso(),
               "status": "answered"}
        if a.changed:
            rec["changes"] = a.changed
        s.append_thread(rec)
        print("✓ 已回写 %s → qa/threads.jsonl（网页会自动刷新显示）" % a.id)
        return
    if a.action == "new":
        text = _read_text_arg(a.ref_text)
        found, info = refs.parse_refs(text)
        answer = _read_text_arg(a.answer_file) if a.answer_file else (a.answer or "")
        rec = {
            "refs": [{"uri": r["uri"], "key": r["key"], "anchor": r["anchor"], "quote": r.get("quote", "")} for r in found],
            "intent": info.get("intent") or a.intent or "提问",
            "target": info.get("target") or a.target or "教练",
            "question": info.get("question") or a.question or "",
            "status": "answered" if answer.strip() else "pending",
            "source": "chat",
        }
        if answer.strip():
            rec.update(answer=answer.strip(), answered_by=a.by or rec["target"], answered=dsession.now_iso())
        rec = s.append_thread(rec)
        print("✓ 已记录 %s（%s）" % (rec["id"], rec["status"]))


def cmd_export(a):
    s = find_session(a.session, default_root(a))
    clean, qa, disc = not a.raw, a.qa, not a.no_disclaimer
    if a.doc in (None, "all", "__all__"):
        if a.format == "zip":
            name, data, _ = dexport.export_zip(s, clean, qa, disc)
        else:
            name, data, _ = dexport.export_transcript(s, a.format, clean, qa, disc)
    else:
        d = s.doc_by_key(a.doc)
        if not d:
            sys.exit("找不到文档：%s" % a.doc)
        name, data, _ = dexport.export_doc(s, d, "docx" if a.format == "zip" else a.format, clean, qa, disc)
    out_dir = a.out or os.path.join(s.path, "exports")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    with open(path, "wb") as fh:
        fh.write(data)
    print("✓ 已导出：%s（%s KB）" % (path, round(len(data) / 1024.0, 1)))


def cmd_budget(a):
    names = presets.preset_names() if a.preset == "all" else [a.preset]
    for name in names:
        rows, total = presets.budget(name)
        label = presets.load()["presets"][name]["label"]
        print("\n## 预设 %s · %s（%d 步 · 字数下限合计 %s）" % (name, label, len(rows), format(total, ",")))
        if a.brief:
            continue
        print("| 步骤 | 环节 | 时长 | 下限 |\n|---|---|---|---:|")
        for sid, title, dur, mc in rows:
            print("| %s | %s | %s | %s |" % (sid, title.replace("{side}", "").replace("{user_side}", ""), dur, mc or "—"))


def main(argv=None):
    p = argparse.ArgumentParser(prog="debate_ctl", description="Debate-Skills v3 编排器命令行")
    p.add_argument("--root", help="会话根目录（默认 $DEBATE_OUTPUT 或 ./debate-output）")
    sub = p.add_subparsers(dest="cmd")

    q = sub.add_parser("init", help="创建会话目录与 session.json")
    q.add_argument("--topic", required=True)
    q.add_argument("--pro", help="正方立场")
    q.add_argument("--con", help="反方立场")
    q.add_argument("--side", default="正方", choices=["正方", "反方"])
    q.add_argument("--preset", default="full", choices=presets.preset_names())
    q.add_argument("--mode", default="isolated", choices=["isolated", "inline"])
    q.add_argument("--output", default="web", choices=["chat", "web", "both"])
    q.add_argument("--lineup", help='"正方=胡渐彪,颜如晶,黄执中,马薇薇;反方=庞颖,周玄毅,詹青云,陈铭"')
    q.add_argument("--slug", help="会话目录名后缀（默认取辩题）")
    q.set_defaults(func=cmd_init)

    for name, fn, hlp in (("next", cmd_next, "下一步"), ("status", cmd_status, "进度看板")):
        q = sub.add_parser(name, help=hlp)
        q.add_argument("session", nargs="?", default="latest")
        q.add_argument("--json", action="store_true")
        q.set_defaults(func=fn)

    q = sub.add_parser("step", help="更新步骤状态（done 前自动校验）")
    q.add_argument("session")
    q.add_argument("step")
    q.add_argument("--status", default="done", choices=["in_progress", "done", "skipped", "redo"])
    q.add_argument("--note")
    q.add_argument("--force", action="store_true")
    q.set_defaults(func=cmd_step)

    q = sub.add_parser("lint", help="机器校验完成契约")
    q.add_argument("target", nargs="?", help="会话目录 / 会话 ID / 单个 .md 文件")
    q.add_argument("--step")
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_lint)

    q = sub.add_parser("locate", help="解析【辩论协同·提问】中的定位引用")
    q.add_argument("text", nargs="?", default="-", help="引用文本 / 文件路径 / - 表示 stdin")
    q.add_argument("--context", type=int, default=2)
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_locate)

    q = sub.add_parser("ask", help="协同问答：list / answer / new")
    q.add_argument("action", choices=["list", "answer", "new"])
    q.add_argument("session", nargs="?", default="latest")
    q.add_argument("--id")
    q.add_argument("--answer")
    q.add_argument("--answer-file")
    q.add_argument("--by")
    q.add_argument("--changed", nargs="*")
    q.add_argument("--ref-text", default="-")
    q.add_argument("--intent")
    q.add_argument("--target")
    q.add_argument("--question")
    q.add_argument("--all", action="store_true")
    q.set_defaults(func=cmd_ask)

    q = sub.add_parser("export", help="导出 docx / md / html / zip")
    q.add_argument("session", nargs="?", default="latest")
    q.add_argument("--doc", help="文档 key（R02、artifacts/正方-一辩稿）；省略或 all = 整场实录")
    q.add_argument("--format", default="docx", choices=["docx", "md", "html", "zip"])
    q.add_argument("--out")
    q.add_argument("--raw", action="store_true", help="不清理契约行/编排器提炼块")
    q.add_argument("--qa", action="store_true", help="附加协同问答附录")
    q.add_argument("--no-disclaimer", action="store_true")
    q.set_defaults(func=cmd_export)

    q = sub.add_parser("budget", help="按预设列出字数下限（来自 rules/presets.json）")
    q.add_argument("--preset", default="all")
    q.add_argument("--brief", action="store_true")
    q.set_defaults(func=cmd_budget)

    a = p.parse_args(argv)
    if not getattr(a, "func", None):
        p.print_help()
        return 1
    a.func(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
