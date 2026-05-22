# Skills · 第三方依赖目录

本目录保留 v1 仓库就已经依赖的三个第三方 Skill。Debate Skill 在不同阶段会调用它们；
**集成方法、调用时机和具体 Prompt 都写在 `Skills/integration.md`**——
开始一场辩论前，编排器应当先读一遍 `integration.md`。

## 目录速览

| Skill 目录 | 角色 | 谁来调用 |
|---|---|---|
| `debate-master-1.0.0/` | 辩论方法论百科（6 维度、谬误表、攻防口诀） | 编排器 + 辩手子代理 |
| `gpyangyoujun-multi-search-engine-2.1.3/` | 16 引擎元搜索（无需 API key） | 辩手子代理（备赛阶段） |
| `pskoett-self-improving-agent-3.0.21/` | 跨会话学习/错误/改进沉淀到 `.learnings/` | 编排器（阶段 H/I + 复盘） |

## 三个 skill 与 Debate-Skill 的关系

```text
Debate-Skill v2 (本仓库)
    │
    ├── 引用 → debate-master           ← 当辩手 / 编排器需要"基础方法论"时查
    ├── 引用 → multi-search-engine     ← 当辩手需要"事实/数据/案例"时查
    └── 引用 → self-improving-agent    ← 当一局结束 / 复盘后需要"沉淀经验"时写
```

> 这三个 skill 是**外部依赖**，本仓库不维护它们的实现，只规定**怎么用**。
> 如果当前环境没装它们，按 `../SKILL.md §2` 的安装指引装。
> `self-improving-agent` 是 v2 新引入的依赖，安装方法见 `integration.md §3.3`。
