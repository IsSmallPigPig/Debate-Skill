---
name: Debate-Skills
version: 3.0.0
description: |
  运行结构化的多角色华语辩论赛（4v4 华语赛制，14 轮主战 + 赛前准备 + 赛后清理），支持自动选角、
  隔离/内联两种执行模式、完整赛/标准赛/速通赛三种规模预设、断点续跑、机器校验完成契约、
  证据台账，以及「辩论协同台」网页（实时展示 · 导出 Word · 复制原文位置向 Agent 提问）。触发词：
    `/debate`            → 进入完整辩论流程（可带 preset= / output= / mode= 参数）
    `/debate resume`     → 从 session.json 断点续跑
    `/debate status`     → 打印进度看板
    `/review`            → 进入复盘流程（见 review.md）
    `/ask`               → 处理协同台「待答队列」中的问题
    `/export`            → 导出整场实录 / 稿件为 Word（.docx）/ Markdown / ZIP
    粘贴的【辩论协同·提问】块 / debate:// 链接 → 定位原文后回答（collab/PROTOCOL.md §3）
  本文件是入口/分诊文件，只描述「做什么、读哪里、按什么顺序」；具体规则、提示模板、轮次脚本、
  输出模板分别放在 rules/、prompts/、templates/ 下，按需加载。
---

# Debate Skill v3 · 入口文件

> 设计原则：**主文件只做调度，不做执行**。所有可复用的内容（规则、Prompt 模板、轮次脚本、
> 输出格式、复盘流程）都拆到子文件，按需 `read_file` 加载，避免一次性灌满上下文。
>
> **v3 的三条新原则**：
> 1. **数字只有一个出处**——所有时长、字数下限、校验项以 `rules/presets.json` 为准；
> 2. **契约由机器校验**——字数、括号、回合数等由 `tools/debate_ctl.py lint` 实测，不信模型自报；
> 3. **过程落盘可续跑**——每个环节写入 `debate-output/<session>/transcript/`，断线可从 `session.json` 继续。

---

## 0. 快速索引（先看这里）

| 你想做的事 | 该读哪个文件 |
|---|---|
| 了解整体流程和心智模型 | 本文件 §1–§6 |
| **查任何环节的时长 / 字数下限 / 校验项（单一事实来源）** | **`rules/presets.json`** ★v3 |
| 看具体的辩论规则（质询/自证/自由辩…） | `rules/rules_guide.md` |
| 看完整的 14 个轮次怎么排 | `rules/round_structure.md` |
| 看每一轮该用什么 Prompt 调辩手 | `prompts/round_prompts.md` |
| **看协同输出协议（落盘 / 校验 / 续跑 / 提问回写）** | **`collab/PROTOCOL.md`** ★v3 |
| **启动协同台网页、导出 Word** | **`collab/README.md`** ★v3 |
| 看全场进度看板 | `python3 tools/debate_ctl.py status`（或 `prompts/round_prompts.md §8`） |
| 看辩稿写作格式 | `rules/script_format.md` |
| 查辩论方法论与战术 | `knowledge/` 目录 |
| 看历史实录检索方法（debatetimer MCP） | `knowledge/06-历史实录检索.md` |
| **看证据台账与防编造规则** | **`templates/evidence_ledger.md`** ★v3 |
| 看最终辩论记录怎么排版 | `templates/transcript_template.md` |
| 看赛前/赛后要生成哪些稿件文件 | `templates/artifacts_spec.md` |
| 看本流程依赖的 3 个外部 Skill 怎么用 | `Skills/integration.md` |
| 进入复盘 | `review.md` |
| 查可用辩手清单 | `debaters/debaters.md` |
| **查辩手人设怎么加载、研究档案怎么用、人设护栏** | **`debaters/PERSONA_PROTOCOL.md`** ★v3 |
| 查某位辩手的人设 DNA | `debaters/<name>-perspective/SKILL.md` |

---

## 1. 这个 Skill 解决什么

让模型扮演一个**辩论赛编排器（Orchestrator）**，按华语辩论赛制（4v4，14 轮）组织一场围绕
具体辩题、有明确正反方、有质询/自证/自由辩/总结的完整对抗，并：

1. 自动从 `debaters/` 中挑选/分配 8 位辩手到正反双方；
2. 按轮次脚本驱动每位辩手按其 Skill 人设发言；
3. 落盘必要的赛前/中场/赛后文档（一辩稿、攻防表、前场整理、最终稿…）；
4. 最后由中立主持人输出 Synthesis；
5. **★v3**：全过程写入会话目录，用户可在「辩论协同台」网页里实时观看、导出 Word、
   把任意一段的**原文位置**连同问题一起复制给 Agent 追问。

---

## 2. 依赖安装（首次运行前执行一次）

> 仅当当前环境**未安装**对应依赖时才执行；已安装则跳过。三个外部 Skill 的**用途**和**调用时机**
> 详见 `Skills/integration.md`。

| 依赖 | 用途速记 | 安装方式 | 级别 |
|---|---|---|:---:|
| `multi-search-engine` | 16 引擎元搜索，备赛 / 临场核验 | 见 §2.1 | **必需** |
| `debate-master` | 辩论方法论百科（6 维度、谬误表、攻防口诀） | 本仓库 `Skills/debate-master-1.0.0/` | 推荐 |
| `self-improvement` | 跨会话经验沉淀到 `.learnings/` | 见 `Skills/integration.md` §3.3 | 推荐 |
| debatetimer.cn MCP ★v3 | 华语辩论历史实录检索（§3B.0） | 见 §2.1 | 推荐 |
| Python 3.8+ ★v3 | 运行 `tools/`（校验、续跑、定位、导出）与协同台 | 系统自带即可，**零第三方依赖** | 推荐 |

### 2.1 安装方法

```bash
# ① multi-search-engine（必需）——任选其一
cp -r Skills/gpyangyoujun-multi-search-engine-2.1.3 <你的 Agent skills 目录>/multi-search-engine   # 用本仓库副本
cocoloop install gpyangyoujun-multi-search-engine-2.1.3                                             # 或用 cocoloop 商店（以商店最新版为准）

# ② debate-master / self-improvement（推荐）——同理复制本仓库副本，或按 Skills/integration.md §3.3

# ③ debatetimer.cn 官方 MCP（推荐，公测免登录，全站共享 5000 次/天，批量算 1 次）
npx add-mcp https://debatetimer.cn/api/mcp
#    装不了 MCP 但能跑 shell → 用同一接口的命令行兜底：
python3 tools/debatetimer.py search "大城市"
```

### 2.2 编排器自检（开赛前必跑）

```text
[ ] Skill(multi-search-engine)  可用？  否 → 走 web_search / web_fetch fallback
[ ] Skill(debate-master)        可用？  否 → 用编排器自身的辩论知识降级
[ ] Skill(self-improvement)     可用？  否 → 跳过经验沉淀
[ ] debatetimer MCP             可用？  否 → python3 tools/debatetimer.py → 再不行走 site:debatetimer.cn 搜索
[ ] 能执行 python3？                    否 → 协同台与机器校验不可用：output 自动降级为 chat，契约按 §7.5 自检
[ ] 能写文件？                          否 → output=chat，稿件全部在对话中给出
```

---

## 3. 输入解析（开赛前必须确认）

从用户的 `/debate ...` 调用中解析：

| 字段 | 说明 | 必填 | 缺省策略 |
|---|---|---|---|
| `topic` | 辩题 | ✅ | 若上下文已隐含主题，直接沿用 |
| `support` | 用户站哪边（正方 / 反方） | ✅ | 用于决定最终要为哪一方出具完整稿件 |
| `personas` | 8 个辩手（正反各 4） | — | 未指定 → 走 §4 自动选角 |
| `preset` ★v3 | 规模预设：`full` / `standard` / `quick` | — | 默认 `full`；用户说「快一点 / 简单打一场」→ `quick`。见 §3.1 |
| `output` ★v3 | 呈现方式：`web` / `chat` / `both` | — | 能写文件且能跑 python → `web`；否则 `chat`。见 §7.3 |
| `mode` | `isolated` / `inline` | — | 默认 `isolated`；用户说 "inline / fast / single-context" → 切换 |
| `synthesis` | 是否要主持人总结 | — | 默认开启；用户说 "no synthesis" → 关闭 |
| `rounds` | （v2 遗留，已废弃） | — | 等价于 `preset`；`rounds=14` → `full` |

**强约束**：在不确认 `topic` 和 `support` 之前，**绝对不要**开始任何轮次。

### 3.1 规模预设（数字以 `rules/presets.json` 为准）

| 预设 | 内容 | 步数 | 字数下限合计 |
|---|---|:---:|---:|
| `full` 完整赛 | 双方赛前 6 步（B0–B5）+ 14 轮 + 评委 + 赛后 6 步（H1–H6）+ Synthesis | 39 | 34,360 |
| `standard` 标准赛 | 双方赛前 B0/B1/B5 + 14 轮 + 评委 + H1/H5 + Synthesis | 26 | 23,100 |
| `quick` 速通赛 | 双方 B1 + R1–R4 / R12 / R13–R14 + 评委 + Synthesis | 12 | 11,500 |

> 可随时运行 `python3 tools/debate_ctl.py budget` 查看逐步明细。

### 3.2 会话初始化（output=web / both 时）

```bash
python3 tools/debate_ctl.py init --topic "<topic>" --pro "<正方立场>" --con "<反方立场>" \
        --side <support> --preset <preset> --mode <mode> --output <output> \
        --lineup "正方=一辩,二辩,三辩,四辩;反方=一辩,二辩,三辩,四辩"
```

生成 `debate-output/<session_id>/`（目录结构见 `collab/PROTOCOL.md §1`），并提示用户可启动协同台：
`python3 collab/server.py --root debate-output`。

---

## 4. 自动选角协议

优先级：

1. 用户明确点名的角色 → **绝不覆盖**
2. 从 `debaters/debaters.md` + `debaters/*-perspective/SKILL.md` 中实际存在的角色里挑
3. 找不到至少 4 个可用角色 → 只询问用户一次，然后停下，**不要凭空捏造**

### 4.1 推荐基线阵容（v3 修订：八人各出场一次，无人跨方）

| 辩位 | 正方 | 反方 |
|:---:|---|---|
| 一辩 | 胡渐彪（攻防/定义） | 庞颖（框架/系统） |
| 二辩 | 颜如晶（故事/共情） | 周玄毅（概念/归谬） |
| 三辩 | 黄执中（价值/质询） | 詹青云（深度解构） |
| 四辩 | 马薇薇（收尾/金句） | 陈铭（升华/温暖） |

> v2.5 的基线表让庞颖同时出现在正方二辩与反方一辩，违反 §4.2「同一辩手不得同时出现在正反两方」，
> v3 已修正。每一格都取自原表的候选或该辩手卡的推荐辩位。

### 4.2 选角启发式

- 优先选**视角差异最大**的组合，而不是风格相近的；
- 同一辩手不得同时出现在正反两方；
- 8 个位置必须由 8 位**不同**辩手填满；如果可用辩手不足 8 人，允许一位辩手在**同一方**的两个辩位
  上出现，但需要在开场说明并标注 `(兼)`；
- 如果置信度低，开赛前一句话报备假设，**不要中途追问**。

### 4.3 人设加载与护栏（★v3）

按 `debaters/PERSONA_PROTOCOL.md` 加载：先读辩手 `SKILL.md`，再按环节**渐进加载**其
`references/research/` 档案（表达 DNA → 立论/质询用思维框架 → 结辩用金句）。
护栏：只使用辩手的**公开辩论风格与公开言论**；不得引入私生活信息；不得把模拟发言当作真人原话；
导出文件默认附「AI 模拟」声明。

---

## 5. 执行模式（Mode）

| 模式 | 一句话 | 适用 |
|---|---|---|
| `isolated`（默认） | 每个辩手用一个**持久子代理**，编排器只装配记录、不代写发言 | 担心编排器把所有辩手写成一个味；希望硬碰硬 |
| `inline` | 编排器在主上下文里**依次**调用每个 Skill，自己代写发言 | 速度优先；希望中途人工纠偏 |

两种模式的详细执行步骤见 **`prompts/round_prompts.md` §1（隔离） / §2（内联）**。

- **★v3 互动环节接力**：isolated 模式下，质询 / 自证 / 自由辩按 `prompts/round_prompts.md §1.5`
  **逐回合在两个（或多个）子代理之间接力**，不得由提问方子代理代写答方回答。
- **★v3 诚实声明**：inline 模式下正反双方的「互不可见」只能是**软隔离**（同一上下文必然看得到）。
  编排器须遵守：一方只能回应对方**已在公开轮次说过**的内容（lint 的「引用核对」会提示疑似越界）。

---

## 6. 顶层执行流（Orchestrator 主循环）

> ⚠️ **关键纪律**：
> 1. 编排器**必须**逐阶段、逐轮次执行 `prompts/round_prompts.md` 中**当前预设包含的每一个**编号 prompt；
> 2. **不准**把多个轮次「打包成一段」输出；
> 3. **不准**因为「觉得够了」就提前进入下一阶段；
> 4. 每轮必须**通过机器校验**（`debate_ctl.py step <session> <步骤> --status done` 返回通过）
>    才能进入下一轮；无法运行 python 时，退回读到 `【完成】` 契约并逐项自检（§7.5）；
> 5. 阶段 B 与阶段 H 的子步骤都是**独立 prompt**，要分别发送；
> 6. 进度看板**每轮更新一次**并在对话中可见（`debate_ctl.py status` 生成，或手工按 §8 模板）；
> 7. 每个环节都要**完整演出**——`output=chat` 时演在对话里，`output=web` 时演在 transcript 文件里（§7.3），
>    严禁只说「已生成 XX.md」而没有任何地方存在完整发言；
> 8. 所有辩稿/发言**严禁**带（动作/表情/语气）等小说式标记，必须按 `rules/script_format.md`
>    的真实华语辩稿格式来写，所有产物必须可**直接复制到 Word 打印**（§7.4）；
> 9. 辩手 / 编排器 / 评委在思考「这一招该怎么打」时，**必须**主动查阅 `knowledge/` 对应文件（§7.7）；
> 10. **★v3** 任何 URL 都必须来自本会话真实的工具返回结果并登记到证据台账，否则标注【待核实】（§7.8）。

### 6.0 每一步的固定收尾（★v3，output=web / both）

```text
① python3 tools/debate_ctl.py next <session>            # 查看下一步：prompt 小节、参与者、下限、输出文件
② python3 tools/debate_ctl.py step <session> <ID> --status in_progress
③ 按 prompt 演出该环节 → 完整写入 transcript/<presets.json 中的 file>
④ python3 tools/debate_ctl.py step <session> <ID> --status done   # 自动 lint；不通过 → 按 §9 重做
⑤ 在对话里贴出：环节标题 + 【校验】行 + 1–3 句战况转播（output=both 时贴全文）
⑥ 每完成一个阶段，贴一次 python3 tools/debate_ctl.py status 的进度看板
```

> 上下文接近上限、会话中断或换了新对话：执行 `/debate resume` —— 读 `session.json` 与已写入的
> transcript，**从文件而不是从记忆**恢复战况，再从 `next` 指出的步骤继续（`collab/PROTOCOL.md §2`）。

> 每个阶段右侧的「外部 Skill」栏标出**该阶段要主动调用**的第三方 Skill；
> 详细调用模板、Prompt、回写约定见 `Skills/integration.md` 对应小节。

```text
[阶段 A] 确认输入
  ├─ 读 §3，确认 topic / support / preset / output / mode
  ├─ 读 §4 + debaters/debaters.md，落定 8 位辩手名单 → debate_ctl.py init（output=web/both）
  └─ 外部 Skill: self-improvement     → 读 .learnings 历史先验（Skills/integration.md §3.4）

[阶段 B] 赛前准备（full 预设 6 个子步骤，分别执行，不准合并；standard/quick 见 §3.1）
  ├─ §3B.0 历史实录检索  ── prompt: prompts/round_prompts.md §3B.0
  │                        debatetimer MCP 检索同题/近题实录 → 敌情通报（knowledge/06）
  ├─ §3B.1 论点架构      ── prompt: prompts/round_prompts.md §3B.1
  ├─ §3B.2 资料收集      ── prompt: prompts/round_prompts.md §3B.2   → 同步写证据台账 evidence.md
  ├─ §3B.3 攻防表        ── prompt: prompts/round_prompts.md §3B.3
  ├─ §3B.4 内部头脑风暴  ── prompt: prompts/round_prompts.md §3B.4
  ├─ §3B.5 一辩稿撰写    ── prompt: prompts/round_prompts.md §3B.5
  ├─ 落盘  artifacts/正方-历史实录敌情通报.md / 反方-历史实录敌情通报.md
  │       artifacts/正方-备赛资料.md / 反方-备赛资料.md
  │       artifacts/正方-一辩稿.md / 反方-一辩稿.md
  │   ⚠ 正反双方互不可见，分别走完各自的子步骤
  └─ 外部 Skill:
      ├─ debatetimer MCP     → §3B.0 首选（兜底：tools/debatetimer.py → site:debatetimer.cn 搜索）
      ├─ debate-master       → §3B.1/§3B.3 必调（Skills/integration.md §1）
      └─ multi-search-engine → §3B.2/§3B.3 必调（Skills/integration.md §2）

[阶段 C] 前场（第 1–4 轮）
  ├─ 读 rules/round_structure.md + rules/rules_guide.md
  ├─ R1 正一申论 → R2 反四质询正一 → R3 反一申论 → R4 正四质询反一
  ├─ Prompt 模板见 prompts/round_prompts.md §4.1–§4.4
  └─ 外部 Skill: multi-search-engine 按需，质询方需要核验对方数据时调用（Skills/integration.md §2.3）

[阶段 D] 战术暂停（第 5 轮）
  ├─ 双方分别复盘前 4 轮，承认对方至少 1 个对的点 ── prompt: §4.5
  ├─ 落盘  artifacts/正方-前场整理.md / 反方-前场整理.md
  └─ 外部 Skill:
      ├─ debate-master       → 用谬误表标注对方论证漏洞
      └─ multi-search-engine → 补充对方刚抛但未引证的数据

[阶段 E] 后场（第 6–11 轮）
  ├─ R6 正二申论 → R7 反三质询正二 → R8 反二申论 → R9 正三质询反二
  ├─ R10 反三自证 → R11 正三自证
  └─ Prompt 模板见 prompts/round_prompts.md §4.6–§4.11

[阶段 F] 自由辩论（第 12 轮）── prompt: §4.12
  └─ 正方先开口，单人单次发言，正反交替；双方各 4'00"，24–40 次发言

[阶段 G] 总结陈词（第 13–14 轮）── prompt: §4.13–§4.14
  ├─ R13 反四总结
  └─ R14 正四总结

[阶段 H] 评委点评 + 赛后清理（full 预设：评委 + 6 个子步骤，分别执行，不准合并）
  ├─ 评委点评           ── prompt: prompts/round_prompts.md §5
  ├─ §6.1 全队头脑风暴  ── prompt: prompts/round_prompts.md §6.1
  ├─ §6.2 一辩稿终稿    ── prompt: prompts/round_prompts.md §6.2  → <user_side>-一辩稿-终稿.md
  ├─ §6.3 ×3            ── 二辩稿 / 三辩自证稿 / 四辩结辩稿（分别执行 3 次）
  ├─ §6.4 ×2            ── 三质二质询稿 / 四质一质询稿（分别执行 2 次）
  ├─ §6.5 攻防表终稿    ── prompt: prompts/round_prompts.md §6.5
  ├─ §6.6 落盘自检      ── prompt: prompts/round_prompts.md §6.6（含 debate_ctl.py lint 全场）
  ├─ 用户质询（可选）   ── 也可在协同台里逐段「复制位置并提问」（§11）
  └─ 外部 Skill:
      ├─ debate-master       → §5 评委必调
      ├─ multi-search-engine → §6.2/§6.3 补证据
      └─ self-improvement    → §6.6 后必调，写 LEARNINGS.md (best_practice)

[阶段 I] Synthesis（若开启）
  ├─ 由编排器以中立主持人身份输出，规则见 §8
  ├─ 导出：python3 tools/debate_ctl.py export <session> --doc all --format docx
  └─ 外部 Skill: self-improvement     → 写 LEARNINGS.md (insight)
```

最终辩论记录的渲染格式见 **`templates/transcript_template.md`**。
每个阶段的外部 Skill 详细调用方式见 **`Skills/integration.md` §5 阶段路由表**。

---

## 7. 时长约束与完成契约

> 1. **以「真实演讲时长」为基准约束**，字数是时长的换算结果，基准语速 **280 字/分钟**；
> 2. **★v3 单一事实来源**：每个环节的时长、字数下限、校验项**只在 `rules/presets.json` 定义**，
>    本节与 `rules/*.md`、`prompts/*.md` 中的数字都是它的镜像；冲突时以 presets.json 为准；
> 3. 字数统计口径：中文字符与全角标点各计 1，连续英文/数字计 1，URL、Markdown 符号、发言人标签、
>    标题、契约行、【编排器·提炼】块不计入。

### 7.1 时间↔字数换算表

| 时长 | 等价字数下限 | 典型用途 |
|---|---|---|
| 20" | ≤ 95 字（上限） | 单次打岔 |
| 30" | ≥ 140 字 | 单次自证段 |
| 1'30" | ≥ 420 字 | 三辩质询全场 |
| 2'30" | ≥ 700 字 | 二辩申论 / 首质 |
| 3'00" | ≥ 840 字 | 自证方 3 分钟（下限取 800） |
| 3'30" | ≥ 980 字 | 一辩申论 / 总结陈词 / 评委点评 |
| 双方各 4'00" | ≥ 2240 字 | 自由辩论（单次 30–210 字，24–40 次） |

### 7.2 每轮的时长 + 字数下限（full 预设速览）

| 阶段 | 子步骤 | 时长 | 字数下限 |
|---|---|:---:|---:|
| B | §3B.0 历史实录检索 | 约 8 分钟 | ≥ 1000 字 × 双方 |
| B | §3B.1 论点架构 / §3B.2 资料收集 / §3B.3 攻防演练 / §3B.4 二次修改 | 约 18 分钟 | 1200 / 1000 / 1500 / 800 × 双方 |
| B | §3B.5 一辩稿彩排 | 3'30" | ≥ 980 字 × 双方 |
| C | R1/R3 一辩申论 | 3'30" 各 | ≥ 980 字 各 |
| C | R2/R4 首质（单边计时） | 2'30" 各 | ≥ 700 字 各（质询方 ≥ 420，≥ 5 回合） |
| D | R5 战术暂停 | 约 3 分钟 × 双方 | ≥ 800 字/方 |
| E | R6/R8 二辩申论 | 2'30" 各 | ≥ 700 字 各 |
| E | R7/R9 三辩质询（单边计时） | 1'30" 各 | ≥ 420 字 各（质询方 ≥ 280，≥ 4 回合） |
| E | R10/R11 自证（双边计时） | 约 3'00" 各 | ≥ 800 字 各（≥ 6 段 × 140；打岔 ≤ 3 次 × 95 字） |
| F | R12 自由辩（双边计时） | 双方各 4'00" | ≥ 2240 字，24–40 次 |
| G | R13/R14 总结陈词 | 3'30" 各 | ≥ 980 字 各 |
| H | 评委点评 | 3'30" | ≥ 980 字 |
| H | 赛后 H1–H5（对话彩排 + 整理） | 约 25 分钟 | 1400 + 980 + (700+800+980) + 600×2 + 800 = 6860 字 |
| I | Synthesis | 约 2'00" | ≥ 560 字 |

**完整一场（full）的字数下限合计：34,360 字**
（赛前 12,960 + 主战 13,000 + 评委与赛后 7,840 + Synthesis 560）

> v2.x 写的「≥ 18000 字」漏算了阶段 B 双方各跑一遍，且自由辩的要求（≥24 次 × ≥140 字 ≈ 12 分钟）
> 与「4 分钟」自相矛盾。v3 统一为「双方各 4'00"」（与国际大专辩论赛等主流华语赛制一致）。
> 一场 full 约 3.4 万字，远超单轮回复上限——这正是 §6.0 逐步落盘 + 断点续跑的意义。

### 7.3 呈现方式（★v3：output = web / chat / both）

**所有辩论环节都必须完整演出**，区别只在「舞台」在哪里：

| output | 完整发言写在哪里 | 对话里显示什么 | 适用 |
|---|---|---|---|
| `web`（有文件+python 时默认） | `transcript/<步骤文件>.md`（协同台实时展示） | 环节标题 + 【校验】行 + 1–3 句转播 + 阶段看板 | 长赛、要导出 Word、要逐段追问 |
| `chat` | 对话 | 完整发言（v2.x 行为） | 无文件/无 shell 环境 |
| `both` | 两处都有 | 完整发言 | 想在对话里通读，同时保留文件 |

共同规范（具体见 `prompts/round_prompts.md §0.5`）：
1. **每次发言**用标题行格式：`## 第 N 轮 · {环节}｜{辩位} · {辩手}` + 时长副标题；
2. **真实辩场用语**（对方辩友、各位评委、主席、谢谢主席）；
3. **正文是完整发言**，不是摘要；
4. **质询/自由辩**用「辩位名加粗 + 冒号 + Q-A 交替」格式（`**反方四辩 · 陈铭**：……`）——协同台据此识别发言人；
5. **赛前讨论 + 赛后复盘**也要演四人对话；
6. **稿件文件**（artifacts/）是从演出内容**提炼**的派生物。

### 7.4 真实辩稿格式（参考 debatetimer.cn）

所有辩稿和现场发言必须按 `rules/script_format.md` 的规范来写：

**严禁出现**：
- ❌ （沉稳起立）、（拍桌）、（深呼吸）等**动作括号**
- ❌ （眉头紧锁）、（语速加快）等**表情/语气括号**
- ❌ "马薇薇站起，犀利地扫视全场"等**小说式旁白**
- ❌ "现场气氛紧张"等**环境描写**
- ❌ "作为正方一辩，我现在开始我的申论"等**元说明**
- ❌ 任何 `{占位符}` 未替换

**必须使用**：
- ✅ 真实辩场套语：开宗明义、综上所述、谢谢主席、对方辩友、第一/第二/第三、首先/其次/最后
- ✅ 一辩稿 8 节结构：问候 / 立场 / 定义 / 判准 / 论点一 / 论点二 / 论点三 / 综上所述
- ✅ 二辩稿 4 节结构：问候 / 回应对方 / 推进论点 / 收束
- ✅ 四辩稿 5–7 节结构：问候 / 战场梳理 / 关键瞬间 / 价值升华 / (正四) 回应反四 / (正四) 判决建议 / 金句
- ✅ 质询稿「问答脚本」格式：质询目标 / 主线问答（含预期答案+我方走法） / 风险预案 / 小结模板

**最终产物要求**：所有落盘 .md 文件可**直接复制到 Word 打印**；协同台/`export` 导出 .docx 时
会自动清理契约行与【编排器·提炼】块。

### 7.5 完成契约（v2.1 引入，★v3 改为机器校验）

每一轮仍在末尾输出 `【完成】` 自报契约行（便于人读），但**放行依据是机器实测的【校验】行**：

```text
【完成】轮次=R1 时长=3'30" 字数=985 含3论点=是 含定义判准=是 含证据URL=3 无动作括号=是     ← 模型自报
【校验】R01 实测字数=1015/980 ✓ 动作括号=0✓ 占位符=0✓ URL=3/3✓  →  通过                     ← debate_ctl.py 实测
```

- 自报与实测不符 → 以实测为准（lint 会给出「自报 vs 实测」提示）；
- 【校验】不通过 → 不准进入下一轮，按 `prompts/round_prompts.md §9` 重做；
- 无法运行 python 时：编排器逐项人工自检【完成】字段，并在看板中注明「未机器校验」。

### 7.6 重做触发条件

详见 `prompts/round_prompts.md §9`。v3 起由 lint 自动检出的硬性问题（error）：
字数不足、回合/段数/发言次数不足、质询方字数不足、打岔超限、自由辩同方连续发言、
动作/表情括号、小说式旁白、元说明、未替换占位符、四人发言不齐。

### 7.7 知识库调用清单

| 阶段 | 必读文件 | 用途 |
|---|---|---|
| 阶段 A 选阵容 | `knowledge/00-philosophy.md` | 判断该辩题适合加法派还是减法派 |
| 阶段 B §3B.0 历史实录检索 | `knowledge/06-历史实录检索.md` | debatetimer MCP 检索 + 敌情通报整理 |
| 阶段 B 立论 §3B.1–§3B.5 | `knowledge/01-立论与战场.md` | 定义、判准、战场切割、攻防表设计 |
| 阶段 B 攻防表 | `knowledge/05-逻辑谬误手册.md` | 给每个攻防点贴方法论标签 |
| R2/R4/R7/R9 质询 | `knowledge/02-质询与攻防.md` | 起追结转、确认/处理/展示三段法 |
| R10/R11 自证 | `knowledge/02 + 03` | 自证方推进 + 打岔方狠技巧 |
| R12 自由辩 | `knowledge/03-自由辩与配合.md` | 团队配合、节奏控场、五大战术 |
| R13/R14 结辩 | `knowledge/04-结辩与升华.md` | 战场梳理、价值升华、金句设计 |
| 评委点评 | `knowledge/05-逻辑谬误手册.md` | 用专业术语解释胜负 |
| Synthesis | `knowledge/00-philosophy.md` | 辩论的「道」层升华 |

### 7.8 证据纪律（★v3，防编造）

1. **URL 只能来自本会话真实的工具返回**（搜索 / 抓取 / debatetimer MCP），并登记到会话目录的
   `evidence.md`（格式见 `templates/evidence_ledger.md`）；
2. 模型记忆中的数据、无法检索到出处的说法 → 台账记为「⚠️待核实」、**不写 URL**，发言中标注【待核实】；
3. debatetimer 整场总结由 AI 根据录音整理，**可能含识别错误与缺段**，引用其中数据前必须二次核验；
4. 「URL 覆盖率」只统计台账中「✅已核验」的条目；宁可少一条证据，不可编一个链接。

---

## 8. Synthesis（主持人总结）规则

如果开启，结尾追加一节，由编排器自身的声音（不是任何辩手）输出：

- ✅ 点出**核心分歧**，不要打「大家都有道理」的和稀泥；
- ✅ 点出多轮交锋中**真实出现**的共识；
- ✅ 识别**哪个辩手更新了看法**、更新了什么；
- ✅ 可以给**条件性建议**（「如果你在 X 情境，更应倾向 Y」），但**不宣布赢家**；
- ❌ 不要捏造辩手没说过的立场；
- ✅ 可以把已有论点重构为更结构化的拆解 / 启发式 / 决策框架。

---

## 9. 失败模式速查（在每轮开始前默念）

| 症状 | 处理 |
|---|---|
| **并行独白** —— 第 2 轮后辩手互不点名 | 重发该轮 Prompt，写明「你必须回应 X 关于 Y 的主张」 |
| **虚假共识** —— 辩手过快趋同 | 信任 Skill 文件；不要软化原本对立的观点 |
| **主题漂移** —— 跑题 | 每轮 Prompt 必须重申 `topic` 原文 |
| **角色泄漏** —— 听起来像普通 GPT 回答 | 重新 fresh 调用该辩手 Skill；不要凭记忆续写人设 |
| **稿件失落** —— 阶段 H 没落盘 | 按 `templates/artifacts_spec.md` 强制清单复核；`debate_ctl.py status` 查缺 |
| **外部 Skill 调用失败** | 按 `Skills/integration.md` §2.5 / §6 降级，并写一条 `ERRORS.md` |
| **★ 字数自报失真** —— 自称 985 字实际 800 | 以 `debate_ctl.py lint` 实测为准，不足即重做 |
| **★ 编造 URL / 数据** | 只用台账中已核验的来源；无出处 → 【待核实】（§7.8） |
| **★ 稻草人** —— 引号里的「对方原话」对方从没说过 | lint「引用核对」提示后，改为真实原话或改成概括性表述 |
| **★ 会话中断 / 上下文爆满** | `/debate resume`：从 session.json + transcript 文件恢复，而不是凭记忆续写 |

---

## 10. 退出角色

最终 Synthesis 输出后，所有辩手默认**退出角色态**。用户继续追问，按常规模型身份回答；
除非用户再次以 `詹青云视角` 等触发词召唤某个 Skill，或通过【辩论协同·提问】指定「原辩手 / 对方辩手」身份作答。
所有发言均为基于公开资料的**风格模拟**，不代表真实人物观点。

---

## 11. 路由：用户输入到此 Skill 怎么走？

```text
用户输入
  ├─ 包含 "/debate resume"     → collab/PROTOCOL.md §2（读 session.json，从 next 步骤继续）
  ├─ 包含 "/debate status"     → python3 tools/debate_ctl.py status（无 shell 时按 round_prompts §8 手工看板）
  ├─ 包含 "/debate"            → 本文件，按 §3 → §6 流程
  ├─ 包含 "/review"            → review.md
  ├─ 包含 "/ask"               → collab/PROTOCOL.md §4（处理协同台待答队列）
  ├─ 包含 "/export"            → python3 tools/debate_ctl.py export（默认整场实录 .docx）
  ├─ 含【辩论协同·提问】或 debate:// 链接 → collab/PROTOCOL.md §3（定位原文 → 按对象/意图作答 → 回写）
  ├─ 包含某辩手触发词          → debaters/<name>-perspective/SKILL.md（单独人设回答）
  └─ 其它                      → 不属于本 Skill 处理范围
```

---

## 12. 辩论协同台（★v3 脚手架）

```bash
python3 collab/server.py --root debate-output          # 打开 http://localhost:8765
python3 collab/server.py --root collab/demo            # 先看示例会话
```

- **实时展示**：Agent 每写入/改写一个 transcript，网页 1.5 秒内刷新；可开「跟随直播」；
- **机器校验可视化**：每个环节显示实测字数、回合数、违规段落定位；
- **导出**：当前文档 / 整场实录 / 全部稿件 → Word（.docx，中文排版）、Markdown、HTML、打印 PDF、ZIP；
- **复制位置并提问**：悬停任意段落或选中一句话 → 复制【辩论协同·提问】（含 `debate://` 锚点 + 原文）→
  粘贴给 Agent；也可「加入待答队列」，在对话里输入 `/ask` 批量处理；答案回写后显示在原文旁。

详见 `collab/README.md`。
