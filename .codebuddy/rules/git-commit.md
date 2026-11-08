---
description: 本项目的 Git 提交与分支规范
alwaysApply: true
enabled: true
---

# Git 提交规范

题目只要求「使用 Git 进行版本控制，提交信息清晰」（开发要求 a）。下列 `题目硬要求` 必须遵守，`本项目约定` 为自定工程实践，可按实际调整。

## 题目硬要求

- 提交信息清晰：使用 Conventional Commits `<type>(<scope>): <简述>`，type 取 `feat` / `fix` / `docs` / `test` / `chore` / `refactor`。
- 提交信息说明「为什么」，不要只写「更新文件」；commit body 补充本阶段设计依据。
- 每个实现阶段一个独立提交，避免一次 `git add .` 塞入大量无关文件，保证提交历史能还原 P0→P5 的演进。
- 提交前确认 `.env`、token、`PLAN.md`、`assets/data/raw/`、`_archive/` 均未被跟踪。

## 本项目约定（建议）

- 较大的功能改动建议在 feature 分支开发，通过 PR 合并到 `main`；合并时选 **Create a merge commit**，保留分支节点，不要用 Squash。
- 禁止 force push `main`，禁止改写已推送的提交。
- 仓库已有 4 次提交直接落在 `main`（`7844ad8` → `b108259`），按「禁止改写已推送提交」不回溯；自 P1 起对新功能按上述建议开分支。
