# 文献笔记数据约定

基本字段：`type: literature-note`、`title`、`aliases`、`tags`、`created`、`source`、`author`、`year`、`theme`、`study_area`、`data_source`、`methodology`、`core_variable`、`key_finding`、`relevance`。

兼容身份：`zotero_key`（父条目）、`pdf_key`（附件）、`doi`、`collection`、`note_path`、`fulltext_path`、`zotero_item`、`zotero_pdf`。路径是相对 Vault 的字符串；URI 使用实际条目 Key。不要把题名当作唯一身份。

| 字段 | 允许值 |
|---|---|
| schema_version | `"2.0"` |
| paper_domain | fsmis / medical_segmentation / general_cv / survey_benchmark / other |
| analysis_modules | 前四种领域值的列表，可叠加 |
| method_tags | 字符串列表 |
| reading_status | inbox / skimmed / reading / deep_read / reported |
| reading_level | skim / deep |
| fsmis_relevance | high / potential / low / uncertain |
| transfer_mode | brief / deep |

`study_area` 是研究任务、对象和应用场景，`core_variable` 是核心机制、概念或指标。字段未知时不补造；入库骨架与完成精读应保持不同状态。

自动更新允许写入上述分析摘要字段及领域、标签、阅读状态、迁移判断；不允许通过 update 修改身份、题名、来源、路径与人工区。更换附件或修复元数据应另外审查。

正文固定为 00–10 节；00–09 在 `AUTO:BEGIN/END` 注释之间，10 在 `HUMAN:BEGIN/END` 之间。保留标记顺序，避免重叠。更新会保留自动区之外的正文，并重写 YAML 的格式。

全文类型为 `literature-fulltext`，有相同的身份和双向路径，额外记录 `source_sha256`、`page_count`、`source_type`、`page_mapping: physical_pdf_1_based`。文本和图片的存在性检查不能代替公式、页码语义与论文结论核验。
