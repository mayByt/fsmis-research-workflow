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

## 本机 API 连接与宿主审批

先用 `workflow.py doctor` 做只读诊断（不需要 Vault 参数）。若返回 `LOCAL_API_PERMISSION_DENIED`、`retry_with_permission: true`，或原始错误为 EPERM/EACCES（Operation not permitted/Permission denied），说明连接在收到 HTTP 响应前被权限策略拒绝，不能据此判断 Zotero 通信选项有误。

对用户已要求的本机读取，使用当前宿主提供的审批机制，重新执行同一命令一次；在提供 exec_command 的环境中使用 `sandbox_permissions: "require_escalated"`，理由限定为读取 Zotero 的 localhost:23119。不要只在原沙箱重复重试，不要改全局网络或审批配置，也不要改用其他传输方式规避同一拒绝。

审批被拒绝、环境禁止提权或已授权重试仍失败时，停止依赖 API 的阶段，报告实际审批/连接结果；可提供普通系统终端中的 doctor 命令供用户诊断。不能声称已读取论文或完成入库。HTTP 403、连接被拒绝和超时分别按 error_code 处理，不能都归为沙箱拒绝。


## 页面图像的按需核验

逐页全文文本长期保留，PNG 不再全量常驻。需要核验 Figure、公式或表格时，按 zotero-fulltext-archiver 使用 `render KEY --pages <物理页>` 并实际查看返回图片。要在笔记中嵌入图片，先加 `--keep` 保存为精选图，再使用返回的 `03fulltext/.../images/<key>/page-XXX.png` 稳定路径；不要链接 `_staging/page-cache/`。旧笔记已引用图保留原位置。PNG 缓存缺失无需重建整篇全文；源 PDF 变化则停止复用并报告。全文无需每页都有 PNG，校验仍须检查所有精选图及实际链接。
