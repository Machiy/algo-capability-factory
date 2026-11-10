---
description: 本项目的 Git 提交与分支规范
alwaysApply: true
enabled: true
---

# Git 提交规范

题目只要求「使用 Git 进行版本控制，提交信息清晰」（开发要求 a）。规则分三层：`题目硬要求` 必须遵守；`本项目约定` 为工程实践；`协作约定` 界定 AI 自行执行 Git 操作的边界。

## 题目硬要求

- 提交信息清晰：使用 Conventional Commits `<type>(<scope>): <简述>`，type 取 `feat` / `fix` / `docs` / `test` / `chore` / `refactor`。
- 提交信息说明「为什么」，不要只写「更新文件」；commit body 补充本阶段设计依据。
- 每个实现阶段一个独立提交，避免一次 `git add .` 塞入大量无关文件，保证提交历史能还原 P0→P5 的演进。
- 提交前确认 `.env`、token、`PLAN.md`、`assets/data/raw/`、`_archive/` 均未被跟踪。

## 本项目约定

- **单人开发阶段直接推 `main`**：题目未要求分支或 PR，独立开发时开分支、发 PR、等合并只增加往返开销，对交付与评分没有帮助。
- 多人协作、需要代码评审或并行开发多条功能线时，再启用 feature 分支 + PR；合并选 **Create a merge commit**，保留分支节点，不要用 Squash。
- 禁止 force push `main`，禁止改写已推送的提交。

## 版本标签（发布动作，必须执行）

题目只要求「Git 版本控制 + 清晰提交信息」，但本项目把「版本可定位」作为交付证据：CHANGELOG 里的每个版本都要能在 Git 上定位到一个不可变提交。

- **触发动作**：每次 `git push origin main` 成功后，**立即执行** `python scripts/tag_release.py`；脚本读取 `factory.__version__`，创建 annotated tag `v<version>` 并推送到 origin。这一步不能省略，也不靠人工记忆。
- **脚本会校验**：工作区干净、`HEAD` 已在 `origin/main`、本地 / 远端同名 tag 不存在；同一版本多次提交时幂等跳过，不重复打 tag。
- **补历史标签**：`python scripts/tag_release.py --version 1.2.0 --target <sha>`，只用于补齐既有版本，不得改写已推送标签。
- **红线**：禁止 force 更新已推送 tag、禁止改写已推送提交、禁止给未推送的提交打 tag；`push` 后未打 tag 视为发布流程未完成。
- 协作约定里「打 tag」这条权限的默认实现方式即本节脚本；若脚本执行失败，必须如实说明并给出待办，不得声称已完成。

## 协作约定（AI 可自行执行，须遵守规范）

- `git push`、创建 / 切换 / 删除分支、发起 PR / MR、merge、rebase、打 tag、创建 Release 等改变远端状态或分支结构的操作，AI **可自行执行，无需逐次询问**；前提是遵守本文件的全部规范。
- 不可逾越的红线：禁止 force push `main`、禁止改写已推送的提交、提交前核对敏感文件未跟踪、每阶段独立提交、Conventional Commits + 说明「为什么」。
- 若 PR / MR 的创建或合并不具备可用工具或凭据，如实说明并给出待办，**不得声称已完成**。
- 本地操作（`git add` / `git commit`、文件编辑、跑测试、读文件）不受限制。
