---
name: Debate-Skills-Review
version: 2.0.0
description: |
  辩论赛复盘流程。触发词 `/review`。在已经完成一场 `/debate` 之后调用，用于：
  对指定持方发起针对性质询（攻防演练），由被质询方迭代修改稿件，输出新版攻防表与定稿。
---

# Review · 复盘流程

> 前置条件：当前会话已经完整跑完一场 `/debate`，并且 `templates/artifacts_spec.md`
> 要求的稿件文件（一辩稿、二辩稿、三辩自证稿、四辩结辩稿、攻防表…）都已落盘。

---

## 1. 复盘的目标

不是再打一场完整辩论，而是：

1. 由用户选定**被复盘的持方**（默认沿用 `/debate` 时的 `support`）；
2. 对立持方读取**被复盘方的所有公开稿件**，发动针对性质询；
3. 被复盘方在多轮压力测试中迭代修改稿件和攻防表；
4. 默认重复 3 轮复盘；若被复盘方主动放弃或编排器判定收敛，提前结束。

---

## 2. 输入

| 字段 | 说明 | 默认 |
|---|---|---|
| `target_side` | 被复盘的持方（正/反） | 沿用 /debate 时的 `support` |
| `rounds` | 复盘轮数 | 3 |
| `focus` | 重点攻击哪几个论点（可选） | 由对立方自由选择 |

---

## 3. 阶段流（每一轮复盘）

> 每个 Step 右侧的「外部 Skill」标注**该步要主动调用**的第三方 Skill，
> 详情见 `Skills/integration.md` 对应小节。

```text
[Step 1] 信息加载（对立持方做）
  ├─ 读取 target_side 的全部公开稿件：
  │    <target_side>-备赛资料.md
  │    <target_side>-前场整理.md
  │    <target_side>-一辩稿.md / 二辩稿.md / 三辩自证稿.md / 四辩结辩稿.md
  │    <target_side>-攻防表.md
  └─ 外部 Skill: self-improvement
       → 读 .learnings/LEARNINGS.md 中与本辩题/同辩位的历史先验
         （Skills/integration.md §3.4「赛前自动读取」）

[Step 2] 攻击规划（对立持方做，内部讨论）
  ├─ 标出对方最薄弱的 3 个攻击点
  ├─ 为每个攻击点准备 ≥1 个例子 + ≥1 个归谬路径
  ├─ 选定本轮的「主攻辩位」（默认四辩主攻 / 三辩配合）
  └─ 外部 Skill:
      ├─ debate-master       → 用谬误表给每个攻击点贴方法论标签
      │                        （Skills/integration.md §1）
      └─ multi-search-engine → 找对方稿件里**无引证或弱引证**的数据点
                               （Skills/integration.md §2.3「事实核验」）

[Step 3] 集中质询（对话呈现）
  ├─ 由对立持方对 target_side 做集中质询（≥ 2 轮你来我往）
  ├─ 规则沿用 rules/rules_guide.md §3 质询
  └─ target_side 全员需保持口径一致

[Step 4] 被复盘方反思（target_side 内部头脑风暴）
  ├─ 每位辩手依次发言，分析对方今天打出的每一击
  ├─ 承认至少 1 个对方说得对的点
  ├─ 决定：是修改定义/判准 / 增补论点 / 换论证路径 / 加防线
  └─ 外部 Skill: debate-master
       → 用 6 维度模板自查改稿方向（Skills/integration.md §1.2 行 H）

[Step 5] 稿件回写（target_side 落盘）
  ├─ 修改对应的稿件文件（按 templates/artifacts_spec.md 命名）
  ├─ 在攻防表中追加本轮新增的攻防项（含「方法论标签」列）
  └─ 外部 Skill: multi-search-engine
       → 给新增的回应补 ≥1 条新证据（带 URL）

[Step 6] 中场小结（编排器输出）
  ├─ 简短报告：本轮新暴露/修复的问题，进入下一轮 or 提前结束
  └─ 外部 Skill: self-improvement
       → 追加 1 条 LEARNINGS.md（category=best_practice），
         记录「对方今天打出的最强一招 + 我方修复方案」
         （Skills/integration.md §3.4 中段模板）
```

---

## 4. 终止条件

满足任一条即结束：

- 已完成 3 轮（默认）；
- 被复盘方主动表示"已无法继续防守"或"已达到稳态"；
- 编排器观察到连续两轮**没有新的攻防项被追加**（收敛）；
- 用户显式 `/end review`。

---

## 5. 最终交付

复盘结束时强制输出：

1. **修订版稿件**（覆盖原文件，文件名不变）：
   - `<target_side>-一辩稿.md`
   - `<target_side>-二辩稿.md`
   - `<target_side>-三辩自证稿.md`
   - `<target_side>-四辩结辩稿.md`
   - `<target_side>-三质二质询稿.md`
   - `<target_side>-四质一质询稿.md`
2. **完整攻防表**：`<target_side>-攻防表.md`，结构为：

   ```markdown
   | # | 对方攻击点 | 我方回应 | 风险等级 | 备用反击 | 方法论标签 |
   |---|---|---|---|---|---|
   ```
3. **复盘日志**：`<target_side>-复盘日志.md`，按轮记录"对方打了什么 / 我方怎么改"。
4. **`.learnings/` 沉淀**：本次复盘的精华应已在每轮 Step 6 写入；
   复盘结束时再追加一条**汇总 insight**，记录"本辩题最值得记住的 1 个反直觉结论"。
   （Skills/integration.md §3.4 末段）

---

## 6. 失败模式速查

| 症状 | 处理 |
|---|---|
| 对立方质询变成"再打一遍辩论" | 强提醒："这是复盘，只攻不申论" |
| 被复盘方死扛、不承认任何对方说得对 | 在 Step 4 强制要求"必须承认 ≥1 个对方说对的点" |
| 稿件每轮越改越糊（论点漂移） | 锁定一辩的定义和判准，二三四辩的修改不得违反 |
| 攻防表没更新 | Step 5 不允许跳过，否则本轮无效 |
| 外部 Skill 调用失败 | 按 `Skills/integration.md` §6 降级；写 `ERRORS.md` |
