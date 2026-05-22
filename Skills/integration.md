---
name: Debate-Skills/skills-integration
version: 2.0.0
description: |
  教模型「在 Debate 流程的哪一步、为什么、怎么」调用三个第三方 Skill：
    1. debate-master            —— 辩论方法论百科
    2. multi-search-engine      —— 16 引擎元搜索
    3. self-improving-agent     —— 跨会话经验沉淀
  本文件是「集成手册」，调用细节集中在这里，主流程文档只用一行指针引用本文件的小节。
---

# Skills Integration · 第三方 Skill 集成手册

> 阅读建议：
> - 第一次：从头读到尾，理解三个 skill 各管什么；
> - 跑流程时：按 §5「阶段路由表」查"我现在该不该调用"。

---

## 0. 总览

| 你想做的事 | 用哪个 Skill | 看本文件哪节 |
|---|---|---|
| 查"循环论证、稻草人怎么破" | `debate-master` | §1 |
| 查 6 大维度的"攻防/语言/心态"清单 | `debate-master` | §1 |
| 检索某辩题的事实/数据/案例 | `multi-search-engine` | §2 |
| 验证对方刚抛的数据是否真实 | `multi-search-engine` | §2.4 |
| 把"对方今天打的招、我方暴露的漏洞"沉淀下来供下次复用 | `self-improving-agent` | §3 |
| 跨会话同步：上一场学到的经验自动出现在下一场 | `self-improving-agent` | §3.4 |

---

## 1. debate-master · 辩论方法论百科

### 1.1 它是什么

一份 **6 维度 × 多张表格** 的辩论能力体系手册：
底层认知（逻辑模型、谬误表）/ 内容架构 / 攻防技术 / 语言表达 / 临场应变 / 心态与团队。

**对编排器的价值**：当编排器、辩手或评委需要引用一个**通用方法论标签**（"这是稻草人"
"这里该用归谬"）时，调用 `debate-master` 加载方法论库后，所有引用都对得上同一套术语。

### 1.2 什么时候调用

| 阶段 | 触发条件 | 用途 |
|---|---|---|
| **B 赛前规划** | 总是 | 让辩手在做"论点架构 / 攻防表"时对照 6 维度填表 |
| **D 战术暂停** | 总是 | 让双方在"前场整理"时用谬误表标注对方哪些论证有漏洞 |
| **H 评委点评** | 总是 | 评委用 `debate-master` 的术语解释"为什么这一击有效" |
| **H 赛后清理** | 用户持方需要 | 持方在改稿时对照 6 维度自查 |

### 1.3 调用模板

**编排器侧（一次性加载，全场复用）：**

```text
Skill(skill="debate-master")
→ 此后所有引用「逻辑模型 / 谬误 / 攻防口诀」都以该 skill 中的定义为准。
```

**辩手子代理侧（在赛前规划 Prompt 里追加）：**

```text
在做论点架构 / 攻防表前，你可以调用 Skill(skill="debate-master")
查阅 6 维度模板。重点关注：
  - 一、底层认知 → 逻辑谬误避雷表
  - 二、内容架构 → 定义/标准/论点/论据/价值 五元素
  - 三、攻防技术 → 质询盘问 / 反驳拆解 / 自由辩交锋
查完后，把对应的方法论标签写进备赛资料对应论点旁边（如「论点 2：用归谬反击」）。
```

### 1.4 输出回写约定

每位辩手在 `<side>-备赛资料.md` 的攻防表里增加一列 `方法论标签`，
取值范围 = `debate-master` 中出现的术语，例如：

| # | 对方可能攻击 | 我方回应 | 方法论标签 |
|---|---|---|---|
| 1 | "你是以偏概全" | 给出大样本数据 | 反击-以偏概全 |
| 2 | 偷换定义 | 重申一辩定义 | 反击-偷换概念 |

---

## 2. multi-search-engine · 16 引擎元搜索

### 2.1 它是什么

无需 API key 即可调用 16 个搜索引擎（7 中文 + 9 海外）的 skill。
辩手用它做**事实/数据/案例**的检索。

> 默认中文辩题用国内引擎（Baidu / Bing CN / 360 / Sogou / WeChat / Shenma），
> 海外辩题或需英文资料时用 Google / DuckDuckGo / Brave / WolframAlpha 等。
> 详细引擎列表见 `Skills/gpyangyoujun-multi-search-engine-2.1.3/SKILL.md`。

### 2.2 什么时候调用

| 阶段 | 调用主体 | 用途 |
|---|---|---|
| **B 赛前规划 §2 资料收集** | 双方所有辩手 | 给每个论点找 ≥1 个例子或数据 |
| **B 赛前规划 §3 攻防表** | 双方所有辩手 | 给对方可能的攻击点也找一份反证 |
| **C/E 质询轮** | 质询方 | 临场需要追问"对方刚说的数据从哪来" |
| **D 战术暂停** | 双方 | 验证前 4 轮里有没有"听起来很强但其实站不住"的论据 |
| **H 赛后清理** | 用户持方 | 给修改后的稿件再补几条证据 |
| **review.md 复盘** | 对立持方 | 找"对方稿件里没引证、可被攻破"的数据点 |

### 2.3 调用模板

**第一次使用（每个辩手子代理）：**

```text
Skill(skill="multi-search-engine")
```

**做事实检索（备赛阶段）：**

```text
我现在是 {persona}，正在为「{topic}」备赛。请帮我检索：
  - 关键词：{query}
  - 优先引擎：{中文场 → Baidu/Bing CN/WeChat；海外场 → Google/DuckDuckGo}
  - 时间范围：{近 1 年 / 不限}（中文场常用 Baidu 的 `gpc` 参数，海外用 `tbs=qdr:y`）
  - 我要的是：≥3 条不同来源的{数据 / 案例 / 学术观点}
对每条来源返回：{标题、URL、关键摘录、是否可作正式引用}
```

**做事实核验（质询临场）：**

```text
对方刚说「{对方论据原文}」。请帮我用 multi-search-engine 同时跑：
  - DuckDuckGo: 原文搜
  - Bing INT: 原文 + "辟谣 OR 反驳 OR 错误"
  - WolframAlpha: 如果是可计算量，直接算一遍
返回结论：{该论据真 / 假 / 部分真}，并给出 ≤3 条最强反证。
```

### 2.4 输出回写约定

- 备赛检索结果 → `<side>-备赛资料.md` §2「资料收集」表格，**每条必须带 URL**；
- 临场核验结果 → 直接体现在该辩手的发言里（"刚才对方提到的 X，根据 [来源]，
  事实是 Y"），同时附加到 `<user_side>-攻防表.md` 的"备用反击"列。

### 2.5 失败模式速查

| 症状 | 处理 |
|---|---|
| 引擎 403/429 | skill 自带 cookie 重试；如果连续 2 次都失败，换引擎 |
| 中文辩题用 Google 搜不到 | 切到 Baidu / Bing CN / WeChat |
| 资料明显有党派/营销倾向 | 至少再用 1 个**异质**引擎交叉验证 |
| 完全找不到资料 | 退而求其次：用"类比案例 + 经典文献"代替"硬数据" |

---

## 3. self-improving-agent · 跨会话经验沉淀

### 3.1 它是什么

把"错误 / 学习 / 改进点"写到工作区根目录的 `.learnings/` 下三个 markdown 文件：

```text
.learnings/
├── LEARNINGS.md         # 经验、最佳实践、知识空白
├── ERRORS.md            # 工具调用失败、子代理崩溃等
└── FEATURE_REQUESTS.md  # 用户提出但当前没实现的功能
```

**为什么 Debate-Skill 需要它**：辩论是反复打的，每场辩论结束后产生的"对方今天打的招、
我方暴露的漏洞、哪类辩题该用哪种阵容"，应当沉淀下来供下一场 / 下一次复盘自动参考。

> 这是 v2 引入的**新依赖**，原版 v1 没有用到。属于"可选但强烈推荐"。

### 3.2 什么时候调用

| 阶段 | 写什么 | 写到哪个文件 |
|---|---|---|
| **任何阶段，工具调用失败** | 报错信息 + 上下文 + 当时在做什么 | `ERRORS.md` |
| **H 评委点评后** | 本场胜方的 ≤3 个关键得分点 / 败方的 ≤3 个失分点 | `LEARNINGS.md`（category=`best_practice`） |
| **H 赛后清理后** | 用户持方"如果重打会怎么改" | `LEARNINGS.md`（category=`correction`） |
| **I Synthesis 后** | 本场的元层观察："这类辩题更适合哪种阵容/打法" | `LEARNINGS.md`（category=`insight`） |
| **review.md 每轮复盘** | 对方在本轮新攻出的角度 + 我方修复方案 | `LEARNINGS.md`（category=`best_practice`） |
| **辩手 Skill 不存在 / 缺失** | 该需求 + 建议补充哪位辩手 | `FEATURE_REQUESTS.md` |

### 3.3 安装

如果当前环境没装该 skill，按其官方说明：

```bash
# 推荐：用 cocoloop（与 multi-search-engine 一致）
# URL 示例（请以 cocoloop 商店里的最新版为准）
cocoloop install pskoett-self-improving-agent-3.0.21

# 手动 fallback：
git clone https://github.com/peterskoett/self-improving-agent.git \
  ~/.openclaw/skills/self-improving-agent
```

首次使用前会自动建好 `.learnings/` 目录和三个空文件，无需手动初始化。

### 3.4 调用模板

**编排器侧（每场辩论结束后调用一次）：**

```text
Skill(skill="self-improvement")

# 然后追加写入：
追加一条 LEARNINGS.md 条目：
  - 类别: best_practice
  - 标题: 在「{topic}」中，{胜方阵营}「{关键战术}」高效
  - 上下文: 第 {N} 轮 {辩位} 提出「{原话摘要}」，对方未能拆解
  - 启发: 下一次面对「{同类辩题特征}」时优先考虑此战术
  - 出处: {本辩论实录 md 路径}
```

**编排器侧（出现工具/子代理错误时）：**

```text
Skill(skill="self-improvement")

追加一条 ERRORS.md 条目：
  - 时间: {ISO 时间}
  - 阶段: {B/C/D/E/F/G/H/I 或 review}
  - 工具: {Skill 名 / 工具名}
  - 错误: {错误摘要，不要贴 secret/token}
  - 复现条件: {简要}
  - 当前处理: {如何回退}
```

**赛前自动读取（每场开赛前必做）：**

```text
Skill(skill="self-improvement")

请读取 .learnings/LEARNINGS.md，筛出与「{topic}」**同类**或**同辩位**相关的条目，
返回 ≤5 条最相关的经验，作为本场开赛前的"先验"，注入到双方辩手的赛前规划提示里。
```

### 3.5 写入红线（来自 self-improvement skill 原始约定）

- ❌ 不要写任何 secret / token / 私钥 / 环境变量；
- ❌ 不要把完整辩论实录复制进 LEARNINGS.md，只写摘要 + 出处链接；
- ✅ 优先写**短结论 + 出处文件路径**，让下次会话能凭路径回查原文。

---

## 4. 三个 Skill 的协作链

一场辩论从头到尾，三个 Skill 的协作顺序如下：

```text
┌──────────────────────────────────────────────────────────────────┐
│ 阶段 A · 确认输入                                                  │
│   ├─ Skill(self-improvement) → 读 .learnings 与本辩题相关的先验    │
│   └─ 把先验摘要塞进编排器的 system context                         │
│                                                                  │
│ 阶段 B · 赛前规划                                                  │
│   ├─ 双方辩手 Skill(debate-master) → 对照 6 维度做论点架构          │
│   ├─ 双方辩手 Skill(multi-search-engine) → 检索论据 + 攻防表反证    │
│   └─ 任一 Skill 调用失败 → Skill(self-improvement) 写 ERRORS.md    │
│                                                                  │
│ 阶段 C/E · 质询轮                                                  │
│   └─ 质询方临场 Skill(multi-search-engine) 核验对方数据（按需）     │
│                                                                  │
│ 阶段 D · 战术暂停                                                  │
│   ├─ 双方 Skill(debate-master) → 用谬误表标注前 4 轮论证            │
│   └─ 双方 Skill(multi-search-engine) → 检索遗漏的反证               │
│                                                                  │
│ 阶段 H · 评委点评 + 赛后清理                                        │
│   ├─ 评委 Skill(debate-master) → 用方法论术语解释胜负               │
│   ├─ 持方 Skill(multi-search-engine) → 给修改后稿件补证据           │
│   └─ Skill(self-improvement) → 写 LEARNINGS.md（best_practice）   │
│                                                                  │
│ 阶段 I · Synthesis                                                │
│   └─ Skill(self-improvement) → 写 LEARNINGS.md（insight）         │
│                                                                  │
│ review.md · 复盘                                                  │
│   ├─ 对立持方 Skill(multi-search-engine) → 找稿件可攻破的证据点      │
│   ├─ 被复盘方 Skill(debate-master) → 对照 6 维度自查改稿            │
│   └─ Skill(self-improvement) → 每轮写 LEARNINGS.md                │
└──────────────────────────────────────────────────────────────────┘
```

---

## 5. 阶段路由表（编排器随手翻）

把 SKILL.md §6 的阶段编号 × 三个 skill 做成查找表。**`-` 表示该阶段不需要调用。**

| 阶段 | debate-master | multi-search-engine | self-improving-agent |
|---|:---:|:---:|:---:|
| A 确认输入 | - | - | ✅ 读先验 |
| B 赛前规划 | ✅ 查方法论 | ✅ 检索论据 | ⚠ 出错才写 |
| C 前场 R1–R4 | - | ⚠ 临场核验 | ⚠ 出错才写 |
| D 战术暂停 | ✅ 谬误标注 | ✅ 补证据 | ⚠ 出错才写 |
| E 后场 R6–R11 | - | ⚠ 临场核验 | ⚠ 出错才写 |
| F 自由辩 R12 | - | ⚠ 临场核验 | ⚠ 出错才写 |
| G 总结 R13–R14 | - | - | ⚠ 出错才写 |
| H 评委 + 赛后清理 | ✅ 解释胜负 | ✅ 补证据 | ✅ 写 best_practice |
| I Synthesis | - | - | ✅ 写 insight |
| review 每轮复盘 | ✅ 自查改稿 | ✅ 找攻击点 | ✅ 写 best_practice |

> ✅ = 必做  ⚠ = 按需做  - = 不需要

---

## 6. 安装一致性自检

开赛前编排器自检：

```text
[ ] Skill(debate-master)            可用？
[ ] Skill(multi-search-engine)      可用？
[ ] Skill(self-improvement)         可用？（v2 新依赖，可选但推荐）
[ ] .learnings/ 目录存在？           （首次使用 self-improvement 会自动建）

任一✅项不可用 → 按 ../SKILL.md §2 / 本文件 §3.3 安装。
任一⚠项不可用 → 降级运行：
  - 没有 debate-master      → 方法论术语用编排器自身知识代替
  - 没有 multi-search-engine → 走 web_search / web_fetch fallback
  - 没有 self-improvement   → 跳过经验沉淀，本场结束不写 .learnings
```
