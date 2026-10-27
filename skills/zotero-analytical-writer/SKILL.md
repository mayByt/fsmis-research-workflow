---
name: zotero-analytical-writer
description: "使用通用 V2 模板和领域模块精读 FSMIS、医学分割、通用 CV 或综述论文，默认给出简短迁移判断。"
---

先读活动 Vault 的 WORKFLOW.md。工具根目录为 `{{WORKFLOW_ROOT}}`，Python 使用其中安装依赖的虚拟环境；命令中的 Vault 路径由用户选择。
`workflow.py --vault <Vault绝对路径> <子命令>` 位于工具根目录 tools/。路径参数必须安全引用。

先读 Vault/模板/论文精读模板.md、已有笔记与全文。按原论文判定 paper_domain 和可叠加的 analysis_modules；只读对应领域模块，不把所有文献强行归 FSMIS。
初筛完成研究问题、贡献、方法、核心证据和短评；未精读部分明确标记。深读重点逐 Figure/Module 解释动机、输入输出与尺寸、计算步骤、公式、区别、消融依据和讲解顺序。
原文事实、解释、假设分清；公式符号、图表数字回看页面。原文未报告则写未报告，不从领域惯例补造。页码使用物理 PDF 页，必要时注明印刷页差异。
保留 00–10 章节。study_area 表示任务/对象/场景，core_variable 表示机制/概念/指标。身份、路径、URI 不随标题改变。
00–09 为 AUTO 区；把新内容保存到临时 Markdown（无保护标记），元数据为 JSON，用 update KEY --body <文件> --metadata <文件> 更新。第 10 节及其他人工区域不可覆盖。工具会备份；保护标记缺失或顺序异常先审查迁移。
阅读完才将 reading_status 设为 skimmed 或 deep_read，reading_level 对应 skim 或 deep；深读不是训练复现。
第 08 节始终短评：high/potential/low/uncertain、来源机制、FSMIS 对应问题、障碍和依据。普通阅读 transfer_mode=brief；只有明确要求创新设计才读取 fsmis-idea-lab 并保存 Idea。


## 页面图像的按需核验

逐页全文文本长期保留，PNG 不再全量常驻。需要核验 Figure、公式或表格时，按 zotero-fulltext-archiver 使用 `render KEY --pages <物理页>` 并实际查看返回图片。要在笔记中嵌入图片，先加 `--keep` 保存为精选图，再使用返回的 `03fulltext/.../images/<key>/page-XXX.png` 稳定路径；不要链接 `_staging/page-cache/`。旧笔记已引用图保留原位置。PNG 缓存缺失无需重建整篇全文；源 PDF 变化则停止复用并报告。全文无需每页都有 PNG，校验仍须检查所有精选图及实际链接。
