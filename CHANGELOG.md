# 变更日志

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。每个版本对应一个 annotated tag 与 GitHub Release。

## [1.0.1] - 2026-11-09

### 变更

- CI 改为**固定双版本并行**（Python 3.11 + 3.12），去掉按事件分流的条件表达式：
  单人开发、直推 `main`、无高频 PR，规则越简单越好读；`3.11` 对应 `requires-python` 声明，
  `3.12` 对应本地实测版本。
- job 名与安装步骤直接显示 Python 版本，watch 页面无需展开日志即可区分两轮。

### 修复

- 恢复 `5a7c484` 中被 `3e47666` 误覆盖的 matrix 表达式（定位替换时连带回滚了相邻改动）。

## [1.0.0] - 2026-11-09

首个完整交付版本，覆盖题目任务 1–6、流程 a–g、开发要求 a–g、基础交付 11 项、进阶要求 8 项与加分项 10 项。

### 新增

- 六层架构（contracts / knowledge / agents / runtime / validation / 接入层）与 Pydantic 契约先行。
- 能力知识图谱：9 类节点 / 13 类关系，NetworkX + SQLite，JSON / CSV / GraphML / PyVis 四种交付形态；
  支持按场景拆分子图（主场景 95 节点 / 259 边，文本子图 17 / 33）。
- 8 个 Agent 角色 + LangGraph 状态机，Beam Top-3 候选、≤3 轮定向修复、失败经验回写。
- 四层验证（接口 / 功能 / 指标 / 稳定性）、子进程沙箱、AST 导入白名单、指标插件与算法模板插件。
- 三种 LLM 后端（Mock / OpenAI 兼容 / cassette 回放），脱敏录制 2 次真实 DeepSeek 调用。
- 三类任务端到端：信用卡违约二分类（AUC 0.78434）、短信垃圾文本分类（accuracy 0.98027）、
  需求量回归（RMSE 19.31，`direction: minimize`）。
- 真实开源仓库 `scorecardpy` 的 AST 抽取（79 个公开能力）与 10× 资源消耗基准。
- 接入层：Typer CLI、FastAPI（`/health`、`/templates`、`/run`）与导出的 OpenAPI 文档。
- GitHub Actions CI（Python 3.11 / 3.12：lint + 128 用例 + 三条端到端）、5 分钟验收路径、交付物索引（README 附录 E）。

### 修复

- Windows 下 venv `python.exe` 为 redirector，内存看门狗只读父进程 RSS（恒 4MB）导致上限失效；
  改为对整棵进程树求和并超限终止。
- 候选打分默认「越大越好」，主指标为 RMSE 时会把最差候选排第一；改为按 `direction` 归一。
- 失败签名正则漏掉 `MetricBelowThreshold`，导致相关 `FailureCase` 记为「未知签名」。
- `scripts/download_data.py` 带 shebang 但索引模式为 100644，触发 ruff `EXE001`（仅 POSIX 可见）。
- README 存在过时阶段描述、模块清单与实测数字冲突，已按实测逐条回填。
