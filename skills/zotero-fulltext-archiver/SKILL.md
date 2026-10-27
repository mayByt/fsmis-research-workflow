---
name: zotero-fulltext-archiver
description: "长期归档 Zotero 逐页全文，按需渲染缓存页面并精选保留图表；校验身份和迁移旧图片。"
---

先读活动 Vault 的 WORKFLOW.md。工具根目录为 `{{WORKFLOW_ROOT}}`，Python 使用其中安装依赖的虚拟环境；命令中的 Vault 路径由用户选择。
`workflow.py --vault <Vault绝对路径> <子命令>` 位于工具根目录 tools/。路径参数必须安全引用。

全文文本长期保留，PNG 按需生成；原 PDF 始终由 Zotero 管理且只读。`ingest KEY` 在 `03fulltext/<collection>/<zotero_key>.md` 保留逐页文本、物理页号、Zotero 页面链接、附件身份及源 SHA-256，不预渲染全部页面。低文本/扫描页停止并报告 OCR 待处理，不以摘要冒充全文。

核验图、公式、表格时用 `render KEY --pages 3,5-7`，只生成指定的物理 PDF 页，返回缓存绝对路径；必须实际查看图片才能声称完成视觉核验。缓存位于 `_staging/page-cache/<key>/<source_sha256>/page-XXX.png`，使用时更新修改时间；渲染会核对当前 Zotero PDF 身份、SHA-256 和页数，源变化时停止。文本提取不恢复 LaTeX，也不等于排版准确。

需要在笔记或组会中长期嵌入的图，先用 `render KEY --pages 3 --keep` 提升为精选页面。精选图保存在全文同目录 `images/<key>/page-003.png`，登记 `retained_pages`，并在全文建立稳定图片链接；笔记只嵌入该长期路径，不嵌入临时缓存。页面是原 PDF 整页，工具不自动裁剪单张 Figure。已有被笔记引用的旧图片保留原路径。

`cache-prune --days 30` 仅预览，增加 `--apply` 才清理超过 30 天未使用的缓存；不会删除精选图和被 Vault 笔记引用的缓存。不自动定时清理，不顺手清空缓存；用户要求清理时再执行。缓存缺失不影响全文有效性；精选图或实际链接缺失必须报错。

旧归档用 `migrate-images` 预览，用户要求迁移后再 `migrate-images --apply --backup-dir <备份目录>`。先创建包含原始全文和 PNG 的 ZIP，扫描全 Vault 的图片引用，保留被引用页面的原位置；其余旧自动页面嵌入移除，图片转入缓存。迁移不改论文笔记、人工区、逐页原文文本、身份或 PDF；失败时回滚。迁移期间避免其他编辑器同时写入。不要手动批量删除 images/。旧全页归档仍可校验，未迁移前不能用 --keep 改写其布局。

有效全文按身份及散列复用；模板更新不触发转换。完成时检查连续物理页号、稳定身份、Note/Fulltext 双向路径和所有持久图片链接；不再要求 PNG 数量等于页数。原文 PDF 内容变化时停止自动覆盖，须明确刷新并审查差异。
