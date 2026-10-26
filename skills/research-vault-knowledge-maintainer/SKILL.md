---
name: research-vault-knowledge-maintainer
description: "依据多篇已有精读笔记和原文，维护 Vault 的跨论文主题、方法对比、证据与争议。"
---

先读活动 Vault 的 WORKFLOW.md。工具根目录为 `{{WORKFLOW_ROOT}}`，Python 使用其中安装依赖的虚拟环境；命令中的 Vault 路径由用户选择。
`workflow.py --vault <Vault绝对路径> <子命令>` 位于工具根目录 tools/。路径参数必须安全引用。

先读 Vault/01knowledge 现有页面及其格式；更新相关页优先。若已有固定 Schema、元数据或 sidecar，遵循既有约定，本技能不重写它们。
每条拟沉淀的主张先用笔记定位，再以相应全文/页面核验机制、结果、条件与反例；单篇摘要不能升级为跨论文共识。未经核验的解释标为解释或待核验。
没有现成结构时，使用来源覆盖、可核验主张、适用条件、冲突/缺口与真实论文链接组织简洁页面。新页必须提供独立于单篇摘要的检索或综合价值。
用户个人批注与人工结论保留；写入前备份，定向更新，不批量重排整个 Vault。不满足证据条件时返回 NO_KNOWLEDGE_CHANGE。
本包不包含第三方 Knowledge Schema 或校验器。若活动 Vault 有专用校验器，按其说明运行；否则明确仅完成来源存在性与内容核对，不能宣称通过未运行的 Schema 校验。
