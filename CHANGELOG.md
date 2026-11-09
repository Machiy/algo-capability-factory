# 变更日志

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。每个版本对应一个 annotated tag 与 GitHub Release。

## [1.0.2] - 2026-11-09

评审视角代码走查后的健壮性修复，不改架构与对外契约。

### 修复

- **`run_id` 路径穿越**：`run_id` 原样拼进 `run_<id>.md` / `trace_<id>.json`，
  API 传 `../../x` 可写出产物目录。现在接口层用 Pydantic pattern + `..` 校验挡成 422，
  工作流入口再兜一道（非法标识返回退出码 2），两层都不产生任何落盘。
- **API 无错误处理**：`/run` 抛异常时只有裸 500。现在调用方错误（数据缺失 / 配置非法 /
  标识不合法）回 400 并带可读原因，其余异常回 500 且只暴露异常类型，堆栈进日志。
- **OpenAPI 版本号硬编码**：`FastAPI(version="0.1.0")` 与包版本脱节，改为读取
  `factory.__version__`，并加测试断言两者一致。
- **CLI 直接抛堆栈**：`factory run` 遇到数据缺失 / 非法标识时打印 traceback；
  现在给出可读错误并以退出码 2 结束。

### 变更

- **日志初始化统一**：`build_kg.py`、`build_text_kg.py` 由各自的 `logging.basicConfig`
  改为 `configure_logging()`，所有入口的日志格式一致。
- **错误签名泛化**：沙箱不再只识别 `KeyError: PAY_1`，而是统一归一为 `KeyError: <列名>`
  （同时兼容 pandas 的 `KeyError: "['X'] not in index"` 与字典的 `KeyError: 'x'`），
  换数据集后同样的修复策略仍可命中。

### 移除

- `factory/agents/roles.py` 中未被引用的 `CODE_TEMPLATE` 常量（模板已由注册表按
  `task_type` + `model_family` 解析）。

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
