# CHANGELOG

## v2.0.0 — 重构（基于 v1.x 全量重写）

> 目标：保持 100% 功能等价的前提下，提升**可读性 / 结构清晰度**。
> 风格沿用原作的中英混排（术语英文，叙述中文）。

### 🆕 新增

- `prompts/round_prompts.md` —— 把"提示模板"从 SKILL.md 里**剥离**出来独立成册，
  并且每一轮（§3.1–§3.14）都有自己的 Prompt 模板，原本只有 R1/R2/R3 的模板被泛化到 14 轮。
- `templates/transcript_template.md` —— 把"输出格式"独立成模板文件，
  顺便修掉了原 SKILL.md 中**"第 10 轮 · 自由辩论"模板被重复贴出两次**的 bug。
- `templates/artifacts_spec.md` —— **新增**所有赛前/中场/赛后稿件的统一文件清单、
  命名规范、章节结构、编排器自检清单。原版只在散文里零散提及"一辩稿""攻防表"，
  没有任何统一规范。
- `CHANGELOG.md`、本文件。

### 🔁 重构

- `SKILL.md` 从 **355 行 / ~18 KB** → **~150 行 / ~6 KB**：
  - 删除**完全重复的两段"# 下载依赖"**（原文件 11–17 行连续出现两次同样的安装指令）；
  - 删除**与 prompts/ 内容重复**的"启动阶段 / 第 1/2/3 轮 Prompt 模板"长文（已迁移到 prompts/round_prompts.md）；
  - 把"输出格式"块迁移到 `templates/transcript_template.md`，并修复其中：
    - 重复出现的"## 第 10 轮 · 自由辩论"块；
    - "第 11 轮"标题下错贴成"第 10 轮"内容的 bug；
  - 新增 §0「快速索引」+ §6「顶层执行流」，让编排器知道"按什么顺序读哪个文件"。

- `review.md` 从 **11 行 / 1 KB** → **~80 行 / ~3 KB**：
  - 原文只有 6 行散文，重构成 6 个清晰阶段（信息加载 → 攻击规划 → 集中质询 → 反思 → 回写 → 小结）；
  - 新增**终止条件**、**最终交付清单**、**失败模式速查**。

- `rules/rules_guide.md`：
  - 原作各章顺序混乱，重排为 §1 计时 → §2 申论 → §3 质询 → §4 自证 → §5 自由辩 → §6 红线；
  - 每个环节用**表格**列规则，告别原文大段无序列表；
  - 修复原文 "不能只是重复第上一轮内容" 的笔误（应为"不能只是重复上一轮内容"）；
  - 新增 §6 全场通用红线清单。

- `rules/round_structure.md`：
  - 把 14 轮压缩成**一张主流程表**（§1），快速看清；
  - 把"赛前规划 / 战术暂停 / 评委点评 / 赛后清理"等阶段从散文里抽出，单独成节；
  - 明确指明每一轮指向 `prompts/round_prompts.md` 的对应小节。

- `debaters/debaters.md`：
  - 原 287 行去重为 ~80 行，保留所有事实信息（推荐辩位、风格、触发词、阵容）；
  - 移除"此文档由女娲造人术自动生成"等元噪声；
  - 新增 §5「单独召唤示例」展示三种典型用法。

### 🐛 修复

| # | 原 bug | 位置 | 修复 |
|---|---|---|---|
| 1 | 下载依赖块连续重复两次 | 原 `SKILL.md` 11–17 行 | v2 `SKILL.md §2` 只保留一次 |
| 2 | 输出格式里第 10 轮自由辩论被重复贴出 | 原 `SKILL.md` 输出格式块 | v2 `templates/transcript_template.md` 修复 |
| 3 | "第 11 轮 总结陈词" 标题底下错贴成"第 10 轮自由辩论"的内容 | 原 `SKILL.md` 输出格式块 | 同上 |
| 4 | 文档结构图里 hu-jianbiao / hu-jian-biao 拼写不一致 | 原 `SKILL.md` 文件结构块 | 统一为 `hu-jian-biao-perspective` |
| 5 | 一辩稿/二辩稿/质询稿等文件无命名规范，赛后清单"散落"在不同段落 | 原 `SKILL.md` + `round_structure.md` | v2 `templates/artifacts_spec.md` 统一定义 |
| 6 | 隔离模式 Prompt 模板只写到第 3 轮，14 轮里有 11 轮没有模板 | 原 `SKILL.md` | v2 `prompts/round_prompts.md` §3 补全到 14 轮 + 评委点评 + 赛后清理 |
| 7 | "rules_guide.md" 多处写成 "rules_guidlines.md" / 链接断裂 | 原 README/SKILL | v2 全文档统一为 `rules/rules_guide.md` |
| 8 | review.md 的 description 与 SKILL.md 一字不差（误复制） | 原 `review.md` 顶部 frontmatter | v2 改为复盘自己的描述 |

### ⚖️ 行为兼容性

- 触发词 `/debate` 与 `/review` **完全保留**；
- 角色卡（`debaters/*-perspective/SKILL.md`）**未做修改**，原汁原味；
- 14 轮顺序、时长、计时模式、自动选角原则、隔离/内联模式语义**全部保留**；
- 依赖（cocoloop / Multi Search Engine）安装链接保持不变。

### 📁 文件结构对比

```text
v1.x（旧）                                v2.0.0（新）
─────────────────────────                ───────────────────────────────
SKILL.md       (18 KB)                   SKILL.md            (~6 KB, 薄入口)
review.md      (1 KB)                    review.md           (~3 KB, 6 阶段)
rules/                                   rules/
  rules_guide.md                           rules_guide.md    (重排 6 节)
  round_structure.md                       round_structure.md(主流程表)
debaters/                                debaters/
  debaters.md                              debaters.md       (去冗余)
  *-perspective/                           *-perspective/    (未改)
                                         prompts/            ★ 新增
                                           round_prompts.md
                                         templates/          ★ 新增
                                           transcript_template.md
                                           artifacts_spec.md
                                         CHANGELOG.md        ★ 新增
                                         README.md           ★ 新增
```

### 📦 迁移说明

如果你已经在 v1.x 上跑过流程并落盘了文件，**所有产物文件名都没有变**——
v2 只是把 v1 已经在用的命名习惯（`正方-一辩稿.md` 等）写进了 `artifacts_spec.md` 强制规范。
直接把仓库切到 v2 即可，旧产物文件可以原地继续使用。

---

## v2.0.1 — 集成第三方 Skills（补丁）

### 🆕 新增

- `Skills/` 目录从 v1 原样保留并搬入 v2，包含 3 个第三方 Skill：
  - `debate-master-1.0.0/`
  - `gpyangyoujun-multi-search-engine-2.1.3/`
  - `pskoett-self-improving-agent-3.0.21/`
- `Skills/README.md` —— 三个 Skill 的速览与定位；
- **`Skills/integration.md`** ★ —— 集成手册：教模型在哪个阶段、为什么、怎么调用
  每个第三方 Skill；包含调用模板、回写约定、失败降级、阶段路由表、安装一致性自检；
- `templates/artifacts_spec.md §5` —— 新增 `.learnings/` 三件套的清单与红线；
- `prompts/round_prompts.md §0` —— 「外部 Skill 调用约定（所有 Prompt 通用）」，
  其余 Prompt 不再到处贴调用约定，统一指向 `Skills/integration.md`。

### 🔁 重构

- `SKILL.md`：
  - §0 索引新增一行指向 `Skills/integration.md`；
  - §2 依赖安装重做成 3 个依赖的对照表，并附编排器开赛前自检；
  - §6 顶层执行流：在阶段 A/B/C/D/H/I 的每一步标出**该步要主动调用的外部 Skill**，
    并指向 `Skills/integration.md` 对应小节；
  - §9 失败模式新增"外部 Skill 调用失败"一行。
- `review.md`：阶段流每个 Step 都标出该步要调用哪个外部 Skill（A 读先验、
  B/E 用 multi-search-engine 找弱点 + debate-master 标谬误、H 写 LEARNINGS）。
- `rules/round_structure.md`：
  - §0 赛前规划表追加"外部 Skill"列；
  - §3.1/§3.2 评委点评 + 赛后清理段落明确指明要调哪个 Skill。
- `prompts/round_prompts.md` §4/§5/§6：评委点评、赛后清理、Synthesis 三段 Prompt
  末尾追加 1 行"接下来该调用哪个外部 Skill 做什么"。

### ⚖️ 行为兼容性

- 三个第三方 Skill 的**原始文件未做任何修改**；
- v1 用过 `cocoloop install multi-search-engine` 安装方式继续有效；
- `self-improvement` 是 v2 引入的**新依赖（推荐而非必装）**，没安装也能跑 14 轮辩论，
  只是失去跨会话经验沉淀能力；
- 所有外部 Skill 调用失败都有降级方案（见 `Skills/integration.md` §6）。

### 📁 集成示意

```text
                                    Debate-Skill v2
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
              ▼                           ▼                           ▼
       debate-master              multi-search-engine          self-improvement
       （方法论百科）              （事实/数据检索）           （跨会话经验沉淀）
              │                           │                           │
              │ 阶段 B/D/H/I              │ 阶段 B/C/D/E/H/review     │ 阶段 A/H/I/review
              │ + Synthesis               │ + 临场质询核验            │ + 错误时
              └───────────┬───────────────┴───────────┬───────────────┘
                          │                           │
                          ▼                           ▼
                  Skills/integration.md   ←── 调用模板/时机/降级
```
