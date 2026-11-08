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

- 新功能在 feature 分支开发，通过 PR / MR 合并到 `main`；合并时选 **Create a merge commit**，保留分支节点，不要用 Squash。执行细节见下节。
- 禁止 force push `main`，禁止改写已推送的提交。
- 仓库早期的 4 次提交直接落在 `main`（`7844ad8` → `b108259`），按「禁止改写已推送提交」不回溯。

## 协作约定（AI 可自行执行，须遵守规范）

- `git push`、创建 / 切换 / 删除分支、发起 PR / MR、merge、rebase、打 tag、创建 Release 等改变远端状态或分支结构的操作，AI **可自行执行，无需逐次询问**；前提是遵守本文件的全部规范。
- 不可逾越的红线：禁止 force push `main`、禁止改写已推送的提交、提交前核对敏感文件未跟踪、每阶段独立提交、Conventional Commits + 说明「为什么」。
- 若 PR / MR 的创建或合并不具备可用工具或凭据，如实说明并给出待办，**不得声称已完成**。
- 本地操作（`git add` / `git commit`、文件编辑、跑测试、读文件）不受限制。
