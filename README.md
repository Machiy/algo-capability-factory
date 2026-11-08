# AlgoCap Factory · 基于 AI Agent 的算法能力工厂

> 面向「信用卡客户下月违约预测」场景，实现从自然语言能力描述到可运行算法代码的端到端半自主生成，并跑通 **能力抽取 → 能力复刻 → 能力验证 → 能力沉淀** 完整闭环。
>
> 对应题目：LLM Agent 笔试《基于 AI Agent 的算法能力系统开发》。

**当前仓库状态：a–g 七步核心闭环已跑通（P0–P3）。** 已实现 L0 契约、L1 能力图谱与混合检索、L2 的 8 个 Agent 角色与工作流编排、L3 子进程沙箱与 AST 静态检查、L4 四层验证与报告生成，以及三种 LLM 后端和脱敏 cassette；`python -m factory run --spec "..." --mock` 一次产出生成代码、四层报告、修复轨迹与图谱回写。指标层因 baseline 级候选未达业务门槛如实判 FAIL，见第 8 节；P4 消融对比与 P5 Web / API 界面属后续阶段。本文档已按题目「提交方式」要求的十项内容写好。

---

## 核心闭环

```
自然语言能力描述
   ↓ a 理解                 Interpreter → CapabilitySpec
   ↓ b 检索                 Retriever  → 能力子图 / 约束 / 历史失败经验
   ↓ c 规划                 Planner    → Beam Top-3 候选方案
   ↓ d 生成                 Coder      → 可运行代码（build_pipeline 契约）
   ↓ e 验证                 Verifier   → 四层验证（接口 / 功能 / 指标 / 稳定性）
   ↓ f 修复                 Repairer   → 错误签名定向修复，最多 3 轮
   ↓ g 沉淀                 Curator    → 回写 ValidationRun / FailureCase / 能力 v+1
                              ↓
                     验证报告 + 候选排名 + 设计依据 + 图谱 diff
```

**快速开始（P5 完成后可用）**

```bash
pip install -r requirements.txt
python scripts/download_data.py            # 首次可选；仓库已内置 CC0 / CC BY 数据
python -m factory run --spec "预测信用卡客户下月违约概率，处理异常类别与类别不平衡，按5:1成本比选阈值，禁止时间泄漏，输出AUC/KS/成本加权损失" --mock
```

`--mock` 使用内置规则模板 LLM，全程离线可跑；去掉该参数并配置 `.env` 即可切换真实 LLM。

---

## 1. 项目背景和目标

真实行业中的算法能力往往分散在业务文档、历史代码仓库、专家经验、实验记录和测试报告中，包括数据预处理方法、模型选择经验、特征工程策略、评价指标、失败案例、调参经验与业务约束。本项目构建一个小型「算法能力工厂」原型，把这些能力自动抽取为结构化知识并沉淀到能力图谱，再由多智能体协作完成算法复刻与自动验证。

**目标**：

1. 验证「能力抽取 — 能力复刻 — 能力验证 — 能力沉淀」核心闭环，而非仅做一次性代码生成；
2. 让知识图谱**真实参与**检索、规划、生成与验证，而非静态展示；
3. 让验证结果**驱动**定向修复，并让失败经验**回写**后可在下一轮被检索命中；
4. 在断网、无本地大模型、无 GPU、无 API key 的环境中完整复现端到端运行（默认 `MockLLM` + 脱敏 cassette 回放）。

**场景选择**：信用卡客户下月违约预测。原题第 12 行的场景列表为开放式举例（「例如……等」），本场景合规。选它的原因是业务约束丰富（成本矩阵、合规、群体稳定性、公平性）、指标族完整、数据集自带真实数据质量陷阱，可产生无需人为埋 bug 的真实失败修复轨迹。

---

## 2. 系统架构和模块设计

| 层 | 模块 | 职责 |
|---|---|---|
| L0 契约 | `contracts/` | `CapabilitySpec`、`CandidatePlan`、`ValidationReport`（Pydantic），全系统唯一数据协议 |
| L1 知识 | `knowledge/` | Schema、抽取器、NetworkX 图 + SQLite 持久化、混合检索器、PyVis 可视化 |
| L2 Agent | `agents/`、`workflow/` | 8 个角色、LangGraph 状态机、Beam Search、修复策略表 |
| L2 支撑 | `llm/` | `BaseLLM` 抽象与三个实现：`MockLLM`（默认）、`OpenAICompatLLM`（DeepSeek API）、`RecordedLLM`（cassette 回放） |
| L3 执行 | `runtime/` | 子进程沙箱、AST 静态检查、超时 / 内存限制、错误分类器 |
| L4 验证 | `validation/` | 四层检查器、指标插件注册、报告生成 |
| L5 接入 | `cli/`、`api/`、`ui/` | Typer CLI、FastAPI、Streamlit |
| L6 资产 | `assets/` | 数据、6 份业务材料、模板、示例、报告样例与 LLM cassette |

**设计原则**：契约先行（所有模块只依赖 Pydantic 数据类）、LLM 可替换（抽象 `BaseLLM`）、验证与场景解耦（换 yaml 即换任务类型）、执行与验证隔离（生成代码只在子进程沙箱内运行）。

**技术选型与理由**（对应开发要求 f；末列记录「先查现成库」的评估结论）

| 组件 | 选择 | 理由 | 评估过的现成方案 / 未采用原因 |
|---|---|---|---|
| LLM | `BaseLLM` 抽象：`MockLLM` / `OpenAICompatLLM`（DeepSeek OpenAI 兼容接口）/ `RecordedLLM`（cassette 回放） | 默认 mock 保证断网复现；本地 CPU 跑开源模型过慢，按开发要求 g 的「API 调用方式」接 DeepSeek 满足任务 1；真实响应脱敏录制后可在无 key 环境回放，三种实现只切 `llm.provider` | LangChain / LlamaIndex 的 LLM 包装：只需一行配置切换，不必引入整套链路；`openai` SDK 已直接使用 |
| 编排 | **LangGraph `StateGraph`**（节点 + 条件边表达修复循环与候选循环） | 条件边、状态传递与循环上限由框架提供；8 个角色作为节点动作，`RunTrace` 仍是唯一输出契约 | 曾自研轻量状态机，按「有现成的不要重复造轮子」已替换；AutoGen / CrewAI 评估过：其 `Agent` / `Task` 抽象会接管 LLM 调用链，破坏「检索证据显式进 prompt」与 `MockLLM` 默认路径 |
| 多智能体角色 | 8 个角色类 + Pydantic IO 契约，由 LangGraph 节点编排 | 角色职责、prompt 与错误签名策略是项目业务规则，框架不提供 | CrewAI / AutoGen：见上，重依赖且接管调用链 |
| 知识图谱 | NetworkX（GraphML）+ SQLite | 零部署、可直接交付 GraphML / CSV | Neo4j：需 Docker，伤「本地一键复现」 |
| 检索 | `rank_bm25.BM25Okapi` + 图邻域扩展 + 元信息打分 | BM25 相关性由现成库计算，权重来自 `configs/default.yaml`，排序可解释且确定 | 手写词元计数已替换；LlamaIndex retrievers 需向量库或 LLM，离线复现成本高 |
| Markdown 解析 | `markdown-it-py` | 章节 / 表格 / 代码块结构由现成解析器识别，原始行仍作证据摘录 | 手写正则已替换；LlamaIndex document loaders 过重且会改变证据哈希口径 |
| 沙箱资源监控 | `psutil` + 标准库 `subprocess` | 跨平台读取子进程内存；POSIX 另有 `resource.RLIMIT_AS` 硬限制 | `ctypes` 手写 Win32 结构已替换；RestrictedPython / Docker 对本原型过重 |
| 日志 | `structlog` + 标准库 `logging` | 结构化渲染由现成库完成，模块内仍用 `getLogger(__name__)` | 手写 `basicConfig` 格式已替换 |
| 静态检查 | 标准库 `ast` + 配置驱动白名单 | 已是现成能力；规则全部来自 `default.yaml` / `verify_credit.yaml` | `bandit` 只查通用安全漏洞，抓不到禁 `ID` 入模、`build_pipeline` 契约签名等项目规则；作为补充也未引入，以免改变 `StaticCheckResult.checks` |
| cassette 回放 | `RecordedLLM`（`BaseLLM` 层按角色 + prompt 命中） | 无 key、断网可原样回放；未命中显式报错，不静默造假 | `vcrpy` 拦截 HTTP 层，而 `provider=cassette` 根本不构造 `openai` client，无法工作；已录制的脱敏 cassette 也会失效 |
| 四层验证 | 自研组合器 + `pytest` + 子进程沙箱 | 题目任务 5 要的是「统一验证机制」这一组合，无单一现成库覆盖；指标用 `sklearn.metrics`、报告用 `Jinja2` | 无对应单一库；组合编排属项目职责 |
| 项目业务规则 | 时间外划分、禁 `ID` / 敏感字段、T1–T4 列名映射、成本比阈值、证据 SHA-256、`verify_*.yaml` 门槛 | 题目场景的合规约束，任何通用库都不会内置，属必须自研部分 | 无对应现成库 |
| 算法栈 | pandas + scikit-learn + imbalanced-learn | 全 CPU、秒级、确定性强，`Pipeline` 天然防泄漏 | — |
| 接入 | Typer CLI | 现成 CLI 框架，`--version` / `--check` / `run --spec` 三入口 | `argparse` 已替换；FastAPI / Streamlit 属 P5 |
| 报告 / 可视化 | Jinja2 Markdown + PyVis HTML | 交付验证报告样例与图谱可视化 | — |

**当前仓库结构**

```
algo-capability-factory/
├── README.md  requirements.txt  .env.example  pyproject.toml  .gitignore
├── .codebuddy/{CODEBUDDY.md, rules/}
├── configs/{default.yaml, verify_credit.yaml, verify_regression.yaml, verify_text.yaml}
├── scripts/download_data.py
├── assets/
│   ├── data/UCI_Credit_Card.csv
│   ├── docs/{data_dictionary.md, risk_policy.md, expert_rules.md,
│   │         experiment_log.md, failure_review.md, test_report.md}
│   ├── legacy/legacy_default_model.py
│   └── llm_cassettes/          # 脱敏后的真实 LLM 对话与响应，入库
├── factory/
│   ├── __init__.py  __main__.py
│   └── contracts/{__init__.py, models.py}
├── outputs/{generated/, reports/, kg/}
└── tests/
```

上述为骨架与能力抽取素材；`knowledge/`、`agents/`、`workflow/`、`runtime/`、`validation/` 等实现模块将在后续阶段按提交逐步加入。内部规划文档不纳入版本控制。

---

## 3. 能力知识图谱 schema 和示例

### 节点（9 类）

| 节点 | 关键属性 |
|---|---|
| `Capability` | id、name、version、task_type、input_schema、output_schema、constraints、source_ref、status、hash |
| `Operator` | Imputer / Encoder / WOEBinner / Sampler / Scaler / Model / ThresholdTuner / FairnessAuditor |
| `Algorithm` | family、hyperparams、lib_deps、code_template_ref |
| `Metric` | name、direction、applicable_task、threshold、plugin_ref |
| `Dataset` | columns、target、split_policy、known_issues |
| `Environment` | python_version、packages、seed、resource_limit |
| `ValidationRun` | run_id、candidate_id、metrics、passed、duration、peak_memory、timestamp |
| `FailureCase` | error_type、traceback_sig、root_cause、fix_strategy、occurrence |
| `Evidence` | path、excerpt、sha256、doc_type |

### 边（12 类）

| 边 | 用途 |
|---|---|
| `REQUIRES`、`USES`、`EVALUATED_BY`、`APPLIES_TO`、`DEPENDS_ON`、`EVIDENCED_BY` | 表达输入输出、适用条件、评价指标、依赖环境与证据来源 |
| `Operator -PRECEDES-> Operator` | 编码 pipeline 顺序与「fit 仅 on train」约束，验证期做静态泄漏检查 |
| `Capability -HAS_RUN-> ValidationRun -RESULTED_IN-> FailureCase -FIXED_BY-> Capability(v+1)` | 沉淀闭环，失败经验可被下一轮检索命中 |
| `DERIVED_FROM`、`TRANSFERABLE_TO`、`SIMILAR_TO` | 版本谱系、跨场景迁移、检索邻域扩展 |

### 六要素落地示例

| 题目要素 | 本场景内容 |
|---|---|
| 算法能力 | WOE 分箱与评分卡 LR、还款状态序列特征、未文档化类别清洗、负数账单处理、类别不平衡与成本敏感阈值、PSI 稳定性、公平性审计 |
| 输入输出 | 输入 23 维结构化特征；输出违约概率 `pd` ∈ [0,1]、阈值标签、标准评分卡分数 |
| 适用条件 | 额度区间、需 ≥6 期账单历史、样本期 2005-04 至 2005-09、敏感字段使用限制、漏报/误报成本比 5:1、最低 KS 门槛、仅作辅助决策 |
| 评价指标 | AUC、KS、PR-AUC、F1、成本加权损失、PSI、分组 AUC |
| 依赖环境 | Python 3.11、pandas / scikit-learn / imbalanced-learn，纯 CPU，固定 seed，60s / 2GB 上限 |
| 历史验证结果 | 每轮 `ValidationRun` 的指标、修复轨迹、候选排名、耗时与内存 |

**能力节点示例（示意 JSON）**

```json
{
  "id": "cap.credit.woe_binning.v1",
  "name": "信用评分卡 WOE 分箱与逻辑回归",
  "task_type": "tabular_binary_classification",
  "input_schema": {"LIMIT_BAL": "numeric", "PAY_0": "ordinal", "BILL_AMT1": "numeric"},
  "output_schema": {"pd": "float[0,1]", "label": "int{0,1}", "score": "int"},
  "constraints": ["需≥6期账单历史", "敏感字段不入模", "fit仅on train", "时间外划分"],
  "metrics": ["AUC", "KS", "cost_weighted_loss", "PSI"],
  "evidence": ["docs/expert_rules.md#L12", "docs/experiment_log.md#L31"]
}
```

抽取结果导出为 `outputs/kg/capabilities.json`、`capabilities.csv` 与 `graph.graphml`，可用 `outputs/kg/kg.html` 直接打开可视化。

---

## 4. Agent 工作流设计

**八个角色**（不是单次 prompt 生成代码，每个角色有独立 system prompt、输入输出 schema，可独立测试）：

| 角色 | 输入 → 输出 |
|---|---|
| Interpreter | 自然语言 → `CapabilitySpec` |
| Retriever | Spec → Top-K 能力子图 + 约束清单 + 历史失败规避项 |
| Planner | Spec + 子图 → N 个 `CandidatePlan`（Beam 宽度 3） |
| Coder | Plan → 完整可运行代码（实现 `build_pipeline()`） |
| Reviewer | 代码 → AST 静态评审（危险 import、泄漏、契约签名） |
| Verifier | 沙箱结果 → 四层 `ValidationReport` |
| Repairer | 错误签名 → 定向修复补丁（不重写全量） |
| Curator | 报告 → KG 回写 + 方案设计依据说明 |

**状态机**

```
Parse → Retrieve → Plan → Generate → StaticCheck → Execute → Validate
                                                       ├─ Pass → Compare → Explain → Sink
                                                       └─ Fail → Diagnose → Repair → Generate (≤3 轮)
```

**统一验证机制（对应题目四层）**

| 层 | 检查内容 |
|---|---|
| 接口规范 | `build_pipeline()` 签名、DataFrame schema、输出列名与 dtype、`pd` ∈ [0,1]、AST import 白名单、禁读标签路径、禁 `ID` 入模 |
| 功能正确性 | 小样本 smoke、无 NaN、fit/predict 幂等、固定种子两次输出一致、单类别 / 全缺失边界输入 |
| 指标表现 | 分层 + 时间外划分，AUC / KS / F1 / PR-AUC / 成本加权损失，对比 Dummy 与 LR baseline，test 仅终评一次 |
| 运行稳定性 | 子进程超时 60s、内存上限、重复运行方差、依赖版本校验、异常捕获与分类 |

**错误签名 → 定向修复**

| 错误签名 | 修复动作 |
|---|---|
| `KeyError: PAY_1` | 映射为真实的 `PAY_0`、`PAY_2`…`PAY_6`，写入列名映射能力节点 |
| `SchemaError` | 未文档化类别归入 `others`，`PAY_* = -2` 重编码，记录清洗 `Operator` |
| `LeakageDetected` | 强制 `sklearn.Pipeline`，按 `PRECEDES` 重排，改时间外划分 |
| `MetricBelowThreshold` | 检索历史高分方案 → 切换模型族 / 加采样 / 网格搜成本最优阈值 |
| `ImportError` / `Timeout` / `Nondeterminism` | 换白名单库 / 降采样换轻量模型 / 注入 `random_state` |

每个 `(错误签名 → 修复动作 → 结果)` 三元组回写为 `FailureCase` 与新版 `Capability`，构成可复用经验。

---

## 5. 环境配置和运行方法

**环境**：Python 3.11+（实测 3.12.9），纯 CPU，无需 GPU、无需 Docker、无需数据库服务。

```bash
# 1) 创建环境
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt

# 2) 可选：配置真实 LLM（不配置则使用 --mock 离线运行）
cp .env.example .env            # 只需填 LLM_API_KEY；端点与模型已有默认值

# 3) 可选：重新拉取数据（仓库已内置，断网可跳过）
python scripts/download_data.py

# 4) 端到端七步闭环（生成代码 + 四层报告 + 修复轨迹 + 图谱回写）
python -m factory run --spec "预测信用卡客户下月违约概率，按5:1成本比选阈值，禁止时间泄漏" --mock

# 5) 分阶段可复现入口
python scripts/build_kg.py               # 构建能力图谱与检索产物
python scripts/verify_baseline.py        # baseline 四层验证自检
python scripts/run_ablation.py           # 有 KG / 无 KG 消融对比
python scripts/record_llm.py             # 录制真实 DeepSeek 调用（需 key）
python -m unittest discover -s tests -v  # 全量测试

# 6) 入口自检
python -m factory --version
python -m factory --check
```

> `factory ui` 与 FastAPI / Streamlit 界面属 P5 阶段，当前尚未实现；CLI 已可用。

**最小依赖**：核心闭环需 `pydantic`、`PyYAML`、`pandas`、`scikit-learn`、`networkx`、`langgraph`、`rank-bm25`、`markdown-it-py`、`psutil`、`structlog`（全部为现成库，`requirements.txt` 已锁版本区间）；若只需验证数据契约与配置，可先 `pip install pydantic PyYAML` 再运行 `python -m unittest discover -s tests -v`。`pyvis`、`Jinja2`、`Typer`、`openai` 按入口加载，全量清单见 `requirements.txt`。

**关于 LLM**：默认配置是「`Interpreter` 走 `cassette`（真实 DeepSeek 录制响应），其余角色走规则模板」—— 即**能力理解这一环由真实 LLM 驱动**，其余环节保持确定性。`llm.role_providers` 控制按角色路由，`--mock` 会关闭路由、强制全链路规则模板。本地部署模型在本项目不可行（CPU 推理过慢），因此按开发要求 g 的「API 调用方式」接入 **DeepSeek 的 OpenAI 兼容接口**：把 `llm.provider` 切到 `openai_compat`，按 `.env.example` 把 `LLM_API_KEY` 填进 `.env` 或设为环境变量即可。官方端点 `https://api.deepseek.com`、当前示例模型 `deepseek-flash`。真实响应的解析结构（`target.name`、`data_split`、`threshold_selection`、`feature_constraints`、`evaluation`）会被映射进 `CapabilitySpec`，端到端报告里的 `能力理解来源=cassette` 就是这条证据。

**凭据与录制回放**：`LLM_API_KEY` 只从环境变量 / `.env` 读取，`.gitignore` 已排除 `.env` 与 `.env.*`；任何 key、token、Authorization header 都不会写入仓库文件、日志或 cassette。真实调用产生的对话正文与响应脱敏后落盘 `assets/llm_cassettes/` 作为交付证据；把 `llm.provider` 设为 `cassette` 即可在**无 key、断网**环境原样回放同一输出。回放未命中时按 `cassette.on_miss` 显式报错或回退 `MockLLM`，不静默造假。凡引用回放结果的报告段落均标注「离线回放」，与实时调用区分。已录制 2 条真实 DeepSeek 调用（均为 Interpreter 环节，产物见 `assets/llm_cassettes/deepseek_deepseek-flash.json`），回放一致性由 `tests/test_cassette_replay.py` 在不联网条件下逐条校验。**真实出站调用共 2 次**：首次录制，以及替换现成库后用不同 prompt 做的实时链路复测（`scripts/record_llm.py --recheck`，新增第 2 条 entry、不覆盖首次证据）；两条都可断网回放。此外 `tests/test_realtime_llm.py` 以模拟 HTTP 层做零费用回归（请求参数、响应解析、脱敏录制、回放全链路），不发请求、不改写交付 cassette。离线回放与实时调用在报告中始终区分。真实 API 演示与预设的修复轨迹分两次运行、分开写入报告。

**主要产物**

| 路径 | 内容 |
|---|---|
| `outputs/generated/candidate_*.py` | 生成 / 修复后的算法代码 |
| `outputs/reports/run_*.md` | 四层验证报告、候选排名、修复轨迹、设计依据 |
| `outputs/kg/graph.graphml`、`kg.html` | 回写后的能力图谱与可视化 |
| `outputs/runs/trace_*.json` | 七步流程可回放轨迹（运行时临时产物，不入库） |
| `assets/llm_cassettes/*.json` | 脱敏后的真实 LLM 对话与响应，供离线回放（入库） |

**配置说明**：`configs/verify_credit.yaml` 定义主场景的划分策略、指标门槛与成本比；`verify_regression.yaml`、`verify_text.yaml` 用于验证「不同任务类型的验证配置」与跨场景迁移，切换配置文件不改核心代码。

---

## 6. 示例数据和测试任务说明

**主数据集**：UCI Default of Credit Card Clients（Yeh & Lien, 2009，DOI `10.24432/C55S3H`），30,000 实例、23 特征 + 1 标签，正例约 22.1%。UCI 页面标注 **CC BY 4.0**，OpenML `d/43435` 提供 **CC0 Public Domain** 版本，均可随仓库分发。

| 字段组 | 列 |
|---|---|
| 标识 | `ID`（禁止入模） |
| 额度 | `LIMIT_BAL` |
| 人口属性 | `SEX`、`EDUCATION`、`MARRIAGE`、`AGE`（敏感属性，仅用于公平性审计） |
| 还款状态 | `PAY_0`、`PAY_2` … `PAY_6` |
| 账单金额 | `BILL_AMT1` … `BILL_AMT6` |
| 付款金额 | `PAY_AMT1` … `PAY_AMT6` |
| 标签 | `default.payment.next.month` |

**模拟业务材料（6 份，对应题目背景的五类能力来源）**

| 文件 | 类型 | 提供的能力 |
|---|---|---|
| `docs/risk_policy.md`、`docs/data_dictionary.md` | 业务文档 | 成本比、额度区间、字段字典、适用条件 |
| `legacy/legacy_default_model.py` | 历史代码仓库 | 旧评分卡实现、依赖、可抽取函数 |
| `docs/expert_rules.md` | 专家经验 | WOE 分箱、还款状态衍生、阈值经验 |
| `docs/experiment_log.md` | 实验记录 | 历史模型与调参结果 |
| `docs/test_report.md`、`docs/failure_review.md` | 测试报告 / 失败复盘 | 失败案例、泄漏事故、评价指标口径 |

**已知数据陷阱**（本项目的核心领域知识与真实失败案例来源）

| 编号 | 陷阱 |
|---|---|
| T1 | 字段名为 `PAY_0` 而非直觉的 `PAY_1`，`PAY_1` 不存在 |
| T2 | `EDUCATION` 有未文档化的 0 / 5 / 6；`MARRIAGE` 有未文档化的 0（54 条）；`PAY_*` 最小 -2 未在数据字典中 |
| T3 | `BILL_AMT*` 可为负；账单期与付款期存在错位 |
| T4 | 标签是「下月」违约，随机划分会引入未来信息泄漏 |

**测试任务**

| 任务 | 配置 | 用途 |
|---|---|---|
| T-credit 信用卡违约二分类（主） | `verify_credit.yaml` | 端到端闭环演示，含 3 轮真实修复 |
| T-regression 需求量回归 | `verify_regression.yaml` | 验证不同任务类型的验证配置（UCI Bike Sharing / California Housing） |
| T-text 文本分类 | `verify_text.yaml` | 验证跨场景迁移（AG News 或 ChnSentiCorp） |

**数据使用声明**：数据仅用于算法原型研究。敏感字段仅用于分组公平性审计，不构成任何授信或部署建议；样本来自 2005 年 4–9 月单一时段，结论不外推至当前客群。

---

## 7. 生成算法代码示例

`python -m factory run --spec "..." --mock` 会在 `outputs/generated/` 落盘 3 个候选的最终源码，均由 `Coder` 按方案渲染、经 `Reviewer` 静态检查与 `Repairer` 定向修复：

```python
# outputs/generated/candidate_plan.01.py（节选，完整文件见仓库）
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = ["LIMIT_BAL", "PAY_0", "..."]   # 19 列；ID / 敏感字段 / 标签已剔除

def build_pipeline(config):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(C=0.5, max_iter=1000, random_state=42)),
    ])
```

首轮 `Coder` 规则模板按直觉把最近一期写成 `PAY_1`（T1 陷阱），在子进程用真实数据集触发 `KeyError: PAY_1`；`Repairer` 按策略表替换为 `PAY_0` 后重新通过沙箱。三个候选以不同 `C` 值区分，AUC 实测见第 8 节。

实现要点：

1. 所有预处理置于 `sklearn.Pipeline` 内，fit 仅作用于训练集；
2. 特征列由配置与数据字典推导，显式排除 `ID`、标签与四个敏感字段；
3. 不含文件写入、网络访问、危险 import，可在沙箱内重复运行且结果确定；
4. 生成代码在独立子进程中执行，超时与内存上限由 `configs/default.yaml` 控制。

完整的「能力描述 → 检索证据 → 3 个候选 → 代码 → 修复 diff」示例见 `outputs/reports/run_demo.md`，生成代码见 `outputs/generated/candidate_plan.0*.py`。

---

## 8. 验证结果和报告样例

> 以下为一次真实运行的实测结果，不做数值填充或美化。指标未达业务门槛时如实判 FAIL，并保留失败记录回写 `FailureCase`。

**端到端报告**：`outputs/reports/run_demo.md`（七步轨迹、检索证据、候选排名、四层结论、修复轨迹、设计依据、图谱 diff）。**框架自检样例**：`outputs/reports/validation_sample.md`（标注为 baseline，非最终验收）。

| 项目 | 实测结果 |
|---|---|
| 七步流程 | a–g 全部执行完成，CLI 退出码 0 |
| 候选方案 | 3 个（Beam Top-3），AUC 0.72061 / 0.72063 / 0.72064 |
| 修复轨迹 | 默认（有 KG）首轮即避开 T1、修复 3 轮；无 KG 时复现 `KeyError: PAY_1` → 列名映射为 `PAY_0`、修复 4 轮（见下方消融） |
| 四层结论 | 接口 / 功能 / 稳定性 PASS；指标层 FAIL（AUC 0.7206 < 0.78、F1 < 0.45） |
| 图谱沉淀 | `outputs/kg/capabilities_after_run.json`，新增 ValidationRun / FailureCase / 能力 v2 节点 |

**四层验证结论（实测）**

| 层级 | 检查项 | 结果 | 说明 |
|---|---|---|---|
| 接口规范 | 契约签名 / AST 白名单 / 禁 `ID` 入模 | PASS | 静态检查 |
| 功能正确性 | smoke / 无异常 / 确定性 | PASS | 子进程用真实数据 fit / predict |
| 指标表现 | AUC、KS、PR-AUC、F1、成本损失、PSI、分组 AUC | FAIL | 时间外划分；baseline 级 LR 未达业务门槛 |
| 运行稳定性 | 超时 60s / 内存 2GB / 重复运行 | PASS | 单次约 1.7–2.1s，子进程隔离 |

**可复现的真实修复轨迹（实测）**

无 KG 对照组（`scripts/run_ablation.py` 的 `without_kg` 组，图谱不含历史经验）：

| 轮次 | 错误签名 | 定向修复 | 结果 |
|---|---|---|---|
| 1 | `KeyError: PAY_1` | 按 `Dataset` 列名映射改为 `PAY_0` | 沙箱从 FAIL 恢复为 PASS |
| 2 | `MetricBelowThreshold` | 策略表命中「切换模型族 / 按成本比调阈值」，当前 Mock 模板无可执行动作 | 如实标记 `no_change`，停止盲目重试 |

有 KG 默认路径：`Interpreter` 走真实录制、图谱含首轮 `FailureCase`，Coder 首轮即用 `PAY_0`，`KeyError` 不再出现，修复轮次降为 3；差异见下方消融表。

> 说明：指标层未达标是 baseline 级候选的真实表现，不是流程失败；达到 `verify_credit.yaml` 门槛需要后续引入 WOE 分箱、采样与成本最优阈值。

**沉淀闭环消融（实测，`scripts/run_ablation.py`）**

同一 spec、同一候选方案、同一数据集，唯一变量是是否检索并注入图谱证据：

| 指标 | 有 KG | 无 KG |
|---|---|---|
| 图谱来源 | 上一轮回写 `capabilities_after_run.json` | 源材料重抽 |
| 命中历史失败经验 | 是 | 否 |
| 修复轮次 | 3 | 4 |
| 是否首轮避开 T1 | 是 | 否 |
| 错误签名 | `MetricBelowThreshold` ×3 | `KeyError: PAY_1` + `MetricBelowThreshold` ×3 |
| 候选 AUC（降序） | 0.720635 / 0.720629 / 0.720612 | 0.720635 / 0.720629 / 0.720612 |

有 KG 组从回写图谱读到上一轮的 `KeyError: PAY_1` 失败案例，Coder 首轮即改用 `PAY_0`，省掉一次失败执行；无 KG 组没有这条证据，先踩 T1 再修复。两组 AUC 完全一致，说明沉淀改变的是过程效率而非指标口径，未做任何数值美化。完整对比见 `outputs/reports/ablation.md`。

---

## 9. 遇到的挑战和解决方案

以下为设计阶段已识别的挑战、以及实现过程中补记的解决方案；其余实现问题将在 P5 结束后继续补记。

| 挑战 | 解决方案 |
|---|---|
| **数据字典与实际数据不一致**（T1、T2），生成代码易按直觉写错列名与类别枚举 | 把 T1–T4 全部抽成 `Dataset.known_issues` 与能力节点，验证期做 schema 断言，失败后按列名表定向修复，并把修复结果回写为可复用经验 |
| **时间泄漏**：标签为「下月」违约，随机划分会让模型看到未来信息，指标虚高 | 时间外划分 + `PRECEDES` 约束强制 `Pipeline` 且 fit 仅 on train + AST 静态泄漏检查；test 集仅在终评使用一次 |
| **无大模型 / 无额度时 demo 跑不起来** | `BaseLLM` 抽象 + `MockLLM` 规则模板为默认路径，真实 LLM 仅作增强，prompt 模板与输出 schema 落盘以保证确定性 |
| **生成代码不可信** | 独立子进程沙箱 + 超时 / 内存限制 + AST import 白名单 + 临时目录 + 禁网 + 禁读标签路径 |
| **知识图谱容易沦为静态展示** | 检索结果强制进入 Planner / Coder prompt，`PRECEDES` 参与验证，并做「有 KG / 无 KG」消融对比写入报告 |
| **修复退化为反复重试** | 先做错误分类再按签名定向修复，最多 3 轮，每轮记录 `(错误签名, 修复动作, 结果)` 三元组 |
| **敏感属性与公平性** | 敏感字段不入模，仅用于分组 AUC 审计，README 明确不作部署建议；把公平性做成 `Metric` 插件 |
| **数据时效与分布漂移** | 用 PSI 指标 + 时间外验证量化漂移，作为「真实行业落地复杂问题」写入报告，不回避 |
| **小数据下资源分析缺说服力** | 构造 10× 合成扩展集，记录各候选耗时 / 峰值内存 / 推理 P95 |
| **指标口径不统一** | 成本比、KS 门槛、baseline 定义全部配置化到 `verify_*.yaml`，避免硬编码 |
| **早期为快速打通闭环写了若干自研轻量件，与开发要求 f「可使用现成工具但需说明选择理由」有张力** | 中途把「复用优先」写进 `.codebuddy/rules/architecture.md` 作为不可裁剪规则，逐项评估现成方案后替换：自研状态机 → LangGraph `StateGraph`、`ctypes` 内存监控 → `psutil`、手写日志格式 → `structlog`、`argparse` → `Typer`、手写 Markdown 正则 → `markdown-it-py`、手写词元计数 → `rank_bm25`；`vcrpy` / `bandit` / CrewAI / LlamaIndex 评估后因粒度或契约冲突未采用，理由逐项写在第 2 节选型表。全部替换以「功能不变」验收：ruff 全绿、83 用例全过、图谱仍 95 节点 / 259 边、端到端 3 候选 AUC 与修复轨迹逐字一致 |
| **沉淀只写不读**：Curator 已把结果写入 `capabilities_after_run.json`，但工作流每轮都从源材料重抽，下一轮看不到上一轮经验 | 让 `Workflow` 启动时优先加载回写图谱（不存在才回退源材料），检索器优先返回本项目实测 `FailureCase`，Coder 命中 T1 历史经验时首轮即避开，Curator 按 `run_id` 去重避免膨胀。消融实测：修复轮次 3 vs 4、有 KG 首轮避开 `PAY_1`、两组 AUC 完全一致 |

---

## 10. 后续可扩展方向

1. 以真实向量检索替换 BM25，保留可解释打分作为对照；
2. 用 MCTS 替代 Beam Search，比较方案搜索效率与最终指标；
3. 增加 PSI 漂移监控与能力自动降级策略；
4. 从真实业务仓库持续增量抽取，形成能力版本谱系与血缘追踪；
5. 扩展回归、多标签、时序任务的验证插件，成为多任务能力工厂；
6. 引入成本敏感多目标优化，同时优化 AUC、成本损失与公平性约束；
7. 对接在线评分服务的部署配置（OpenAPI 接口文档由 P5 的 FastAPI 自动生成并导出为 `outputs/reports/openapi.json`，属交付物而非后续方向）；
8. 接入更多真实代码仓库的函数级抽取，提升能力复用率。

---

## 附录 A · 题目十项对照

| 题目要求 | 本 README 章节 |
|---|---|
| 1 项目背景和目标 | 第 1 节 |
| 2 系统架构和模块设计 | 第 2 节 |
| 3 能力知识图谱 schema 和示例 | 第 3 节 |
| 4 Agent 工作流设计 | 第 4 节 |
| 5 环境配置和运行方法 | 第 5 节 |
| 6 示例数据和测试任务说明 | 第 6 节 |
| 7 生成算法代码示例 | 第 7 节 |
| 8 验证结果和报告样例 | 第 8 节 |
| 9 遇到的挑战和解决方案 | 第 9 节 |
| 10 后续可扩展方向 | 第 10 节 |

## 附录 B · 实现后需更新的占位内容

- [x] 顶部「当前仓库状态」改为实际完成阶段
- [x] 第 5 节命令与 `requirements.txt` 对齐
- [x] 用 DeepSeek API 录制真实调用并补齐 cassette 证据（prompt 模板见 `factory/llm/demo.py`）
- [x] 第 7 节替换为 `outputs/generated/` 中的真实生成代码与修复 diff
- [x] 第 8 节所有 `<实测后填充>` 替换为实测指标，附上真实报告文件与图谱 diff
- [x] 第 9 节补记「复用优先」实现挑战；其余实现挑战待 P5 末
- [x] 附录 A 保持与最终 README 结构一致
- [x] P4 补「有 KG / 无 KG」消融对比与第二轮检索命中首轮经验的证据（见第 8 节与 `outputs/reports/ablation.md`）
- [ ] P5 补 Web / API 界面与最终验收指标

## 附录 C · 数据与引用

```
Yeh, I. C., & Lien, C. H. (2009). Default of Credit Card Clients [Dataset].
UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H
License: CC BY 4.0 (UCI) / CC0 Public Domain (OpenML d/43435)
```

衍生材料 `assets/docs/` 与 `assets/legacy/` 为本项目构造的模拟业务材料，仅用于演示能力抽取流程。

---

## 附录 D · 实现演进与阶段 ↔ 提交对照

本节如实记录仓库的开发顺序。历史按 P0 → P3 分阶段独立提交（Conventional Commits + body 说明「为什么」），**未改写任何已推送提交**；`.codebuddy/rules/git-commit.md` 明确禁止 force push `main` 与改写已推送提交。

**演进主线**：P0 骨架与规范 → P1 能力图谱与检索 → P2 沙箱与四层验证 → P3 三种 LLM 后端、脱敏 cassette 与 a–g 七步闭环 → 按「复用优先」规则把自研件替换为现成库。最后一阶段不是推翻前期工作，而是在对外契约、产物与测试行为完全不变的前提下换成成熟实现，回归证据见第 8、9 节。

| 阶段 | 代表性提交 | 内容 |
|---|---|---|
| P0 骨架与规范 | `7844ad8`、`0cc7f60`、`4c79d44`、`b108259` | 仓库初始化、信用卡违约示例数据、契约骨架、配置与业务材料、项目级 CodeBuddy 规则 |
| 规范校准 / LLM 路线 | `71b9d75`、`020e665`、`6450a45`、`aa3dacf`、`dc4c148`、`cee2ed0` | 按 `llm_agent.md` 原文区分题目硬要求与设计选择；确定 DeepSeek API + cassette；补齐生成参数与协作约定 |
| P1 能力图谱 | `3463084`、`4dcff63` | 9 类节点 / 13 类关系、证据哈希、NetworkX + SQLite、JSON/CSV/GraphML、混合检索、PyVis；清理 lint 违规 |
| P2 验证框架 | `9f7b6c4`、`6625bee`、`d1ce37b`、`1126ee9` | 交付 JSON 去时间戳改用内容哈希、AST 静态检查 + 子进程沙箱、指标插件 / 时间外划分 / 四层检查器 / 报告、冻结验证样例 |
| 分支与流程调整 | `5f3290b`（PR #1，merge commit）、`20b70ac`、`7fe4f98`、`0b936d8` | 早期按规则采用 feature 分支 + PR，单人开发后改为直推 `main`；两处 merge commit 保留分支节点 |
| P3 LLM 后端 | `3ceb961`、`ecd9e69`、`1a0148f` | `MockLLM` / `OpenAICompatLLM` / `RecordedLLM`、脱敏 cassette 与断网回放、一次真实 DeepSeek 调用证据 |
| P3 七步闭环 | `677ab5b`、`4a6e5c6`、`208bbd7` | 8 角色、Beam Top-3、≤3 轮定向修复、Curator 回写、`run --spec` 与端到端产物 |
| 复用优先整改 | `5f26a87`、`379f7aa`、`f064a1b`、`82f6d4f` | 新增规则；现成库替换基础设施 / 检索 / 解析；LangGraph 替换自研状态机；同步选型理由与产物 |
| P4 沉淀闭环 | `c642c24` | 工作流优先加载回写图谱、检索优先实测失败经验、Coder 首轮避开 T1、回写按 `run_id` 去重；新增消融脚本与对比报告 |

> 完整历史以 `git --no-pager log` 为准。所有提交时间由 Git 按实际提交时刻记录，未做调整；评审可据此还原 P0 → P3 的演进。

---

本 README 随各阶段实现进度持续更新，每次更新对应一次独立提交。
