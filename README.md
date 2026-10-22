# Debate Skill v3

> 一个用来在 LLM 上跑**完整华语辩论赛**的 Skill。
> 8 位华语辩坛标志性辩手 × 14 轮赛制 × 隔离 / 内联两种执行模式 × 3 个外部 Skill 协作。
> **v3 新增**：规模预设 · 机器校验完成契约 · 断点续跑 · 证据台账 · debatetimer 官方 MCP ·
> **辩论协同台**（网页实时展示 / 导出 Word / 复制原文位置向 Agent 提问）。

---

## 快速上手

1. 把整个仓库目录加入你的 Skill 加载器；
2. 确保 `Skills/` 目录里的 3 个依赖 Skill 已经被加载器识别（安装见 `SKILL.md §2.1`）；
   可选：`npx add-mcp https://debatetimer.cn/api/mcp` 安装历史实录检索 MCP；
3. 在对话里输入：

   ```text
   /debate 年轻人该不该回老家发展  我打正方
   /debate 年轻人该不该回老家发展  我打正方  preset=quick        ← 速通赛（约 1.2 万字）
   ```

4. 编排器会：
   - 调用 `self-improvement` 读 `.learnings/` 历史经验（如果有）；
   - 自动选 8 位辩手分别填到正反双方 4 个辩位；
   - `debate_ctl.py init` 建立会话目录，逐环节写入 `debate-output/<session>/transcript/`；
   - 用 debatetimer MCP 检索同题/近题历史实录，用 `multi-search-engine` 找资料并登记证据台账；
   - 每个环节结束由 `debate_ctl.py step … --status done` **机器校验**（字数、回合、括号、占位符…），不通过就重做；
   - 落盘备赛资料、一辩稿、二辩稿、三辩自证稿、四辩结辩稿、质询稿、攻防表；
   - 最后由中立主持人输出 Synthesis，并可一键导出整场实录 Word；
   - 调用 `self-improvement` 把本场关键经验沉淀到 `.learnings/`。

5. 打开**辩论协同台**实时观看、导出、逐段提问：

   ```bash
   python3 collab/server.py --root debate-output     # 实战
   python3 collab/server.py --root collab/demo       # 先看示例会话
   # 浏览器打开 http://localhost:8765
   ```

6. 中断了？输入 `/debate resume` 从断点继续；想复盘：`/review`；处理网页上排队的问题：`/ask`。

---

## 我为什么要读哪个文件？

| 你的角色 | 推荐阅读顺序 |
|---|---|
| **第一次用** | `SKILL.md` → `rules/round_structure.md` → `collab/README.md` |
| **要改时长 / 字数下限 / 校验项** | `rules/presets.json` ★ v3 单一事实来源 |
| **要改规则** | `rules/rules_guide.md` |
| **要改 Prompt** | `prompts/round_prompts.md` |
| **要改辩稿格式 / 套语** | `rules/script_format.md` |
| **查辩论方法论 / 战术 / 谬误** | `knowledge/` 目录 |
| **学历史实录检索方法（赛前必做）** | `knowledge/06-历史实录检索.md`（v3：官方 MCP） |
| **要改输出长相** | `templates/transcript_template.md` + `templates/artifacts_spec.md` |
| **要改「调外部 Skill」的时机/方式** | `Skills/integration.md` |
| **要接入/改造协同台** | `collab/README.md` + `collab/PROTOCOL.md` ★ v3 |
| **要加新辩手** | 在 `debaters/` 里照已有目录新建 `<name>-perspective/`，写进 `debaters/debaters.md`，遵守 `debaters/PERSONA_PROTOCOL.md` |
| **要做复盘** | `review.md` |
| **想看改了什么** | `CHANGELOG.md`、`docs/v3-审查与升级报告.md` |

---

## 目录结构

```text
Debate-Skill/
├── README.md                       # 本文件
├── CHANGELOG.md                    # 版本记录（v1 → v3）
├── SKILL.md                        # 主入口（薄）
├── review.md                       # /review 复盘流程
├── docs/v3-审查与升级报告.md        # ★ v3 全量审查发现与升级说明
├── rules/                          # 规则手册
│   ├── presets.json                # ★ v3 单一事实来源：步骤 / 时长 / 字数下限 / 校验项 / 预设
│   ├── rules_guide.md              # 单个环节的规则
│   ├── round_structure.md          # 14 轮顺序与时长
│   └── script_format.md            # 真实辩稿写作规范（参考 debatetimer.cn）
├── knowledge/                      # 华语辩论高阶知识库（00–06）
├── prompts/round_prompts.md        # 调辩手用的 Prompt 模板库（含 §0.6 协同落盘、§1.5 互动接力）
├── templates/
│   ├── transcript_template.md      # 最终辩论实录的渲染模板
│   ├── artifacts_spec.md           # 所有要落盘的文件清单 + 章节
│   └── evidence_ledger.md          # ★ v3 证据台账模板与防编造规则
├── tools/                          # ★ v3 纯标准库工具（Python 3.8+）
│   ├── debate_ctl.py               # init / next / step / status / lint / locate / ask / export / budget
│   ├── debatetimer.py              # debatetimer.cn 官方 MCP 命令行客户端
│   └── debatekit/                  # 共享核心：分块锚点、预设、会话、校验、定位、docx、导出
├── collab/                         # ★ v3 辩论协同台（脚手架）
│   ├── server.py                   # 标准库 HTTP 服务
│   ├── web/                        # 单页应用（无外部依赖）
│   ├── PROTOCOL.md                 # Agent 侧协议
│   ├── README.md                   # 使用说明
│   └── demo/                       # 示例会话
├── Skills/                         # 第三方依赖 + 集成手册
│   ├── README.md
│   ├── integration.md
│   ├── debate-master-1.0.0/
│   ├── gpyangyoujun-multi-search-engine-2.1.3/
│   └── pskoett-self-improving-agent-3.0.21/
└── debaters/                       # 8 位辩手的思维操作系统
    ├── debaters.md                 # 索引（含 v3 修正后的基线阵容）
    ├── PERSONA_PROTOCOL.md         # ★ v3 人设加载协议 + 护栏
    └── <name>-perspective/         # SKILL.md + references/research/01–06
```

---

## 三个外部 Skill（+1 个 MCP）一句话简介

| 依赖 | 作用 | 何时调 | 详见 |
|---|---|---|---|
| `debate-master` | 6 维度方法论 / 谬误表 / 攻防口诀 | 阶段 B 备赛、D 战术暂停、H 评委点评 | `Skills/integration.md` §1 |
| `multi-search-engine` | 16 个搜索引擎，无需 API key | 阶段 B 检索论据、质询轮临场核验、复盘找弱点 | `Skills/integration.md` §2 |
| `self-improvement` | 跨会话经验记入 `.learnings/` | 阶段 A 读先验 / H+I 写经验 / review 每轮 | `Skills/integration.md` §3 |
| debatetimer MCP ★v3 | 华语辩论历史实录检索 | 阶段 B §3B.0 | `knowledge/06-历史实录检索.md` §2.4 |

---

## 设计原则

1. **主入口薄、子文件厚**：`SKILL.md` 只负责「调度 + 引用」，不内嵌任何 Prompt / 输出格式。
2. **一处定义、多处引用**：数字在 `rules/presets.json`、规则在 `rules/`、模板在 `prompts/`、
   产物结构在 `templates/`、外部 Skill 在 `Skills/integration.md`，各自只有一份「事实来源」。
3. **辩手卡保持原作**：v3 仍不改 `debaters/*-perspective/SKILL.md`，加载方式与护栏另写在
   `debaters/PERSONA_PROTOCOL.md`。
4. **外部 Skill 解耦**：本仓库不内嵌外部 Skill 的实现，只规定「何时/为何/如何调」以及降级路径。
5. **可验证产出**（v3 强化）：契约由机器实测而非模型自报；证据必须有真实出处；过程落盘、可续跑、可导出。
6. **零依赖**：工具与协同台只用 Python 标准库与原生 JS，任何有 `python3` 的 Agent 环境都能直接运行。

---

## 致谢

- 原版仓库：<https://github.com/IsSmallPigPig/Debate-Skill>
- 8 位辩手的人设档案（`debaters/*-perspective/`）来自原作者；
- `Skills/` 下三个第三方 Skill 各自归属其原作者，本仓库仅做集成；
- 历史实录数据来自辩之竹 debatetimer.cn 官方 MCP（公测）。
