# 变更日志

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。每个版本对应一个 annotated tag 与 GitHub Release。

## [1.1.0] - 2026-11-09

对照代码走查结论做的真实性整改：把三处「文档说做了、代码没做」的检查补成真的，并修掉两处会让闭环失效的逻辑缺陷。对外契约只增不改（新增 `TestEvaluation`、`RunTrace.code_sources`、`WorkflowSettings`），端到端三条命令的指标与修复轨迹保持一致。

### 新增

- **确定性实测**：`DatasetSandbox.run(repeat=2)` 在同一子进程内重建并二次 fit，两次连续输出的最大绝对差写入 `SandboxResult` 的 `repeat_variance`；`deterministic` 不再恒为 True。次数由 `workflow.determinism_repeat` 控制。
- **test 段终评**：`DatasetSandbox.run(segment="test")` 改在末段评估；工作流在候选比较结束后对最佳候选消费一次 test，结果写入 `RunTrace.test_evaluation` 与报告第 5 节，不参与排序与修复。开关 `workflow.evaluate_on_test`。
- **Coder 采用 LLM 代码**：真实 LLM 返回的代码先过 AST 静态检查，通过才采用；缺 `build_pipeline`、缺 `FEATURE_COLUMNS`、危险 import 均回退算法模板，原因记入 `RunTrace.code_sources` 与日志。Mock 输出标注为「仅作契约示例」。
- `WorkflowSettings`：`beam_width` / `max_repair_rounds` / `determinism_repeat` / `evaluate_on_test` 全部从 `configs/default.yaml` 读取（此前 `workflow` 段存在但从未被加载）。

### 修复

- **候选族裁剪从未生效**：可用性判断只认 `<task_type>.<family>` 前缀，而表格模板按裸 `<family>` 注册，导致表格场景恒不裁剪、三个候选里两个是 LR。改为两种写法都认，候选现在是 LR / RF / HGB 三种算法（RF AUC 0.7899 成为最佳候选）。
- **沉淀经验只活一轮**：`Curator` 原按 `run_id` 覆盖 `FailureCase`，第二次运行会删掉上一轮学到的 T1 经验。改为按 `error_signature` 复用后，同一 demo 首轮 2 轮修复、次轮 1 轮修复。

### 变更

- **知识图谱边语义**：从「按列表下标轮转」改为「名称或属性文本命中才连边」，主场景 259→188 边、文本场景 33→15 边；`DEPENDS_ON` 按顶层包名匹配（`sklearn.linear_model` → `sklearn`）。
- **失败经验跨轮复用**：`Curator` 对 `FailureCase` 按 `error_signature` 去重，不再随 `run_id` 覆盖删除；只有出现新签名才升级能力版本，版本号按图中 `<anchor>.vN` 递增并形成版本链。
- **Planner 候选**：先按算法族去重再截断到 `beam_width`，避免同族候选占满宽度。
- **检索**：Top-K 命中后做一跳邻域扩展，邻居按边类型加权加分。
- **API**：`CandidateSummary.auc` 改为通用 `metrics` + `primary_metric` / `primary_value`，文本与回归任务的 `/run` 响应不再返回 `null`；新增 `RunResponse.test_metrics`。
- **抽取器**：Dataset 节点的名称、标签、禁入模字段、敏感字段、划分策略改由 `verify_*.yaml` 派生的 `dataset_profile` 提供，不再写死在 `extractor.py`。
- `configs/default.yaml` 的 `project.version` 与包版本对齐。

### 移除

- `requirements.txt` 中的 `streamlit`：全仓零引用，题目「Web 界面、CLI 或 API」三选一已由 CLI + API 满足。

### 测试

- 新增 17 个用例：确定性（正向 + 非确定性检测）、test 段隔离、终评契约、代码来源四条路径、配置生效与缺省回退、API 通用指标、CLI 进程级入口（`--version` / `--check` / `run --help`）、`POST /run` 真实闭环（临时工作区）。全量 143 个用例通过，`ruff check` 全绿。

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
