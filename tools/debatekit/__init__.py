"""debatekit · Debate-Skills v3 的纯标准库工具包。

模块：
- mdblocks   Markdown → 带稳定锚点的块（网页 / 定位 / lint / 导出 共用同一份切分逻辑）
- presets    读取 rules/presets.json（单一事实来源）
- session    会话目录模型（session.json / transcript / artifacts / qa）
- lint       机器校验完成契约（实测字数、动作括号、占位符、回合数……）
- refs       「定位引用」的生成与解析（debate://<session>/<doc>#b<N>）
- docx       纯标准库 .docx 写出器（中文字体、表格、页码）
- export     清理导出（md / html / docx / zip）

只依赖 Python 3.8+ 标准库。
"""

__version__ = "3.0.0"
