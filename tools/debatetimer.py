#!/usr/bin/env python3
"""debatetimer · 辩之竹（debatetimer.cn）官方 MCP 的命令行兜底客户端（纯标准库）。

优先级（见 knowledge/06-历史实录检索.md §二）：
  ① 环境已安装 MCP（npx add-mcp https://debatetimer.cn/api/mcp）→ 直接调用 MCP 工具
  ② 没装 MCP 但能跑 shell → 用本脚本（同一个官方接口，JSON-RPC over HTTP）
  ③ 都不行 → multi-search-engine / web_search：site:debatetimer.cn {关键词}

用法：
  python3 tools/debatetimer.py search "大城市" [--type topic|team|tournament] [--page 1] [--size 10]
  python3 tools/debatetimer.py summary <matchId> [--passcode XXXX] [--save research/]
  python3 tools/debatetimer.py batch <id1> <id2> ... [--save research/]     # ≤20 场，只算 1 次调用
  python3 tools/debatetimer.py tools                                           # 诊断：列出服务端工具

注意：
- 公测期全站共享 5000 次/天，批量算 1 次 → 能批量就批量；
- 服务端返回的 recordPageUrl 主机名是 127.0.0.1（已知问题），本脚本自动改写为 https://debatetimer.cn；
- 整场总结由 AI 根据录音整理，**可能含语音识别错误与缺段**（如把「西贝预制菜」识别成「西类预制食品」），
  引用其中的数据前必须用搜索引擎二次核验，并登记到证据台账。
"""

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = os.environ.get("DEBATETIMER_MCP", "https://debatetimer.cn/api/mcp")
SITE = "https://debatetimer.cn"
UA = "Debate-Skills/3.0 (+https://github.com/IsSmallPigPig/Debate-Skill)"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # pragma: no cover
        pass


class MCPError(Exception):
    pass


def fix_url(url, match_id=None):
    if not url and match_id:
        return "%s/record/%s" % (SITE, match_id)
    return re.sub(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?", SITE, url or "")


def _post(payload, session_id=None, timeout=30):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("User-Agent", UA)
    if session_id:
        req.add_header("Mcp-Session-Id", session_id)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        sid = resp.headers.get("Mcp-Session-Id")
    body = body.strip()
    if body.startswith("event:") or body.startswith("data:"):
        # SSE：取最后一个 data: 行
        datas = [ln[5:].strip() for ln in body.split("\n") if ln.startswith("data:")]
        body = datas[-1] if datas else "{}"
    return json.loads(body or "{}"), sid


_SESSION = {"id": None}


def call_tool(name, arguments, retries=1):
    payload = {"jsonrpc": "2.0", "id": int(time.time() * 1000) % 100000, "method": "tools/call",
               "params": {"name": name, "arguments": arguments}}
    last = None
    for attempt in range(retries + 1):
        try:
            resp, _ = _post(payload, _SESSION["id"])
            if "error" in resp:
                msg = json.dumps(resp["error"], ensure_ascii=False)
                if "session" in msg.lower() and not _SESSION["id"]:
                    _initialize()
                    continue
                raise MCPError(msg)
            result = resp.get("result") or {}
            if result.get("isError"):
                texts = [c.get("text", "") for c in result.get("content") or []]
                raise MCPError("；".join(texts) or "工具返回错误")
            return result
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = exc
            time.sleep(1.5)
    raise MCPError("网络/解析失败：%s" % last)


def _initialize():
    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                          "clientInfo": {"name": "debate-skills-cli", "version": "3.0.0"}}}
    _, sid = _post(payload)
    _SESSION["id"] = sid


# ---------------------------------------------------------------- formatting

WARN = "⚠️ 以下总结由 debatetimer.cn 根据比赛录音 AI 整理，可能含语音识别错误或缺段；引用数据前请二次核验并登记证据台账。"


def fmt_item(k, it):
    lock = " 🔒需口令" if it.get("locked") else ""
    return ("%2d. %s ⟷ %s%s\n    %s · %s · %s\n    %s · matchId=%s" % (
        k, it.get("topicA", ""), it.get("topicB", ""), lock,
        it.get("tournamentName") or "（无赛事名）",
        " vs ".join(x for x in (it.get("teamA"), it.get("teamB")) if x) or "（队伍未填）",
        (it.get("createdAt") or "")[:10],
        fix_url(it.get("recordPageUrl"), it.get("matchId")), it.get("matchId")))


def summary_md(sc):
    mid = sc.get("matchId", "")
    url = fix_url(sc.get("recordPageUrl"), mid)
    lines = [
        "# %s ⟷ %s" % (sc.get("topicA", ""), sc.get("topicB", "")),
        "",
        "> 赛事：%s ｜ 队伍：%s ｜ 实录：%s" % (sc.get("tournamentName") or "—",
                                       " vs ".join(x for x in (sc.get("teamA"), sc.get("teamB")) if x) or "—", url),
        "> %s" % WARN,
        "",
        (sc.get("summary") or "（该场暂无整场总结：%s）" % sc.get("status", "unknown")).strip(),
        "",
    ]
    return "\n".join(lines), url


def save_summary(directory, sc):
    os.makedirs(directory, exist_ok=True)
    md, url = summary_md(sc)
    mid = sc.get("matchId", "unknown")
    path = os.path.join(directory, "debatetimer-%s.md" % mid[:8])
    front = "---\nsource: debatetimer.cn MCP get_debate_summary\nmatch_id: %s\nurl: %s\nfetched: %s\n---\n\n" % (
        mid, url, _dt.datetime.now().replace(microsecond=0).isoformat())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(front + md)
    return path


# ---------------------------------------------------------------- commands

def cmd_search(a):
    args = {"query": a.query, "searchType": a.type, "page": a.page, "pageSize": a.size}
    res = call_tool("search_debates", args)
    sc = res.get("structuredContent") or {}
    if a.json:
        for it in sc.get("items") or []:
            it["recordPageUrl"] = fix_url(it.get("recordPageUrl"), it.get("matchId"))
        print(json.dumps(sc, ensure_ascii=False, indent=2))
        return
    items = sc.get("items") or []
    print("🔎 「%s」（%s）第 %s 页：%d 场%s ｜ 今日剩余额度 %s" % (
        a.query, a.type, sc.get("page", a.page), len(items), "，还有更多" if sc.get("hasMore") else "", sc.get("quotaRemaining", "?")))
    if not items:
        print("   0 命中 —— 搜索为题目子串匹配：换更短/更泛的关键词（如「老家」→「大城市」「小城市」「返乡」），"
              "或改用 --type team / tournament，仍无结果则走 site:debatetimer.cn 搜索引擎兜底。")
    for k, it in enumerate(items, 1):
        print(fmt_item(k, it))


def cmd_summary(a):
    args = {"matchId": a.match_id}
    if a.passcode:
        args["passcode"] = a.passcode
    res = call_tool("get_debate_summary", args)
    sc = res.get("structuredContent") or {}
    if a.json:
        sc["recordPageUrl"] = fix_url(sc.get("recordPageUrl"), sc.get("matchId"))
        print(json.dumps(sc, ensure_ascii=False, indent=2))
        return
    if a.save:
        print("✓ 已保存：%s" % save_summary(a.save, sc))
    print(summary_md(sc)[0])


def cmd_batch(a):
    ids = a.match_ids[:20]
    if len(a.match_ids) > 20:
        print("（最多 20 场/次，已截取前 20 场）", file=sys.stderr)
    res = call_tool("batch_get_debate_summary", {"requests": [{"matchId": i} for i in ids]})
    sc = res.get("structuredContent") or {}
    results = sc.get("results") or sc.get("items") or []
    if a.json:
        print(json.dumps(sc, ensure_ascii=False, indent=2))
        return
    print("📦 批量获取 %d 场 ｜ 今日剩余额度 %s\n" % (len(results), sc.get("quotaRemaining", "?")))
    for r in results:
        if a.save and r.get("summary"):
            print("✓ 已保存：%s" % save_summary(a.save, r))
        print(summary_md(r)[0])
        print("\n" + "-" * 60 + "\n")


def cmd_tools(a):
    resp, _ = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    for t in (resp.get("result") or {}).get("tools") or []:
        print("- %s：%s" % (t.get("name"), (t.get("description") or "").split("\n")[0]))


def main(argv=None):
    p = argparse.ArgumentParser(prog="debatetimer", description="debatetimer.cn 官方 MCP 命令行客户端")
    p.add_argument("--json", action="store_true", help="输出原始 JSON")
    sub = p.add_subparsers(dest="cmd")
    q = sub.add_parser("search")
    q.add_argument("query")
    q.add_argument("--type", default="topic", choices=["topic", "team", "tournament"])
    q.add_argument("--page", type=int, default=1)
    q.add_argument("--size", type=int, default=10)
    q.set_defaults(func=cmd_search)
    q = sub.add_parser("summary")
    q.add_argument("match_id")
    q.add_argument("--passcode")
    q.add_argument("--save", help="保存为 Markdown 的目录（例如 <session>/research）")
    q.set_defaults(func=cmd_summary)
    q = sub.add_parser("batch")
    q.add_argument("match_ids", nargs="+")
    q.add_argument("--save")
    q.set_defaults(func=cmd_batch)
    q = sub.add_parser("tools")
    q.set_defaults(func=cmd_tools)
    a = p.parse_args(argv)
    if not getattr(a, "func", None):
        p.print_help()
        return 1
    try:
        a.func(a)
    except MCPError as exc:
        print("✗ debatetimer MCP 调用失败：%s\n  → 兜底：用搜索引擎检索 site:debatetimer.cn %s" % (
            exc, getattr(a, "query", "")), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
