---
name: research-vault-ingest-orchestrator
description: "将指定 Zotero 论文入库或完整精读并更新 Obsidian，协调身份、全文、分析、知识决策与校验。"
---

先读活动 Vault 的 WORKFLOW.md。工具根目录为 `{{WORKFLOW_ROOT}}`，Python 使用其中安装依赖的虚拟环境；命令中的 Vault 路径由用户选择。
`workflow.py --vault <Vault绝对路径> <子命令>` 位于工具根目录 tools/。路径参数必须安全引用。

按需读取本 Vault .agents/skills/ 下数据获取、全文归档与分析写作技能，在当前会话顺序执行。
1. 用户未提供 Key 时运行 `workflow.py list --query 关键词`，核对实际题名；多个匹配需要选定。该命令不需要 Vault 参数，不代表 Zotero 当前选中项。
2. 运行 `workflow.py --vault <路径> ingest KEY`。多 PDF 附件显式用 --pdf-key 指定。复用合法全文；INGESTED_NOT_ANALYZED 只表示骨架入库。
3. 根据 skim/deep 要求，读取原文与页面，按 Writer 更新同一笔记；每篇默认 FSMIS 简评。
4. 有跨论文证据或用户要求维护知识时读 knowledge-maintainer；否则记录 NO_KNOWLEDGE_CHANGE，不造空知识页。
5. 运行 validate 与 tools/refresh_index.py --vault <路径>；失败时不宣称完成。仅有内容更新不重新解析 PDF。
以 zotero_key 唯一识别论文，pdf_key 仅标识附件。不自动发现、下载新论文或改写 Zotero 数据。
