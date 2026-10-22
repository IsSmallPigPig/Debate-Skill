/* 辩论协同台 · Debate Collab —— 纯原生 JS，无外部依赖。所有请求均为相对 URL。 */
(function () {
  "use strict";

  // ------------------------------------------------------------ state & helpers
  const S = {
    sessions: [], sid: null, summary: null, steps: [], docs: [], stages: {}, threads: [],
    version: null, docKey: null, doc: null, basket: [],
    target: "教练（跳出角色）", intent: "解释", follow: false, blockSig: {}, lastTemplate: "",
    polling: false, liveOk: true,
  };
  const INTENT_TPL = {
    "解释": "请解释这段的论证思路：它想钉住什么？在全场攻防里起什么作用？",
    "反驳": "请以对方辩手的身份现场反驳这段（真实辩场用语，约 1 分钟）。",
    "补强": "这段有什么漏洞？请给出补强方案，以及可以直接替换的说法。",
    "核验事实": "请核验这段中的事实与数据：给出可访问的来源 URL，并更新证据台账 evidence.md。",
    "改写": "请按以下要求改写这段，并写回原文件：",
    "自定义": "",
  };
  const STATUS_TXT = { done: "已完成", issues: "未通过校验", in_progress: "进行中", pending: "未开始", skipped: "已跳过" };
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const enc = encodeURIComponent;
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtNum = (n) => (n || 0).toLocaleString("zh-CN");
  const norm = (s) => String(s || "").replace(/[\s\u3000]+/g, "");

  async function api(path, opts) {
    const r = await fetch(path, Object.assign({ cache: "no-store" }, opts || {}));
    if (!r.ok) {
      let msg = r.status + "";
      try { msg = (await r.json()).error || msg; } catch (e) { /* ignore */ }
      throw new Error(msg);
    }
    return r.json();
  }

  let toastTimer = null;
  function toast(msg, ms) {
    const t = $("#toast");
    t.innerHTML = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, ms || 2600);
  }

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (e) { /* fall through */ }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(ta);
    ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    if (!ok) manualCopy(text);
    return ok;
  }

  function manualCopy(text) {
    let m = $("#manualCopy");
    if (!m) {
      m = document.createElement("div");
      m.id = "manualCopy";
      m.style.cssText = "position:fixed;inset:0;background:rgba(15,23,42,.35);z-index:80;display:grid;place-items:center";
      m.innerHTML = '<div style="background:#fff;border-radius:14px;padding:16px;width:min(640px,92vw);box-shadow:0 12px 32px rgba(0,0,0,.2)">' +
        '<div style="font-weight:700;margin-bottom:6px">浏览器禁止了自动复制，请手动复制（Ctrl/⌘ + C）</div>' +
        '<textarea style="height:260px;font-family:var(--mono);font-size:12px"></textarea>' +
        '<div style="text-align:right;margin-top:8px"><button class="btn" id="manualClose">关闭</button></div></div>';
      document.body.appendChild(m);
      m.addEventListener("click", (e) => { if (e.target === m || e.target.id === "manualClose") m.remove(); });
    }
    const ta = $("textarea", m);
    ta.value = text;
    setTimeout(() => { ta.focus(); ta.select(); }, 30);
  }

  // ------------------------------------------------------------ routing
  function parseHash() {
    const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map((p) => {
      try { return decodeURIComponent(p); } catch (e) { return p; }
    });
    const out = { sid: parts[0] || null, key: parts[1] || null, block: null };
    if (parts[2] && /^b\d+$/.test(parts[2])) out.block = parseInt(parts[2].slice(1), 10);
    return out;
  }
  function setHash(block) {
    const bits = [S.sid, S.docKey].filter(Boolean).map(enc);
    if (block) bits.push("b" + block);
    history.replaceState(null, "", "#/" + bits.join("/"));
  }

  // ------------------------------------------------------------ boot
  async function boot() {
    bindUI();
    let data;
    try {
      data = await api("api/sessions");
    } catch (e) {
      $("#doc").innerHTML = '<div class="empty"><h2>无法连接协同台服务</h2><p>' + esc(e.message) + "</p></div>";
      return;
    }
    S.sessions = data.sessions || [];
    renderSessionSelect();
    if (!S.sessions.length) {
      renderEmpty(data.root);
      startPolling();
      return;
    }
    const h = parseHash();
    const sid = S.sessions.some((s) => s.id === h.sid) ? h.sid : S.sessions[0].id;
    await openSession(sid, h.key, h.block);
    startPolling();
  }

  function renderEmpty(root) {
    $("#progressCard").innerHTML = "";
    $("#navTree").innerHTML = "";
    $("#topicLine").innerHTML = '<span class="t muted">尚无会话</span>';
    $("#doc").innerHTML =
      '<div class="empty"><h2>还没有任何辩论会话</h2>' +
      "<p>协同台正在监听：<code>" + esc(root) + "</code><br>让 Agent 以 <code>output=web</code> 运行 <code>/debate</code>，或手动创建一个会话：</p>" +
      "<pre>python3 tools/debate_ctl.py init --topic \"年轻人该不该回老家发展\" \\\n  --pro \"年轻人应该回老家发展\" --con \"年轻人不应该回老家发展\" \\\n  --side 正方 --preset full</pre>" +
      "<p>Agent 每写入一个 <code>transcript/*.md</code>，这里会在 1.5 秒内自动出现。</p></div>";
  }

  async function openSession(sid, key, block) {
    S.sid = sid;
    S.docKey = null;
    S.doc = null;
    $("#sessionSelect").value = sid;
    await loadSession();
    const docs = S.docs;
    let target = key && docs.some((d) => d.key === key) ? key : null;
    if (!target) {
      const tr = docs.filter((d) => d.group === "transcript");
      const latest = tr.slice().sort((a, b) => b.mtime - a.mtime)[0];
      target = (latest || docs[0] || {}).key || null;
    }
    if (target) await openDoc(target, block);
    else renderNoDoc();
  }

  async function loadSession() {
    const data = await api("api/session?id=" + enc(S.sid));
    S.summary = data.summary;
    S.steps = data.steps || [];
    S.docs = data.docs || [];
    S.stages = data.stages || {};
    S.threads = data.threads || [];
    S.version = data.version;
    renderTop();
    renderProgress();
    renderNav();
    renderThreadList();
  }

  // ------------------------------------------------------------ top bar
  function renderSessionSelect() {
    const sel = $("#sessionSelect");
    sel.innerHTML = S.sessions.map((s) => '<option value="' + esc(s.id) + '">' + esc(s.topic) + " · " + esc(s.id) + "</option>").join("");
    sel.hidden = S.sessions.length < 2;
  }

  function renderTop() {
    const s = S.summary || {};
    const sides = s.sides || {};
    const pill = (side, cls) => sides[side]
      ? '<span class="side-pill ' + cls + '" title="' + esc(side + "：" + sides[side]) + '">' + side + "：" + esc(sides[side]) +
        (s.user_side === side ? '<span class="you">· 你</span>' : "") + "</span>"
      : "";
    $("#topicLine").innerHTML = '<span class="t" title="' + esc(s.topic) + '">' + esc(s.topic || "") + "</span>" + pill("正方", "pro") + pill("反方", "con");
    document.title = (s.topic ? s.topic + " · " : "") + "辩论协同台";
  }

  function renderProgress() {
    const s = S.summary || {};
    const pct = s.total ? Math.round((s.done / s.total) * 100) : 0;
    const cur = S.steps.find((r) => r.id === s.current) || S.steps.find((r) => r.status === "in_progress");
    $("#progressCard").innerHTML =
      '<div class="pc-row"><span class="pc-preset">' + esc(s.preset_label || s.preset || "") + (s.mode ? " · " + esc(s.mode) : "") + "</span>" +
      '<span class="pc-count">' + (s.done || 0) + "<small> / " + (s.total || 0) + " 步</small></span></div>" +
      '<div class="bar"><i style="width:' + pct + '%"></i></div>' +
      '<div class="pc-chars">实测 ' + fmtNum(s.chars) + " 字 · 下限合计 " + fmtNum(s.min_chars) + " 字</div>" +
      (cur ? '<div class="pc-current">▶ 当前：<b>' + esc(cur.id) + "</b> " + esc(cur.nav.replace(/^\S+\s/, "")) + "</div>" : "") +
      '<label class="pc-follow"><input type="checkbox" id="followToggle"' + (S.follow ? " checked" : "") + "> 跟随直播（自动打开最新写入的环节）</label>";
    $("#followToggle").addEventListener("change", (e) => {
      S.follow = e.target.checked;
      toast(S.follow ? "已开启跟随直播：Agent 写到哪里，这里就跳到哪里" : "已关闭跟随直播");
    });
  }

  // ------------------------------------------------------------ nav
  function stepLabel(r) {
    let lbl = r.nav;
    const m = r.id.match(/^R05-(正方|反方)$/);
    if (m) lbl += "（" + m[1] + "）";
    return lbl;
  }

  function renderNav() {
    const byStage = {};
    S.steps.forEach((r) => { (byStage[r.stage] = byStage[r.stage] || []).push(r); });
    const parts = [];
    Object.keys(S.stages).forEach((st) => {
      const rows = byStage[st];
      if (!rows || !rows.length) return;
      const done = rows.filter((r) => r.status === "done").length;
      parts.push('<div class="nav-group"><div class="nav-stage"><span>' + st + " · " + esc(S.stages[st]) + "</span><span>" + done + "/" + rows.length + "</span></div>");
      let lastSide = null;
      rows.forEach((r) => {
        const sm = r.id.match(/^B\d-(正方|反方)$/);
        if (sm && sm[1] !== lastSide) {
          lastSide = sm[1];
          parts.push('<div class="nav-sub">' + sm[1] + "</div>");
        }
        parts.push(navItemHtml(r));
      });
      parts.push("</div>");
    });
    const extra = S.docs.filter((d) => d.group !== "transcript" || !d.step || !S.steps.some((r) => r.doc === d.key));
    const groups = { artifact: "稿件 · 可直接 Word 打印", evidence: "证据台账", research: "检索资料（debatetimer 等）", other: "其它文件", transcript: "未识别的实录文件" };
    Object.keys(groups).forEach((g) => {
      const ds = extra.filter((d) => d.group === g);
      if (!ds.length) return;
      parts.push('<div class="nav-group"><div class="nav-stage"><span>' + groups[g] + "</span><span>" + ds.length + "</span></div>");
      ds.forEach((d) => {
        parts.push('<button class="nav-item' + (d.key === S.docKey ? " active" : "") + '" data-key="' + esc(d.key) + '">' +
          '<span class="st file">' + ({ evidence: "证", research: "检" }[g] || "文") + '</span><span class="lbl" title="' + esc(d.title) + '">' +
          esc(d.path.split("/").pop().replace(/\.md$/, "")) + "</span></button>");
      });
      parts.push("</div>");
    });
    $("#navTree").innerHTML = parts.join("");
  }

  function navItemHtml(r) {
    const has = !!r.doc;
    const cls = ["nav-item"];
    if (has && r.doc === S.docKey) cls.push("active");
    if (!has) cls.push("disabled");
    const icon = { done: "✓", issues: "!", in_progress: "", pending: "", skipped: "–" }[r.status] || "";
    let cnt = "";
    if (has && r.min_chars) cnt = '<span class="cnt' + (r.chars < r.min_chars ? " bad" : "") + '">' + fmtNum(r.chars) + "/" + fmtNum(r.min_chars) + "</span>";
    else if (has) cnt = '<span class="cnt">' + fmtNum(r.chars) + "</span>";
    else if (r.min_chars) cnt = '<span class="cnt">≥' + fmtNum(r.min_chars) + "</span>";
    const tip = r.title + " · " + (STATUS_TXT[r.status] || r.status) + (r.errors ? " · " + r.errors + " 项硬性问题" : "") + (r.warnings ? " · " + r.warnings + " 项建议" : "");
    return '<button class="' + cls.join(" ") + '" ' + (has ? 'data-key="' + esc(r.doc) + '"' : 'data-step="' + esc(r.id) + '"') + ' title="' + esc(tip) + '">' +
      '<span class="st ' + r.status + '">' + icon + '</span><span class="lbl">' + esc(stepLabel(r)) + "</span>" + cnt + "</button>";
  }

  // ------------------------------------------------------------ document
  async function openDoc(key, block, opts) {
    opts = opts || {};
    const prevKey = S.docKey;
    const main = $("#main");
    const keepScroll = opts.keepScroll && prevKey === key ? main.scrollTop : null;
    let p;
    try {
      p = await api("api/doc?id=" + enc(S.sid) + "&key=" + enc(key));
    } catch (e) {
      toast("打开失败：" + esc(e.message));
      return;
    }
    const oldSig = prevKey === key ? S.blockSig : {};
    S.docKey = key;
    S.doc = p;
    renderDoc(p);
    $$(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.key === key));
    const sig = {};
    p.blocks.forEach((b) => { sig[b.i] = b.plain; });
    S.blockSig = sig;
    if (prevKey === key && Object.keys(oldSig).length) {
      let changed = 0;
      p.blocks.forEach((b) => {
        if (oldSig[b.i] !== b.plain) {
          changed++;
          const el = $("#b" + b.i);
          if (el) el.classList.add("flash");
        }
      });
      if (changed && opts.announce) toast("「" + esc(p.doc.nav) + "」更新了 " + changed + " 段");
    }
    if (block) {
      focusBlock(block);
      setHash(block);
    } else {
      setHash();
      if (keepScroll != null) main.scrollTop = keepScroll;
      else if (opts.toBottom) main.scrollTop = main.scrollHeight;
      else if (prevKey !== key) main.scrollTop = 0;
    }
    if (window.innerWidth <= 820) $("#sidebar").classList.remove("open");
  }

  function focusBlock(i) {
    const el = $("#b" + i);
    if (!el) return;
    $$(".blk.target").forEach((x) => x.classList.remove("target"));
    el.classList.add("target");
    el.scrollIntoView({ block: "center", behavior: "smooth" });
  }

  function blockLabel(b) {
    let s = "¶" + b.i;
    if (b.turn) s += " · " + b.turn.label + (b.turn.note ? "（" + b.turn.note + "）" : "");
    else if (b.type === "heading") s += " · 标题";
    else if (b.type === "table") s += " · 表格";
    return s;
  }

  function issuesByBlock(lint) {
    const map = {};
    if (!lint) return map;
    lint.checks.forEach((c) => {
      (c.blocks || []).forEach((i) => { (map[i] = map[i] || []).push(c); });
    });
    return map;
  }

  function threadAnchors(p) {
    // 线程挂到哪一段：优先用原文匹配（防止块编号漂移），否则用锚点编号
    const map = {};
    (p.threads || []).forEach((th) => {
      (th.refs || []).forEach((r) => {
        if (r.key !== p.doc.key) return;
        let idx = parseInt(String(r.anchor || "b0").slice(1), 10) || 0;
        const q = norm(r.quote).slice(0, 40);
        if (q) {
          const hits = p.blocks.filter((b) => norm(b.plain).indexOf(q) >= 0);
          if (hits.length) {
            hits.sort((a, b) => Math.abs(a.i - idx) - Math.abs(b.i - idx));
            idx = hits[0].i;
          }
        }
        if (idx) (map[idx] = map[idx] || []).push(th);
      });
    });
    return map;
  }

  function renderDoc(p) {
    const d = p.doc;
    const lint = p.lint;
    const spec = p.spec || {};
    const stageName = d.stage ? d.stage + " · " + (S.stages[d.stage] || "") : ({ artifact: "稿件", evidence: "证据台账", research: "检索资料", other: "文件" }[d.group] || "文件");
    const tags = [];
    if (spec.duration && spec.duration !== "—") tags.push('<span class="tag">⏱ ' + esc(spec.duration) + (spec.timing && spec.timing !== "—" ? " · " + esc(spec.timing) + "计时" : "") + "</span>");
    if (spec.prompt) tags.push('<span class="tag" title="对应 Prompt 小节">' + esc(spec.prompt.replace("prompts/round_prompts.md ", "prompts ")) + "</span>");
    (p.speakers || []).forEach((sp) => {
      const cls = sp.role.indexOf("正方") === 0 ? "pro" : sp.role.indexOf("反方") === 0 ? "con" : "";
      tags.push('<span class="tag ' + cls + '">' + esc(sp.role) + (sp.name ? " · " + esc(sp.name) : "") + "</span>");
    });
    tags.push('<span class="tag" title="文件路径">' + esc(d.path) + "</span>");

    let lintHtml = "";
    if (lint) {
      const chips = lint.chips.map((c) => '<span class="chip ' + (c.ok ? "ok" : "bad") + '">' + esc(c.label) + " " + esc(c.value) + (c.ok ? " ✓" : " ✗") + "</span>");
      if (lint.warnings) chips.push('<span class="chip warn">建议 ' + lint.warnings + "</span>");
      const n = lint.checks.length;
      lintHtml = '<div class="lint-bar">' + chips.join("") + (n ? '<button class="link" id="toggleChecks">' + (lint.pass ? "查看 " + n + " 条建议" : "查看 " + n + " 条问题") + "</button>" : '<span class="chip ok">机器校验通过</span>') + "</div>";
      if (n) {
        lintHtml += '<ul class="checks" id="checksList"' + (lint.pass ? " hidden" : "") + ">" + lint.checks.map((c) =>
          '<li class="' + c.level + '"><span class="lv">' + (c.level === "error" ? "✗" : "⚠") + "</span><span>" + esc(c.msg) + "</span>" +
          (c.blocks && c.blocks.length ? '<button class="link go" data-goto="' + c.blocks[0] + '">¶' + c.blocks.slice(0, 4).join(",") + "</button>" : "") + "</li>").join("") + "</ul>";
      }
    }

    const issues = issuesByBlock(lint);
    const tmap = threadAnchors(p);
    const firstHeading = p.blocks.find((b) => b.type === "heading");
    const dupTitle = firstHeading && norm(firstHeading.plain) === norm(d.title) ? firstHeading.i : 0;
    const blocks = p.blocks.map((b) => {
      const cls = ["blk"];
      if (b.i === dupTitle) cls.push("dup-title");
      if (b.turn) cls.push("blk-turn", b.turn.side === "正方" ? "pro" : b.turn.side === "反方" ? "con" : "neutral");
      const iss = issues[b.i];
      const dot = iss ? '<span class="issue-dot' + (iss.some((c) => c.level === "error") ? " error" : "") + '" title="' + esc(iss.map((c) => c.msg).join("\n")) + '"></span>' : "";
      const ths = tmap[b.i] || [];
      return '<div class="' + cls.join(" ") + '" id="b' + b.i + '" data-i="' + b.i + '">' +
        '<div class="gutter"><a class="anchor" href="#" data-goto="' + b.i + '" title="' + esc(p.uri_prefix + "#b" + b.i) + '">¶' + b.i + "</a></div>" + dot +
        '<div class="content">' + b.html + "</div>" +
        '<div class="tools"><button data-act="copy" title="复制【辩论协同·提问】到剪贴板，粘贴给 Agent">⧉ 复制位置</button>' +
        '<button data-act="ask" title="加入引用篮并打开提问面板">💬 提问</button><span class="sep"></span>' +
        '<button data-act="add" title="加入引用篮（可多选后一起提问）">＋ 引用</button></div>' +
        (ths.length ? '<button class="thread-count" data-toggle-threads="' + b.i + '" title="协同问答">💬' + ths.length + "</button>" : "") +
        (ths.length ? '<div class="threads" id="th' + b.i + '">' + ths.map(threadHtml).join("") + "</div>" : "") +
        "</div>";
    }).join("");

    $("#doc").innerHTML =
      '<header class="doc-head"><div class="crumbs">' + esc(stageName) + (d.step ? " · " + esc(d.step) : "") + "</div>" +
      '<h1 class="doc-title">' + esc(d.title) + "</h1>" +
      '<div class="doc-meta">' + tags.join("") + "</div>" + lintHtml +
      '<div class="doc-actions"><button class="btn sm" data-exp="doc:docx">⬇ Word</button><button class="btn sm" data-exp="doc:md">⬇ Markdown</button>' +
      '<button class="btn sm" data-exp="doc:html">⬇ HTML</button><button class="btn sm" data-exp="print">🖨 打印 / PDF</button>' +
      '<button class="btn sm" id="copyDocRef">⧉ 复制本文档位置</button></div></header>' +
      '<section class="blocks" id="blocks">' + (blocks || '<div class="placeholder"><div class="big">✎</div>文件是空的，等待 Agent 写入…</div>') + "</section>";
  }

  function threadHtml(th) {
    const when = (th.answered || th.created || "").replace("T", " ").slice(5, 16);
    const quote = (th.refs && th.refs[0] && th.refs[0].quote) || "";
    return '<div class="thread' + (th.answer ? "" : " pending") + '" id="thr-' + esc(th.id) + '">' +
      '<div class="th-head"><span class="who">' + esc(th.target || "教练") + "</span><span>· " + esc(th.intent || "提问") + "</span><span>· " + esc(when) + "</span>" +
      '<span class="th-status">' + (th.answer ? "已回答" : "等待 Agent") + "</span></div>" +
      (quote ? '<div class="th-quote">「' + esc(quote.slice(0, 120)) + (quote.length > 120 ? "…" : "") + "」</div>" : "") +
      '<div class="th-q"><b>问：</b>' + esc(th.question || "（无文字问题）") + "</div>" +
      (th.answer ? '<div class="th-a">' + (th.answer_html || esc(th.answer)) + "</div>" : "") + "</div>";
  }

  function renderNoDoc() {
    $("#doc").innerHTML = '<div class="placeholder" style="padding:80px 20px"><div class="big">⌛</div>会话已创建，Agent 还没有写入任何文件。<br>写入后这里会自动出现（每 1.5 秒同步一次）。</div>';
  }

  function renderPendingStep(stepId) {
    const r = S.steps.find((x) => x.id === stepId);
    if (!r) return;
    S.docKey = null;
    $$(".nav-item").forEach((el) => el.classList.toggle("active", el.dataset.step === stepId));
    const sp = (r.speakers || []).map((x) => esc(x.role + (x.name ? " · " + x.name : ""))).join("、") || "—";
    $("#doc").innerHTML =
      '<header class="doc-head"><div class="crumbs">' + esc(r.stage + " · " + (S.stages[r.stage] || "")) + " · " + esc(r.id) + '</div><h1 class="doc-title">' + esc(r.title) + "</h1>" +
      '<div class="doc-meta"><span class="tag">' + esc(STATUS_TXT[r.status] || r.status) + "</span></div></header>" +
      '<div class="placeholder" style="text-align:left;line-height:2">' +
      "<div>⏳ 该环节尚未生成。Agent 运行到这里时会写入：</div>" +
      "<div><code>transcript/" + esc(r.file) + "</code></div>" +
      "<div>Prompt：<code>" + esc(r.prompt) + "</code></div>" +
      "<div>参与：" + sp + "</div>" +
      "<div>时长：" + esc(r.duration) + " · 计时：" + esc(r.timing) + " · 字数下限：" + fmtNum(r.min_chars) + "</div></div>";
  }

  // ------------------------------------------------------------ refs & basket
  function makeRef(blockI, quote) {
    const p = S.doc;
    const b = p.blocks.find((x) => x.i === blockI);
    if (!b) return null;
    let q = (quote || b.plain || "").trim().replace(/\s+/g, " ");
    if (!quote && q.length > 180) q = q.slice(0, 180) + "…";
    if (quote && q.length > 400) q = q.slice(0, 400) + "…";
    return {
      uri: p.uri_prefix + "#b" + b.i,
      key: p.doc.key,
      anchor: "b" + b.i,
      quote: q,
      where: p.doc.title + " › " + blockLabel(b),
      short: (p.doc.step || p.doc.nav || p.doc.key) + " ¶" + b.i + (b.turn ? " · " + b.turn.label : ""),
    };
  }

  function compose(refs, question) {
    const s = S.summary || {};
    let out = "【辩论协同·提问】\n会话：" + (s.topic || "") + "（" + S.sid + "）\n提问对象：" + S.target + "｜意图：" + S.intent + "\n";
    refs.forEach((r, k) => {
      out += "\n[" + (k + 1) + "] " + r.uri + "\n    位置：" + r.where + "\n    原文：「" + r.quote + "」\n";
    });
    out += "\n问题：" + (question && question.trim() ? question.trim() : "（在这里写下你的问题）") + "\n";
    out += "（Agent：请按 Debate-Skill collab/PROTOCOL.md §3 处理——先用 tools/debate_ctl.py locate 定位原文，再回答，最后用 ask new 回写 qa/threads.jsonl）";
    return out;
  }

  function addToBasket(ref, silent) {
    if (!ref) return;
    if (S.basket.some((r) => r.uri === ref.uri && r.quote === ref.quote)) {
      if (!silent) toast("这个位置已经在引用篮里了");
      return;
    }
    S.basket.push(ref);
    renderBasket();
    if (!silent) toast("已加入引用篮（" + S.basket.length + "）· 可继续选择其它位置后一起提问");
  }

  function renderBasket() {
    const n = S.basket.length;
    const badge = $("#basketCount");
    badge.textContent = n;
    badge.classList.toggle("zero", !n);
    $("#basket").innerHTML = n
      ? S.basket.map((r, k) => '<div class="ref"><div class="r1"><code>' + esc(r.anchor) + "</code>" + esc(r.short) + "</div>" +
        '<div class="r2">「' + esc(r.quote) + '」</div><button class="x" data-rm="' + k + '" title="移除">×</button></div>').join("")
      : '<div class="basket-empty">悬停正文段落 → 点「＋ 引用」或「💬 提问」；<br>也可以直接<b>选中一段文字</b>，引用会精确到你选的那句话。<br>可以一次引用多个位置（例如对比 R02 与 R08 是否矛盾）。</div>';
    updatePreview();
  }

  function updatePreview() {
    $("#askPreview").textContent = S.basket.length ? compose(S.basket, $("#question").value) : "（引用篮为空）";
  }

  function openPanel(focusQuestion) {
    $("#layout").classList.remove("panel-closed");
    if (focusQuestion) setTimeout(() => $("#question").focus(), 60);
  }

  // ------------------------------------------------------------ threads (panel list)
  function renderThreadList() {
    const ths = (S.threads || []).slice().reverse();
    const answered = ths.filter((t) => t.answer).length;
    $("#threadStats").textContent = ths.length ? "（" + answered + "/" + ths.length + " 已回答）" : "";
    $("#threadList").innerHTML = ths.length
      ? ths.map((t) => {
        const r = (t.refs || [])[0] || {};
        return '<div class="ti" data-thread="' + esc(t.id) + '" data-key="' + esc(r.key || "") + '" data-anchor="' + esc(r.anchor || "") + '">' +
          '<div class="t1"><span>' + esc(r.key || "") + " " + esc(r.anchor || "") + "</span><span>· " + esc(t.intent || "") + '</span><span class="s ' + (t.answer ? "answered" : "pending") + '">' + (t.answer ? "已回答" : "待回答") + "</span></div>" +
          '<div class="t2">' + esc(t.question || r.quote || "") + "</div></div>";
      }).join("")
      : '<div class="basket-empty">还没有问答。用「加入待答队列」提交的问题、以及 Agent 回写的答案都会显示在这里和原文旁边。</div>';
  }

  // ------------------------------------------------------------ export
  function doExport(spec) {
    if (spec === "print") {
      document.body.classList.toggle("print-qa", $("#optQa").checked);
      window.print();
      return;
    }
    const [kind, fmt] = spec.split(":");
    let url = "api/export?id=" + enc(S.sid) + "&fmt=" + (fmt || "zip") +
      "&clean=" + ($("#optClean").checked ? 1 : 0) + "&qa=" + ($("#optQa").checked ? 1 : 0) + "&disclaimer=" + ($("#optDisclaimer").checked ? 1 : 0);
    if (kind === "doc") {
      if (!S.docKey) { toast("请先打开一个文档"); return; }
      url += "&key=" + enc(S.docKey);
    } else if (kind === "all") {
      url += "&key=__all__";
    }
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast("正在生成并下载…");
  }

  // ------------------------------------------------------------ live sync
  function setLive(ok) {
    if (ok === S.liveOk) return;
    S.liveOk = ok;
    $("#liveDot").classList.toggle("off", !ok);
    $("#liveText").textContent = ok ? "实时" : "离线";
  }

  function startPolling() {
    if (S.polling) return;
    S.polling = true;
    const tick = async () => {
      try {
        if (!S.sid) {
          const data = await api("api/sessions");
          if ((data.sessions || []).length) {
            S.sessions = data.sessions;
            renderSessionSelect();
            await openSession(S.sessions[0].id);
          }
        } else {
          const v = await api("api/version?id=" + enc(S.sid));
          if (v.version !== S.version) await onChange();
        }
        setLive(true);
      } catch (e) {
        setLive(false);
      }
      setTimeout(tick, 1500);
    };
    setTimeout(tick, 1500);
  }

  async function onChange() {
    const before = {};
    S.docs.forEach((d) => { before[d.key] = d.mtime; });
    const prevThreads = JSON.stringify(S.threads);
    await loadSession();
    const changed = S.docs.filter((d) => before[d.key] !== d.mtime);
    const threadsChanged = JSON.stringify(S.threads) !== prevThreads;
    const newest = changed.filter((d) => d.group === "transcript").sort((a, b) => b.mtime - a.mtime)[0] || changed[0];
    if (newest && (!S.doc || (S.follow && newest.key !== S.docKey))) {
      await openDoc(newest.key, null, { toBottom: true });
      toast("📡 已打开最新写入的「" + esc(newest.nav) + "」");
      return;
    }
    const docChanged = !!S.docKey && changed.some((d) => d.key === S.docKey);
    if (S.docKey && (docChanged || threadsChanged)) {
      const main = $("#main");
      const atBottom = main.scrollTop + main.clientHeight >= main.scrollHeight - 40;
      const follow = S.follow && atBottom && docChanged;
      await openDoc(S.docKey, null, { keepScroll: !follow, toBottom: follow, announce: docChanged });
      if (threadsChanged && !docChanged) toast("💬 协同问答有更新");
    }
    if (!S.follow && newest && newest.key !== S.docKey && newest.group === "transcript") {
      toast("「" + esc(newest.nav) + "」有新内容 · <a href='#' style='color:#9fe3ee' data-open='" + esc(newest.key) + "'>打开</a>", 5000);
    }
  }

  // ------------------------------------------------------------ search
  let searchTimer = null;
  function onSearchInput() {
    clearTimeout(searchTimer);
    const q = $("#searchInput").value.trim();
    const box = $("#searchResults");
    if (!q) { box.hidden = true; return; }
    searchTimer = setTimeout(async () => {
      try {
        const data = await api("api/search?id=" + enc(S.sid) + "&q=" + enc(q));
        const hits = data.hits || [];
        const re = new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
        box.innerHTML = hits.length
          ? hits.map((h) => '<button class="search-hit" data-key="' + esc(h.key) + '" data-i="' + h.i + '"><div class="h1">' + esc(h.nav) + " · " + esc(h.label) + '</div><div class="h2">' +
            esc(h.snippet).replace(re, (m) => "<mark>" + m + "</mark>") + "</div></button>").join("")
          : '<div class="placeholder" style="padding:16px">没有找到「' + esc(q) + "」</div>";
        box.hidden = false;
      } catch (e) { box.hidden = true; }
    }, 220);
  }

  // ------------------------------------------------------------ selection popover
  let selRef = null;
  function onSelection() {
    const pop = $("#selPop");
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !S.doc) { pop.hidden = true; return; }
    const text = sel.toString().trim();
    if (text.length < 2) { pop.hidden = true; return; }
    const node = sel.anchorNode && (sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement);
    const blk = node && node.closest && node.closest(".blk");
    if (!blk || !$("#blocks").contains(blk)) { pop.hidden = true; return; }
    selRef = makeRef(parseInt(blk.dataset.i, 10), text);
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    pop.hidden = false;
    const w = pop.offsetWidth;
    pop.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, rect.left + rect.width / 2 - w / 2)) + "px";
    pop.style.top = Math.max(64, rect.top - 44) + "px";
  }

  // ------------------------------------------------------------ navigation from refs
  function gotoRef(uri) {
    const m = String(uri).match(/^debate:\/\/([^/]+)\/([^#]+)#b(\d+)/);
    if (!m) return;
    const go = () => openDoc(decodeURIComponent(m[2]), parseInt(m[3], 10));
    if (m[1] !== S.sid && S.sessions.some((s) => s.id === m[1])) openSession(m[1], decodeURIComponent(m[2]), parseInt(m[3], 10));
    else go();
  }

  // ------------------------------------------------------------ UI bindings
  function bindUI() {
    $("#sessionSelect").addEventListener("change", (e) => openSession(e.target.value));
    $("#navToggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
    $("#panelToggle").addEventListener("click", () => $("#layout").classList.toggle("panel-closed"));
    $("#panelClose").addEventListener("click", () => $("#layout").classList.add("panel-closed"));
    if (window.innerWidth <= 1080) $("#layout").classList.add("panel-closed");

    $("#navTree").addEventListener("click", (e) => {
      const it = e.target.closest(".nav-item");
      if (!it) return;
      if (it.dataset.key) openDoc(it.dataset.key);
      else if (it.dataset.step) renderPendingStep(it.dataset.step);
    });

    $("#exportBtn").addEventListener("click", (e) => { e.stopPropagation(); $("#exportMenu").hidden = !$("#exportMenu").hidden; });
    $("#exportMenu").addEventListener("click", (e) => {
      const b = e.target.closest("[data-exp]");
      if (b) { doExport(b.dataset.exp); $("#exportMenu").hidden = true; }
      e.stopPropagation();
    });

    $("#doc").addEventListener("click", async (e) => {
      const exp = e.target.closest("[data-exp]");
      if (exp) return doExport(exp.dataset.exp);
      const go = e.target.closest("[data-goto]");
      if (go) { e.preventDefault(); const i = parseInt(go.dataset.goto, 10); focusBlock(i); setHash(i); return; }
      const dref = e.target.closest("a.dref");
      if (dref) { e.preventDefault(); return gotoRef(dref.dataset.ref); }
      if (e.target.id === "toggleChecks") { const l = $("#checksList"); if (l) l.hidden = !l.hidden; return; }
      if (e.target.id === "copyDocRef") {
        const ref = makeRef(1);
        if (ref) {
          ref.where = S.doc.doc.title + " › 整份文档";
          ref.quote = (S.doc.blocks[0] && S.doc.blocks[0].plain || "").slice(0, 60);
          await copyText(compose([ref], ""));
          toast("已复制本文档位置 · 粘贴到 Agent 对话框，写上你的问题即可");
        }
        return;
      }
      const tt = e.target.closest("[data-toggle-threads]");
      if (tt) { const box = $("#th" + tt.dataset.toggleThreads); if (box) box.hidden = !box.hidden; return; }
      const act = e.target.closest(".tools button");
      if (act) {
        const blk = act.closest(".blk");
        const ref = makeRef(parseInt(blk.dataset.i, 10));
        if (act.dataset.act === "copy") {
          const ok = await copyText(compose([ref], ""));
          if (ok) toast("已复制 <b>" + esc(ref.short) + "</b> 的位置 · 粘贴到 Agent 对话框，写上你的问题即可");
        } else if (act.dataset.act === "ask") {
          addToBasket(ref, true);
          openPanel(true);
          toast("已加入引用篮，在右侧写下问题");
        } else if (act.dataset.act === "add") {
          addToBasket(ref);
        }
      }
    });

    document.addEventListener("mouseup", (e) => {
      if (e.target && e.target.closest && e.target.closest("#selPop")) return;
      setTimeout(onSelection, 10);
    });
    document.addEventListener("keyup", (e) => { if (e.shiftKey) setTimeout(onSelection, 10); });
    $("#main").addEventListener("scroll", () => { $("#selPop").hidden = true; }, { passive: true });
    $("#selPop").addEventListener("mousedown", (e) => e.preventDefault());
    $("#selPop").addEventListener("click", async (e) => {
      const b = e.target.closest("button");
      if (!b || !selRef) return;
      if (b.dataset.act === "sel-copy") {
        const ok = await copyText(compose([selRef], ""));
        if (ok) toast("已复制所选句子的位置 · 粘贴给 Agent 并写上问题");
      } else {
        addToBasket(selRef);
      }
      $("#selPop").hidden = true;
      window.getSelection().removeAllRanges();
    });

    $("#basket").addEventListener("click", (e) => {
      const rm = e.target.closest("[data-rm]");
      if (rm) { S.basket.splice(parseInt(rm.dataset.rm, 10), 1); renderBasket(); }
    });
    $("#basketClear").addEventListener("click", () => { S.basket = []; renderBasket(); });
    $("#targetSeg").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      $$("#targetSeg button").forEach((x) => x.classList.toggle("on", x === b));
      S.target = b.dataset.v;
      updatePreview();
    });
    $("#intentChips").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      $$("#intentChips button").forEach((x) => x.classList.toggle("on", x === b));
      S.intent = b.dataset.v;
      const qa = $("#question");
      if (!qa.value.trim() || qa.value === S.lastTemplate) {
        qa.value = INTENT_TPL[S.intent] || "";
        S.lastTemplate = qa.value;
      }
      if (S.intent === "反驳" && S.target.indexOf("教练") === 0) {
        $$("#targetSeg button").forEach((x) => x.classList.toggle("on", x.dataset.v.indexOf("对方") === 0));
        S.target = "对方辩手（保持人设）";
      }
      updatePreview();
    });
    $("#question").addEventListener("input", updatePreview);
    $("#copyAsk").addEventListener("click", async () => {
      if (!S.basket.length) { toast("请先在正文中选择至少一个位置（＋ 引用 / 选中文字）"); return; }
      const ok = await copyText(compose(S.basket, $("#question").value));
      if (ok) toast("已复制 " + S.basket.length + " 处引用 + 问题 · 粘贴到 Agent 对话框发送即可");
    });
    $("#queueAsk").addEventListener("click", async () => {
      if (!S.basket.length) { toast("请先在正文中选择至少一个位置"); return; }
      try {
        const res = await api("api/threads?id=" + enc(S.sid), {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refs: S.basket, intent: S.intent, target: S.target, question: $("#question").value }),
        });
        toast("已加入待答队列（" + esc(res.thread.id) + "）· 在 Agent 对话中输入 <b>/ask</b> 即可批量处理", 4200);
        S.basket = [];
        $("#question").value = "";
        renderBasket();
        await loadSession();
        if (S.docKey) await openDoc(S.docKey, null, { keepScroll: true });
      } catch (e) { toast("提交失败：" + esc(e.message)); }
    });
    $("#threadList").addEventListener("click", (e) => {
      const ti = e.target.closest(".ti");
      if (!ti || !ti.dataset.key) return;
      const i = parseInt((ti.dataset.anchor || "b0").slice(1), 10) || null;
      openDoc(ti.dataset.key, i);
    });

    $("#searchInput").addEventListener("input", onSearchInput);
    $("#searchResults").addEventListener("click", (e) => {
      const h = e.target.closest(".search-hit");
      if (!h) return;
      $("#searchResults").hidden = true;
      openDoc(h.dataset.key, parseInt(h.dataset.i, 10));
    });
    $("#toast").addEventListener("click", (e) => {
      const a = e.target.closest("[data-open]");
      if (a) { e.preventDefault(); openDoc(a.dataset.open, null, { toBottom: true }); $("#toast").hidden = true; }
    });

    document.addEventListener("click", (e) => {
      const t = e.target && e.target.closest ? e.target : document.body;
      if (!t.closest("#exportDrop")) $("#exportMenu").hidden = true;
      if (!t.closest(".search")) $("#searchResults").hidden = true;
    });
    document.addEventListener("keydown", (e) => {
      const typing = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "");
      if (e.key === "/" && !typing) { e.preventDefault(); $("#searchInput").focus(); }
      if (e.key === "Escape") {
        $("#exportMenu").hidden = true; $("#searchResults").hidden = true; $("#selPop").hidden = true;
      }
    });
    window.addEventListener("hashchange", () => {
      const h = parseHash();
      if (h.sid && h.sid !== S.sid) openSession(h.sid, h.key, h.block);
      else if (h.key && h.key !== S.docKey) openDoc(h.key, h.block);
      else if (h.block) focusBlock(h.block);
    });
    renderBasket();
  }

  boot();
})();
