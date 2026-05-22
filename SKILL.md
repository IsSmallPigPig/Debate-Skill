---
name: Debate-Skills
version: 2.0.0
description: |
  运行结构化的多角色华语辩论赛（BP/华语赛制混合），支持自动选角、隔离/内联两种执行模式、
  多轮交锋与中立总结。触发词：
    `/debate`  → 进入完整辩论流程
    `/review`  → 进入复盘流程（见 review.md）
  本文件是入口/分诊文件，只描述「做什么、读哪里、按什么顺序」；具体规则、提示模板、轮次脚本、
  输出模板分别放在 rules/、prompts/、templates/ 下，按需加载。
---

# Debate Skill v2 · 入口文件

> v2 的设计原则：**主文件只做调度，不做执行**。所有可复用的内容（规则、Prompt 模板、轮次脚本、
> 输出格式、复盘流程）都拆到子文件，按需 `read_file` 加载，避免一次性灌满上下文。

---

## 0. 快速索引（先看这里）

| 你想做的事 | 该读哪个文件 |
|---|---|
| 了解整体流程和心智模型 | 本文件 §1–§5 |
| 看具体的辩论规则（质询/自证/自由辩…） | `rules/rules_guide.md` |
| 看完整的 14 个轮次怎么排 | `rules/round_structure.md` |
| 看每一轮该用什么 Prompt 调辩手 | `prompts/round_prompts.md` |
| 看最终辩论记录怎么排版 | `templates/transcript_template.md` |
| 看赛前/赛后要生成哪些稿件文件 | `templates/artifacts_spec.md` |
| **看本流程依赖的 3 个外部 Skill 怎么用** | **`Skills/integration.md`** ★ |
| 进入复盘 | `review.md` |
| 查可用辩手清单 | `debaters/debaters.md` |
| 查某位辩手的人设 DNA | `debaters/<name>-perspective/SKILL.md` |

---

## 1. 这个 Skill 解决什么

让模型扮演一个**辩论赛编排器（Orchestrator）**，按华语辩论赛制（4v4，14 轮）组织一场围绕
具体辩题、有明确正反方、有质询/自证/自由辩/总结的完整对抗，并：

1. 自动从 `debaters/` 中挑选/分配 8 位辩手到正反双方；
2. 按轮次脚本驱动每位辩手按其 Skill 人设发言；
3. 落盘必要的赛前/中场/赛后文档（一辩稿、攻防表、前场整理、最终稿…）；
4. 最后由中立主持人输出 Synthesis。

---

## 2. 依赖安装（首次运行前执行一次）

> 仅当当前环境**未安装**对应 Skill 时才执行；已安装则跳过。三个依赖的**用途**和**调用时机**
> 详见 `Skills/integration.md`。

| 依赖 Skill | 用途速记 | 安装方式 | 强制 |
|---|---|---|:---:|
| `debate-master` | 辩论方法论百科（6 维度、谬误表、攻防口诀） | 见 `Skills/debate-master-1.0.0/` 本地副本，或自带 | ⛔ 推荐 |
| `multi-search-engine` | 16 引擎元搜索，备赛 / 临场核验 | 见 §2.1 | ✅ 必装 |
| `self-improvement` | 跨会话经验沉淀到 `.learnings/` | 见 `Skills/integration.md` §3.3 | ⛔ 推荐 |

### 2.2 编排器自检（开赛前必跑）

```text
[ ] Skill(debate-master)        可用？  否 → 用编排器自身的辩论知识降级
[ ] Skill(multi-search-engine)  可用？  否 → 走 web_search/web_fetch fallback
[ ] Skill(self-improvement)     可用？  否 → 跳过经验沉淀
```

> 辩论方法论的二次参考资料：https://debatetimer.cn/ 。

---

## 3. 输入解析（开赛前必须确认）

从用户的 `/debate ...` 调用中解析：

| 字段 | 说明 | 必填 | 缺省策略 |
|---|---|---|---|
| `topic` | 辩题 | ✅ | 若上下文已隐含主题（如刚结束的并行讨论），直接沿用 |
| `support` | 用户站哪边（正方 / 反方） | ✅ | 用于决定最终要为哪一方出具完整稿件 |
| `personas` | 8 个辩手（正反各 4） | ⛔ | 未指定 → 走 §4 自动选角 |
| `rounds` | 轮次方案 | ⛔ | 默认走 `rules/round_structure.md` 的 14 轮完整流程 |
| `mode` | `isolated` / `inline` | ⛔ | 默认 `isolated`；用户说 "inline / fast / single-context / mode=inline" → 切换 |
| `synthesis` | 是否要主持人总结 | ⛔ | 默认开启；用户说 "no synthesis" → 关闭 |

**强约束**：在不确认 `topic` 和 `support` 之前，**绝对不要**开始任何轮次。

---

## 4. 自动选角协议

优先级：

1. 用户明确点名的角色 → **绝不覆盖**
2. 从 `debaters/debaters.md` + `debaters/*-perspective/SKILL.md` 中实际存在的角色里挑
3. 找不到至少 4 个可用角色 → 只询问用户一次，然后停下，**不要凭空捏造**

### 4.1 推荐基线阵容（来自 debaters.md）

| 辩位 | 正方推荐 | 反方推荐 |
|:---:|---|---|
| 一辩 | 胡渐彪（攻防/定义） | 庞颖（框架/系统） |
| 二辩 | 庞颖（系统论证） | 颜如晶 / 周玄毅（情感 / 归谬） |
| 三辩 | 黄执中（价值升华） | 周玄毅 / 詹青云（深度解构） |
| 四辩 | 陈铭 / 马薇薇（收尾/金句） | 詹青云 / 陈铭（升华/金句） |

> 选角时优先满足**辩位推荐**（debaters.md 中每位辩手都标了推荐辩位）。

### 4.2 选角启发式

- 优先选**视角差异最大**的组合，而不是风格相近的；
- 同一辩手不得同时出现在正反两方；
- 8 个位置必须由 8 位**不同**辩手填满；如果可用辩手不足 8 人，允许一位辩手在两个不同辩位
  上出现，但需要在开场说明并标注 `(兼)`；
- 如果置信度低，开赛前一句话报备假设，**不要中途追问**。

---

## 5. 执行模式（Mode）

| 模式 | 一句话 | 适用 |
|---|---|---|
| `isolated`（默认） | 每个辩手用一个**持久子代理**，编排器只装配记录、不代写发言 | 担心编排器把所有辩手写成一个味；希望硬碰硬 |
| `inline` | 编排器在主上下文里**依次**调用每个 Skill，自己代写发言 | 速度优先；希望中途人工纠偏 |

两种模式的详细执行步骤（持久代理、Prompt 模板、token 节约）见
**`prompts/round_prompts.md` §1（隔离模式） / §2（内联模式）**。

---

## 6. 顶层执行流（Orchestrator 主循环）

> 每个阶段右侧的「外部 Skill」栏标出**该阶段要主动调用**的第三方 Skill；
> 详细调用模板、Prompt、回写约定见 `Skills/integration.md` 对应小节。

```text
[阶段 A] 确认输入
  ├─ 读 §3，确认 topic / support / mode
  ├─ 读 §4 + debaters/debaters.md，落定 8 位辩手名单
  └─ 外部 Skill: self-improvement     → 读 .learnings 历史先验
                                        （见 Skills/integration.md §3.4「赛前自动读取」）

[阶段 B] 赛前准备
  ├─ 读 rules/round_structure.md「赛前规划」
  ├─ 正反两方分别完成「论点架构 / 资料收集 / 攻防表」
  ├─ 各自落盘  正方-备赛资料.md / 反方-备赛资料.md
  │           正方-一辩稿.md   / 反方-一辩稿.md
  │   ⚠ 此阶段正反双方互不可见
  └─ 外部 Skill:
      ├─ debate-master       → 6 维度模板，谬误表，攻防口诀
      │                        （Skills/integration.md §1）
      └─ multi-search-engine → 每个论点 ≥1 例子 / 每个攻防点 ≥1 反证
                               （Skills/integration.md §2）

[阶段 C] 前场（第 1–4 轮）
  ├─ 读 rules/round_structure.md + rules/rules_guide.md
  ├─ R1 正一申论 → R2 反四质询正一 → R3 反一申论 → R4 正四质询反一
  ├─ Prompt 模板见 prompts/round_prompts.md §3.1–§3.4
  └─ 外部 Skill: multi-search-engine ⚠按需，质询方需要核验对方数据时调用
                                       （Skills/integration.md §2.3「事实核验」）

[阶段 D] 战术暂停（第 5 轮）
  ├─ 双方分别复盘前 4 轮，承认对方至少 1 个对的点
  ├─ 落盘  正方-前场整理.md / 反方-前场整理.md
  └─ 外部 Skill:
      ├─ debate-master       → 用谬误表标注对方论证漏洞
      └─ multi-search-engine → 补充对方刚抛但未引证的数据

[阶段 E] 后场（第 6–11 轮）
  ├─ R6 正二申论 → R7 反三质询正二 → R8 反二申论 → R9 正三质询反二
  ├─ R10 反三自证 → R11 正三自证
  └─ Prompt 模板见 prompts/round_prompts.md §3.6–§3.11

[阶段 F] 自由辩论（第 12 轮）
  └─ 由正方先开口，单人单次发言，正反交替，≤ 40 次

[阶段 G] 总结陈词（第 13–14 轮）
  ├─ R13 反四总结
  └─ R14 正四总结

[阶段 H] 评委点评 + 赛后清理
  ├─ 评委按 rules/rules_guide.md 的标准点评胜负与得失
  ├─ 用户持方辩手头脑风暴，按 templates/artifacts_spec.md 修改并落盘最终稿件：
  │    一辩稿 / 二辩稿 / 三辩自证稿 / 四辩结辩稿
  │    三质二质询稿 / 四质一质询稿
  │    攻防表（最终版）
  ├─ 用户质询（可选）
  └─ 外部 Skill:
      ├─ debate-master       → 评委用方法论术语解释胜负
      ├─ multi-search-engine → 给修改后稿件补证据
      └─ self-improvement    → 写 LEARNINGS.md (best_practice)
                               （Skills/integration.md §3.4）

[阶段 I] Synthesis（若开启）
  ├─ 由编排器以中立主持人身份输出，规则见 §8
  └─ 外部 Skill: self-improvement     → 写 LEARNINGS.md (insight)
                                        本场的元层观察，供下次同类辩题用
```

最终辩论记录的渲染格式见 **`templates/transcript_template.md`**。
每个阶段的外部 Skill 详细调用方式见 **`Skills/integration.md` §5 阶段路由表**。

---

## 7. 长度约束

- **每位辩手每轮**：目标 150–350 词；超出会迅速重复自己；
- **完整 14 轮 + 8 辩手**：预估 6000–9000 词；如果用户要求更长，开赛前提醒；
- **稿件文件**（一辩稿、结辩稿等）：每篇 300–800 词，可超出辩位上限；
- 当某辩手 Skill 偏爱长独白（如黄执中），在该轮 Prompt 中明确写**"控制在 300 词以内，
  只讲一个核心论点"**。

---

## 8. Synthesis（主持人总结）规则

如果开启，结尾追加一节，由编排器自身的声音（不是任何辩手）输出：

- ✅ 点出**核心分歧**，不要打"大家都有道理"的和稀泥；
- ✅ 点出多轮交锋中**真实出现**的共识；
- ✅ 识别**哪个辩手更新了看法**、更新了什么；
- ✅ 可以给**条件性建议**（"如果你在 X 情境，更应倾向 Y"），但**不宣布赢家**；
- ❌ 不要捏造辩手没说过的立场；
- ✅ 可以把已有论点重构为更结构化的拆解 / 启发式 / 决策框架。

---

## 9. 失败模式速查（在每轮开始前默念）

| 症状 | 处理 |
|---|---|
| **并行独白** —— 第 2 轮后辩手互不点名 | 重发该轮 Prompt，写明 "你必须回应 X 关于 Y 的主张" |
| **虚假共识** —— 辩手过快趋同 | 信任 Skill 文件；不要软化原本对立的观点 |
| **主题漂移** —— 跑题 | 每轮 Prompt 必须重申 `topic` 原文 |
| **角色泄漏** —— 听起来像普通 GPT 回答 | 重新 fresh 调用该辩手 Skill；不要凭记忆续写人设 |
| **稿件失落** —— 阶段 H 没落盘 | 按 `templates/artifacts_spec.md` 强制清单复核 |
| **外部 Skill 调用失败** | 按 `Skills/integration.md` §2.5 / §6 降级，并写一条 `ERRORS.md` |

---

## 10. 退出角色

最终 Synthesis 输出后，所有辩手默认**退出角色态**。用户继续追问，按常规模型身份回答；
除非用户再次以 `詹青云视角` 等触发词召唤某个 Skill。

---

## 11. 路由：用户输入到此 Skill 怎么走？

```text
用户输入
  ├─ 包含 "/debate"           → 本文件，按 §6 流程
  ├─ 包含 "/review"           → review.md
  ├─ 包含某辩手触发词         → debaters/<name>-perspective/SKILL.md（单独人设回答）
  └─ 其它                     → 不属于本 Skill 处理范围
```
