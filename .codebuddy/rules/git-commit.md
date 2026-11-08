---
description: 本项目的 Git 提交与分支规范
alwaysApply: true
enabled: true
---

# Git 提交规范

- 使用 Conventional Commits：`<type>(<scope>): <简述>`，type 取 `feat` / `fix` / `docs` / `test` / `chore` / `refactor`。
- 提交信息说明「为什么」，不要只写「更新文件」。
- 每个实现阶段一个独立提交，避免一次 `git add .` 塞入大量无关文件。
- 新功能在 feature 分支开发，通过 PR 合并到 `main`；合并时选 **Create a merge commit**，保留分支节点，不要用 Squash。
- 禁止 force push `main`，禁止改写已推送的提交。
- 提交前确认 `.env`、token、`PLAN.md`、`assets/data/raw/`、`_archive/` 均未被跟踪。
