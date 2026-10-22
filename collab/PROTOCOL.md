---
name: Debate-Skills/collab-protocol
version: 3.0.0
description: |
  编排器 ↔ 协同台 ↔ 用户 之间的协同协议：会话目录怎么写、断点怎么续、
  用户从网页复制来的【辩论协同·提问】怎么定位与回答、答案怎么回写到原文旁边。
  所有命令只依赖 Python 3.8+ 标准库。
---

# 协同输出协议（collab/PROTOCOL.md）

> 一句话：**编排器把每个环节写进文件，协同台把文件变成可读、可导出、可逐段追问的网页，
> 用户把「原文位置 + 问题」复制回来，编排器定位、回答、再写回去。**

```text
 编排器（Agent）                     会话目录 debate-output/<sid>/                 协同台（浏览器）
 ──────────────                     ─────────────────────────                   ────────────────
 debate_ctl init      ───────────▶  session.json                    ◀─ 轮询 ───  进度看板 / 导航
 演出环节 → 写文件     ───────────▶  transcript/R02-质询-….md         ◀─ 轮询 ───  逐段渲染 + 锚点 ¶N
 debate_ctl step done ── lint ───▶  （校验结果实时计算）              ◀─────────  字数/回合/违规定位
 写证据               ───────────▶  evidence.md                                   导出 docx / md / zip
                                     qa/threads.jsonl  ◀── 待答队列 ── 「加入待答队列」
 /ask 或粘贴提问 ◀──────────────────────────────────────── 剪贴板 ── 「复制位置并提问」
 debate_ctl ask … ── 回写答案 ──▶  qa/threads.jsonl                ── 轮询 ──▶ 答案显示在原文旁
```

---

## 1. 会话目录（编排器写，协同台读）

```text
debate-output/                         # 默认根目录（可用 --root 或环境变量 DEBATE_OUTPUT 修改）
└── <session_id>/                      # 由 debate_ctl.py init 生成，例如 20261015-2030-年轻人该不该回老家发展
    ├── session.json                   # 元数据 + 进度（见 §1.2）
    ├── transcript/                    # ★ 每个环节一个文件，文件名 = presets.json 里该步骤的 file 字段
    │   ├── A-开赛确认.md
    │   ├── B0-正方-历史实录检索.md
    │   ├── R01-申论-正方一辩.md
    │   ├── R02-质询-反四质询正一.md
    │   ├── …
    │   ├── J-评委点评.md
    │   └── S-主持人总结.md
    ├── artifacts/                     # 派生稿件（templates/artifacts_spec.md 的 #0a–#15）
    ├── research/                      # 检索原始资料（tools/debatetimer.py --save 写到这里）
    ├── evidence.md                    # 证据台账（templates/evidence_ledger.md）
    ├── qa/threads.jsonl               # 锚定问答（§5）
    └── exports/                       # debate_ctl.py export 的输出
```

### 1.1 transcript 文件规范

- **文件名前缀即步骤 ID**（`R02-…`、`B0-正方-…`、`H3-二辩…`），协同台据此归位；用 `debate_ctl.py next` 查看应写的文件名。
- 第一行是环节标题：`## 第 2 轮 · 质询｜反方四辩 → 正方一辩`，第二行是 `> 时长 2'30" · 单边计时` 副标题。
- **发言人标签**一律写成段首加粗 + 冒号：`**反方四辩 · 陈铭**：……`；备注放在标签后的括号里：
  `**正方二辩 · 颜如晶**（打岔 1/3）：……`、`**反方四辩 · 陈铭**（小结）：……`。
  这是 lint 计算回合/段数/交替、协同台着色与定位的依据。
- 段落之间空一行；**一个段落 = 一个锚点**（¶N）。
- 可选 front matter（`---` 包裹的 `key: value`）：`step`、`title`、`status`。不写也能识别。
- 重做时**原地覆盖**同名文件；协同台会高亮变化的段落。

### 1.2 session.json

```json
{
  "schema": "debate-session/1",
  "session_id": "20261015-2030-年轻人该不该回老家发展",
  "topic": "年轻人该不该回老家发展",
  "sides": {"正方": "年轻人应该回老家发展", "反方": "年轻人不应该回老家发展"},
  "user_side": "正方",
  "preset": "full",
  "mode": "isolated",
  "output": "web",
  "lineup": {"正方": {"一辩": "胡渐彪", "二辩": "颜如晶", "三辩": "黄执中", "四辩": "马薇薇"},
             "反方": {"一辩": "庞颖", "二辩": "周玄毅", "三辩": "詹青云", "四辩": "陈铭"}},
  "progress": {"current": "R03", "steps": {"R02": {"status": "done", "updated": "…"}}}
}
```

不要手改 `progress`，用 `debate_ctl.py step` 更新（它会在标记 done 前自动校验）。

---

## 2. 断点续跑（`/debate resume`）

触发：用户说 `/debate resume`、「继续上次的辩论」，或编排器自己判断上下文快满了。

```text
1. python3 tools/debate_ctl.py status [<session>|latest]     # 看清已完成 / 未通过 / 下一步
2. 读 session.json（辩题、持方、预设、阵容）——不要凭记忆
3. 读「下一步」所需的前文：
     · 该环节 prompt 要求回应的轮次（例如 R06 要回应 R03/R04）→ 读对应 transcript 文件
     · 本方 artifacts/<side>-备赛资料.md、前场整理
     · evidence.md
4. python3 tools/debate_ctl.py next <session>                # 得到 prompt 小节、参与者、下限、输出文件
5. 按 SKILL.md §6.0 继续：in_progress → 演出 → 写文件 → step done → 贴【校验】行
```

**上下文预算规则**：每完成一个阶段（B/C/D/E/F/G/H），若对话已很长，主动在对话里贴一次
`status`，此后只依赖文件续写；**引用对方原话必须从 transcript 文件复制**，不得凭印象改写。

---

## 3. 处理【辩论协同·提问】（用户粘贴到对话中）

用户在协同台点「复制位置」或「复制提问」后，粘贴进来的是：

```text
【辩论协同·提问】
会话：年轻人该不该回老家发展（20261015-2030-回老家发展）
提问对象：教练（跳出角色）｜意图：补强

[1] debate://20261015-2030-回老家发展/R02#b10
    位置：第 2 轮 · 质询｜反方四辩 → 正方一辩 › ¶10 · 正方一辩 · 胡渐彪
    原文：「我方不说他错，我方说这样的选择对普通年轻人来说风险更高。…」

问题：正一这里是不是答软了？有没有更好的接法？
```

### 3.1 处理步骤

1. **定位**（必须，不要只看剪贴板里的片段就回答）：
   ```bash
   python3 tools/debate_ctl.py locate - <<'EOF'
   <把整段粘贴内容原样放这里>
   EOF
   ```
   输出文件路径、行号、目标段落与上下文。**以「原文」为准、锚点为辅**：文件被改写后块编号可能漂移，
   工具会按原文自动纠偏（显示 `quote(drift +1)`）。无 shell 时：按 URI 打开
   `<session>/transcript/<步骤ID>-*.md`，按空行切段数到第 N 段，并用原文核对。
2. **按「提问对象」切换身份**：

   | 提问对象 | 身份 | 要求 |
   |---|---|---|
   | 教练（跳出角色） | 编排器以辩论教练口吻 | 讲清「为什么」，给可直接替换的说法 |
   | 原发言辩手（保持人设） | 该段发言者的 persona | 按 `debaters/PERSONA_PROTOCOL.md` 加载人设，第一人称回答 |
   | 对方辩手（保持人设） | 与发言者对立一方、最相关辩位的 persona | 真实辩场用语现场回应 |
   | 评委 | 中立评委 | 引用轮次与方法论术语（knowledge/05） |

3. **按「意图」作答**：

   | 意图 | 产出 |
   |---|---|
   | 解释 | 这段想钉住什么、在全场攻防中的作用、对方可能怎么接 |
   | 反驳 | 一段可直接上场的反驳（遵守 rules/script_format.md，无动作括号） |
   | 补强 | 漏洞诊断 + 可直接替换的段落 + 为什么有效 |
   | 核验事实 | 检索 → 给出来源 URL → **更新 evidence.md**（✅/⚠️）→ 必要时建议改写 |
   | 改写 | 给出改写稿；**用户确认后**再覆盖原文件对应段落，并在答案里注明改了哪里 |
   | 自定义 | 按问题回答 |

4. **回写**（让答案出现在协同台的原文旁边）：
   ```bash
   python3 tools/debate_ctl.py ask new <session> --ref-text - --answer-file answer.md --by "教练" <<'EOF'
   <粘贴内容原样>
   EOF
   ```
   答案用 Markdown 写在 `answer.md`（可含 `debate://…#bN` 链接，网页里可点击跳转）。
   若改动了文件，追加 `--changed transcript/R02-….md`。
5. 在对话里正常给出回答（回写只是同步到网页，不代替回答）。

---

## 4. 待答队列（`/ask`）

用户在协同台点「加入待答队列」，问题以 `status=pending` 写入 `qa/threads.jsonl`。用户在对话中输入 `/ask` 时：

```bash
python3 tools/debate_ctl.py ask list <session>          # 列出待答问题（含定位到的文件与行号）
# 逐条按 §3.1 的第 2–3 步回答，然后：
python3 tools/debate_ctl.py ask answer <session> --id <QID> --answer-file answer.md --by "教练"
```

一次 `/ask` 处理全部待答问题；每条在对话里给出简短答复，完整答案以回写为准。

---

## 5. 问答记录格式（qa/threads.jsonl）

追加写入、按 `id` 合并（同一 id 的后一条覆盖前一条的同名字段）：

```json
{"id":"Q1015-211400-a1f3","created":"…","refs":[{"uri":"debate://<sid>/R02#b10","key":"R02","anchor":"b10","quote":"…","where":"…"}],
 "intent":"补强","target":"教练（跳出角色）","question":"…","status":"pending","source":"web"}
{"id":"Q1015-211400-a1f3","answer":"Markdown 答案","answered_by":"教练","answered":"…","status":"answered","changes":["transcript/R02-….md"]}
```

---

## 6. 导出（`/export`）

```bash
python3 tools/debate_ctl.py export <session> --doc all --format docx      # 整场实录（按赛程汇编）
python3 tools/debate_ctl.py export <session> --doc R02 --format docx      # 单个环节
python3 tools/debate_ctl.py export <session> --doc artifacts/正方-一辩稿 --format docx
python3 tools/debate_ctl.py export <session> --format zip                 # 全部稿件 + 逐轮实录 + 台账
#   --raw 不清理契约行/编排器提炼块   --qa 附协同问答附录   --no-disclaimer 不附 AI 模拟声明
```

Word 文件为纯标准库生成的 OOXML：宋体小四正文、黑体标题、楷体引用、A4、页脚页码，
Word / WPS / LibreOffice 均可直接打开打印。

---

## 7. 安全与隐私

- 协同台只读会话目录，唯一的写操作是向 `qa/threads.jsonl` 追加提问；路径越界请求一律拒绝。
- 默认监听 `0.0.0.0:8765` 便于局域网 / 预览环境访问；只想本机访问时加 `--host 127.0.0.1`。
- 证据台账与问答里不要写入任何 token / 密钥 / 个人隐私。
