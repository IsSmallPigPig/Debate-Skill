# 辩论协同台 · Debate Collab

> Debate-Skills v3 的协同脚手架：**把 Agent 的输出变成网页**，能**导出文档**，能**复制原文位置向 Agent 提问**。
> 纯 Python 标准库 + 原生 JS，零依赖、零构建，`python3` 一条命令启动。


## 快速开始

```bash
cd Debate-Skill

# 1) 先看示例会话（速通赛进行到第 3 轮，含真实检索数据与两条协同问答）
python3 collab/server.py --root collab/demo
# 打开 http://localhost:8765

# 2) 实战：让 Agent 以 output=web 跑 /debate，然后监听它的输出目录
python3 collab/server.py --root debate-output
```

常用参数：`--port 8765`、`--host 127.0.0.1`（仅本机）、`--verbose`（打印请求日志）。
`--root` 可以指向「包含多个会话的目录」，也可以直接指向某一个会话目录。

## 三大能力

### ① 实时展示 Agent 的输出

- 左侧按赛程（A 开赛 → B 赛前 → C/D/E 主战 → F 自由辩 → G 结辩 → H 评委与赛后 → I 总结）列出**当前预设的全部步骤**：
  ✓ 已完成 / ! 未通过校验 / ● 进行中 / ○ 未开始，并显示「实测字数 / 下限」。
- 中间逐段渲染：发言人标签按正方（绛红）/ 反方（藏蓝）着色；每段左侧有锚点 ¶N。
- 每个环节顶部显示**机器校验**结果（字数、回合、质询方字数、打岔、交替、动作括号、占位符、URL），
  问题段落左侧有红/黄点，点「¶N」直接跳到对应段落。
- 每 1.5 秒同步一次：Agent 新写入或重写的段落会高亮闪烁；勾选「跟随直播」后自动跳到最新写入的环节。
- 顶部搜索（按 `/` 聚焦）可在全场发言里查找。

### ② 导出文档

右上角「导出」或文档顶部按钮：

| 范围 | 格式 |
|---|---|
| 当前文档 | Word（.docx）· Markdown · HTML · 打印 / 另存为 PDF |
| 整场实录（按赛程顺序汇编，含封面信息表、证据台账附录） | Word · Markdown · HTML |
| 全部稿件 | ZIP（整场实录 docx+md、每份稿件 docx+md、逐轮实录 docx、证据台账） |

选项：清理契约行 / 编排器提炼（默认开）、附 AI 模拟声明（默认开）、附协同问答（默认关）。
命令行同样可导出：`python3 tools/debate_ctl.py export <session> --doc all --format docx`。

### ③ 复制原文位置，向 Agent 提问

| 操作 | 效果 |
|---|---|
| 悬停段落 → **⧉ 复制位置** | 把该段的【辩论协同·提问】复制到剪贴板，粘贴到 Agent 对话框，写上问题即可 |
| 选中一句话 → **复制位置并提问** | 引用精确到你选中的句子 |
| 悬停段落 → **＋ 引用** | 加入右侧「引用篮」，可跨环节多选（例如对比 R02 与 R08 是否矛盾） |
| 右侧面板 | 选择**提问对象**（教练 / 原辩手 / 对方辩手 / 评委）与**意图**（解释 / 反驳 / 补强 / 核验事实 / 改写） |
| **复制提问** | 把所有引用 + 问题一起复制，粘贴给 Agent |
| **加入待答队列** | 不用切窗口：问题写入 `qa/threads.jsonl`，之后在对话里输入 `/ask` 一次处理全部 |

剪贴板内容示例：

```text
【辩论协同·提问】
会话：年轻人该不该回老家发展（20261015-2030-回老家发展）
提问对象：教练（跳出角色）｜意图：补强

[1] debate://20261015-2030-回老家发展/R02#b10
    位置：第 2 轮 · 质询｜反方四辩 → 正方一辩 › ¶10 · 正方一辩 · 胡渐彪
    原文：「我方不说他错，我方说这样的选择对普通年轻人来说风险更高。…」

问题：正一这里是不是答软了？有没有更好的接法？
（Agent：请按 Debate-Skill collab/PROTOCOL.md §3 处理——先用 tools/debate_ctl.py locate 定位原文，再回答，最后用 ask new 回写 qa/threads.jsonl）
```

Agent 收到后用 `tools/debate_ctl.py locate` 定位（**以原文为准**，即使文件被改写导致段落编号漂移也能找回），
按对象与意图作答，再用 `ask new` / `ask answer` 回写——答案会自动出现在网页里对应段落的下方。

## 目录

```text
collab/
├── server.py        # 标准库 HTTP 服务（只用相对 URL，可放在反向代理/预览域名后）
├── web/             # index.html · app.css · app.js（无外部资源，离线可用）
├── PROTOCOL.md      # Agent 侧协议：落盘、续跑、定位提问、回写、导出
├── README.md        # 本文件
└── demo/            # 示例会话
tools/
├── debate_ctl.py    # init / next / step / status / lint / locate / ask / export / budget
├── debatetimer.py   # debatetimer.cn 官方 MCP 命令行客户端
└── debatekit/       # 共享核心：分块与锚点、预设、会话、校验、定位、docx 写出、导出
```

## 接口（供二次开发）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `api/sessions` | 会话列表 + 摘要 |
| GET | `api/session?id=` | 摘要、按预设展开的步骤（含状态与校验）、文档列表、问答 |
| GET | `api/doc?id=&key=` | 分块（html/纯文本/发言人）、校验结果、该文档的问答 |
| GET | `api/version?id=` | 目录指纹（前端据此轮询刷新） |
| GET | `api/search?id=&q=` | 全场搜索 |
| GET | `api/export?id=&key=&fmt=docx\|md\|html\|zip&clean=&qa=&disclaimer=` | 导出下载；`key=__all__` 为整场 |
| POST | `api/threads?id=` | 加入待答队列 `{refs, intent, target, question}` |

## 常见问题

- **复制没反应？** 非 HTTPS 的局域网地址下浏览器可能禁用剪贴板 API，协同台会自动降级；仍失败时会弹出可手动复制的文本框。
- **段落编号变了，旧问答还对得上吗？** 问答按「原文」重新挂载到最匹配的段落，编号只作辅助。
- **能多人同时看吗？** 可以，任何能访问该端口的浏览器都能实时看到同一场辩论，并各自提问入队。
