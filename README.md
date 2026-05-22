# Debate Skill v2

> 一个用来在 LLM 上跑**完整华语辩论赛**的 Skill。
> 8 位华语辩坛标志性辩手 × 14 轮赛制 × 隔离 / 内联两种执行模式 × 3 个外部 Skill 协作。

---

## 快速上手

1. 把整个 `Debate-Skill-v2/` 目录加入你的 Skill 加载器；
2. 确保 `Skills/` 目录里的 3 个依赖 Skill 已经被加载器识别（详见 `Skills/README.md`）；
3. 在对话里输入：

   ```text
   /debate 年轻人该不该回老家发展  我打正方
   ```

4. 编排器会：
   - 调用 `self-improvement` 读 `.learnings/` 历史经验（如果有）；
   - 自动选 8 位辩手分别填到正反双方 4 个辩位；
   - 走完 14 轮赛制；调用 `multi-search-engine` 帮辩手找资料、用 `debate-master`
     标注谬误；
   - 落盘备赛资料、一辩稿、二辩稿、三辩自证稿、四辩结辩稿、质询稿、攻防表；
   - 最后由中立主持人输出 Synthesis；
   - 调用 `self-improvement` 把本场关键经验沉淀到 `.learnings/`。

5. 想再"复盘 / 攻防演练"被复盘方的稿件：

   ```text
   /review
   ```

---

## 我为什么要读哪个文件？

| 你的角色 | 推荐阅读顺序 |
|---|---|
| **第一次用** | `SKILL.md` → `rules/round_structure.md` → `Skills/integration.md` |
| **要改规则** | `rules/rules_guide.md` |
| **要改 Prompt** | `prompts/round_prompts.md` |
| **要改辩稿格式 / 套语** | `rules/script_format.md` ★ v2.3 新增 |
| **查辩论方法论 / 战术 / 谬误** | `knowledge/` 目录 ★ v2.4 新增 |
| **学历史实录检索方法（赛前必做）** | `knowledge/06-历史实录检索.md` ★ v2.5 新增 |
| **要改输出长相** | `templates/transcript_template.md` + `templates/artifacts_spec.md` |
| **要改"调外部 Skill"的时机/方式** | `Skills/integration.md` |
| **要加新辩手** | 在 `debaters/` 里照已有目录新建一个 `<name>-perspective/`，并把名字写进 `debaters/debaters.md` |
| **要做复盘** | `review.md` |
| **想看相对 v1 改了什么** | `CHANGELOG.md` |

---

## 目录结构

```text
Debate-Skill-v2/
├── README.md                       # 本文件
├── CHANGELOG.md                    # v1 → v2 改了什么
├── SKILL.md                        # 主入口（薄）
├── review.md                       # /review 复盘流程
├── rules/                          # 规则手册
│   ├── rules_guide.md              # 单个环节的规则
│   ├── round_structure.md          # 14 轮顺序与时长
│   └── script_format.md            # ★ v2.3 真实辩稿写作规范（参考 debatetimer.cn）
├── knowledge/                      # ★ v2.4 华语辩论高阶知识库
│   ├── README.md                   # 知识库索引
│   ├── 00-philosophy.md            # 辩论哲学与流派（加法/减法派、心法）
│   ├── 01-立论与战场.md            # 立论、定义战、战场切割
│   ├── 02-质询与攻防.md            # 质询四步法、确认/处理/展示
│   ├── 03-自由辩与配合.md          # 团队配合、节奏控场、五大战术
│   ├── 04-结辩与升华.md            # 战场梳理、价值升华、金句设计
│   ├── 05-逻辑谬误手册.md          # 24 种常见谬误识别 + 反击模板
│   └── 06-历史实录检索.md          # ★ v2.5 debatetimer.cn 检索 + 敌情通报整理
├── prompts/                        # 调辩手用的 Prompt 模板库
│   └── round_prompts.md
├── templates/                      # 输出与产物模板
│   ├── transcript_template.md      # 最终辩论实录的渲染模板
│   └── artifacts_spec.md           # 所有要落盘的文件清单 + 章节
├── Skills/                         # ★ 第三方依赖 + 集成手册
│   ├── README.md                   # Skills 目录速览
│   ├── integration.md              # ★ 集成手册：何时/为何/如何调
│   ├── debate-master-1.0.0/                       # 辩论方法论百科
│   ├── gpyangyoujun-multi-search-engine-2.1.3/    # 16 引擎元搜索
│   └── pskoett-self-improving-agent-3.0.21/       # 跨会话经验沉淀
└── debaters/                       # 8 位辩手的思维操作系统
    ├── debaters.md                 # 索引（含推荐阵容）
    ├── zhan-qingyun-perspective/   # 詹青云
    ├── huang-zhi-zhong-perspective/# 黄执中
    ├── chen-ming-perspective/      # 陈铭
    ├── yan-ru-jing-perspective/    # 颜如晶
    ├── pang-ying-perspective/      # 庞颖
    ├── hu-jian-biao-perspective/   # 胡渐彪
    ├── ma-wei-wei-perspective/     # 马薇薇
    └── zhou-xuan-yi-perspective/   # 周玄毅
```

---

## 三个外部 Skill 一句话简介

| Skill | 作用 | 何时调 | 详见 |
|---|---|---|---|
| `debate-master` | 6 维度方法论 / 谬误表 / 攻防口诀 | 阶段 B 备赛、D 战术暂停、H 评委点评 | `Skills/integration.md` §1 |
| `multi-search-engine` | 16 个搜索引擎，无需 API key | 阶段 B 检索论据、质询轮临场核验、复盘找弱点 | `Skills/integration.md` §2 |
| `self-improvement` | 跨会话经验记入 `.learnings/` | 阶段 A 读先验 / H+I 写经验 / review 每轮 | `Skills/integration.md` §3 |

---

## 设计原则

1. **主入口薄、子文件厚**：`SKILL.md` 只负责"调度 + 引用"，不内嵌任何 Prompt / 输出格式。
2. **一处定义、多处引用**：规则在 `rules/`、模板在 `prompts/`、产物结构在 `templates/`、
   外部 Skill 在 `Skills/integration.md`，各自只有一份"事实来源（source of truth）"。
3. **辩手卡保持原作**：v2 不改 `debaters/*-perspective/SKILL.md`，
   尊重原作者捕捉的辩手 DNA。
4. **外部 Skill 解耦**：本仓库不内嵌外部 Skill 的实现，只在 `Skills/integration.md`
   规定"何时/为何/如何调"以及失败降级路径，外部 Skill 可独立升级。
5. **可验证产出**：所有该落盘的文件都在 `templates/artifacts_spec.md` 列清楚，
   编排器每阶段必须自检。

---

## 致谢

- 原版仓库：<https://github.com/IsSmallPigPig/Debate-Skill>
- 8 位辩手的人设档案（`debaters/*-perspective/SKILL.md`）来自原作者；
- `Skills/` 下三个第三方 Skill 各自归属其原作者，本仓库仅做集成；
- v2 重构在 v1 基础上完成，仅做结构和可读性优化，未改变功能边界。
