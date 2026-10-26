---
name: zotero-fulltext-archiver
description: "将指定 Zotero PDF 归档为有物理页码和完整页面图像的 Markdown，校验身份并复用已有全文。"
---

先读活动 Vault 的 WORKFLOW.md。工具根目录为 `{{WORKFLOW_ROOT}}`，Python 使用其中安装依赖的虚拟环境；命令中的 Vault 路径由用户选择。
`workflow.py --vault <Vault绝对路径> <子命令>` 位于工具根目录 tools/。路径参数必须安全引用。

使用 ingest 命令；原 PDF 只读。归档到 03fulltext/<collection>/<zotero_key>.md，记录源 SHA-256；图片在同目录 images/<key>/。
pypdf 保留逐页提取文本，pypdfium2 渲染每个 PDF 页面；不会自动 OCR 或恢复 LaTeX。复杂公式、表格和图需查看原页面。
低文本/扫描页停止，不能用摘要替代全文。源文件变化、附件变化或双向链接损坏时停止自动覆盖，并报告需要审查的对象。
有效全文和图片可复用；换模板不重新转换。完成需检查页数、图像、稳定身份与 Note/Fulltext 双向路径。
