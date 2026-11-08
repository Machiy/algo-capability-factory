---
description: 本项目的 Git 提交与分支规范
alwaysApply: true
enabled: true
---

# Git 提交规范

题目只要求「使用 Git 进行版本控制，提交信息清晰」（开发要求 a）。规则分三层：`题目硬要求` 必须遵守；`本项目约定` 为自定工程实践，可按实际调整；`协作约定` 约束 AI 执行 Git 操作前的确认流程。

## 题目硬要求

- 提交信息清晰：使用 Conventional Commits `<type>(<scope>): <简述>`，type 取 `feat` / `fix` / `docs` / `test` / `chore` / `refactor`。
- 提交信息说明「为什么」，不要只写「更新文件」；commit body 补充本阶段设计依据。
- 每个实现阶段一个独立提交，避免一次 `git add .` 塞入大量无关文件，保证提交历史能还原 P0→P5 的演进。
- 提交前确认 `.env`、token、`PLAN.md`、`assets/data/raw/`、`_archive/` 均未被跟踪。

## 本项目约定（建议）

- 较大的功能改动建议在 feature 分支开发，通过 PR 合并到 `main`；合并时选 **Create a merge commit**，保留分支节点，不要用 Squash。
- 禁止 force push `main`，禁止改写已推送的提交。
- 仓库已有 4 次提交直接落在 `main`（`7844ad8` → `b108259`），按「禁止改写已推送提交」不回溯；自 P1 起对新功能按上述建议开分支。

## 协作约定（AI 执行前须逐次确认）

- 任何改变远端状态或分支结构的操作 —— `git push`、创建 / 切换 / 删除分支、发起 PR / MR、merge、rebase、打 tag、创建 Release、改写已推送提交 —— 执行前必须先说明将做什么并取得用户明确同意。
- 即使判断为「规范流程所必需」，或用户此前曾授权过同类操作，也必须**逐次询问**；一次性授权不累积、不延伸到下一次。
- 本地操作（`git add` / `git commit`、文件编辑、跑测试、读文件）不受本条约束。
- 与「本项目约定（建议）」的关系：feature 分支 + PR 仍是建议做法，是否采用由用户逐次决定，不由 AI 自行发起。
