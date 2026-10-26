---
name: research-vault-literature-retrieval
description: "检索本 Vault 论文、比较方法或回答证据问题；先笔记定位，再到全文和原 PDF 核验。"
---

先读活动 Vault 的 WORKFLOW.md。工具根目录为 `{{WORKFLOW_ROOT}}`，Python 使用其中安装依赖的虚拟环境；命令中的 Vault 路径由用户选择。
`workflow.py --vault <Vault绝对路径> <子命令>` 位于工具根目录 tools/。路径参数必须安全引用。

先检查 Vault/02vault 的题名、主题、领域、方法标签和正文，使用 rg 等本地工具筛选真实候选；读取相关笔记，不能仅靠相似标题答题。
对关键结论、公式、数值和适用条件，追踪笔记 fulltext_path，再定位 PDF 页、Figure、Equation、Table。必要时检查页面图像；区分笔记解释和原文报告。
跨论文比较先核对任务、数据划分、标注预算、预训练、指标与汇总单位；协议不一致时避免直接排名。列明覆盖的论文及缺失证据，不能把未找到当作不存在。
答案引用真实笔记/全文路径或 Zotero 物理页链接。没有证据时说明不确定；未经用户要求不拓展为互联网调研。检索本身不改写笔记或创建知识页。
