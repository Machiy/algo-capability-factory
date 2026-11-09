# AlgoCap Factory · 基于 AI Agent 的算法能力工厂

[![ci](https://github.com/Machiy/algo-capability-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/Machiy/algo-capability-factory/actions/workflows/ci.yml)

> 面向「信用卡客户下月违约预测」场景，实现从自然语言能力描述到可运行算法代码的端到端半自主生成，并跑通 **能力抽取 → 能力复刻 → 能力验证 → 能力沉淀** 完整闭环。
>
> 对应题目：LLM Agent 笔试《基于 AI Agent 的算法能力系统开发》。

**当前仓库状态：P0–P5 已完成并实测。** a–g 七步闭环（能力抽取 → 检索 → 规划 → 生成 → 验证 → 修复 → 沉淀）全链路可跑；L0 契约、L1 能力图谱与混合检索、L2 的 8 个 Agent 角色与 LangGraph 编排、L3 子进程沙箱与 AST 静态检查、L4 四层验证与报告生成、L5 的 Typer CLI 与 FastAPI 均已落地，并支持三种 LLM 后端与脱敏 cassette。`python -m factory run --spec "..." --mock` 一次产出生成代码、四层报告、修复轨迹与图谱回写；最新一次实测为 3 候选、最佳候选（HGB）四层全通过、AUC 0.7843。题目进阶要求的 8 项全部满足，10 项加分项已全部覆盖（真实仓库抽取见第 3 节、资源消耗分析见第 8 节、跨场景迁移见第 8 节）。本文档已按题目「提交方式」要求的十项内容写好。

---

## 5 分钟验收路径

> 无 GPU、无 Docker、无数据库、无需 API key；数据与 cassette 均已入库，**断网可跑**。

| # | 命令 | 应看到 |
|---|---|---|
| 0 | `python -m venv .venv` → 激活（Windows `.venv\Scripts\activate`，Linux/macOS `source .venv/bin/activate`）→ `pip install -r requirements.txt` | 一次性安装完成，无需清单外依赖 |
| 1 | `python -m ruff check .` | `All checks passed!` |
| 2 | `python -m unittest discover -s tests` | `Ran 128 tests ... OK` |
| 3 | `python -m factory run --spec "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"` | `四层全通过=True 理解来源=cassette 候选=3`；最佳候选 HGB AUC 0.7843。修复轮次取决于是否已有回写图谱：仓库自带 `capabilities_after_run.json` 时为 **2**（首轮避开 T1），删掉该文件再跑为 **3**（现场复现 `KeyError: PAY_1` → 定向修复） |
| 4 | `python -m factory run --spec "把短信分类为垃圾短信或正常短信，输出准确率与宏平均F1" --mock --task-config configs/verify_text.yaml --run-id text_demo --kg-out capabilities_text_after_run.json --gen-dir text` | `四层全通过=True`；linear_svc accuracy 0.9803 |
| 5 | `python -m factory run --spec "根据多期特征预测日需求量，最小化RMSE，输出RMSE/MAE/R2" --mock --task-config configs/verify_regression.yaml --run-id regression_demo --kg-out capabilities_regression_after_run.json --gen-dir regression` | `四层全通过=True`；ridge RMSE 19.31、R² 0.978 |

**只看一个文件**：`outputs/reports/run_demo.md` —— 七步轨迹、检索证据、候选排名、四层结论、修复轨迹、图谱 diff 全在里面。
**只看一处修复**：该报告第 4 节 `KeyError: PAY_1 → 按 Dataset 列名映射把 PAY_1 改为 PAY_0`（数据自带的 T1 陷阱，非人为埋 bug）。
**只看图谱**：浏览器打开 `outputs/kg/kg.html`（PyVis 可视化），或 `outputs/kg/graph.graphml`（任意图工具）。

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

**快速开始**

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
| L1 知识 | `knowledge/` | Schema、材料抽取器（`Extractor`）、真实仓库 AST 抽取器（`RepoExtractor`）、NetworkX 图 + SQLite 持久化、混合检索器、PyVis 可视化 |
| L2 Agent | `agents/`、`workflow/` | 8 个角色、LangGraph 状态机、Beam Search、修复策略表 |
| L2 支撑 | `llm/` | `BaseLLM` 抽象与三个实现：`MockLLM`（默认）、`OpenAICompatLLM`（DeepSeek API）、`RecordedLLM`（cassette 回放） |
| L3 执行 | `runtime/` | 子进程沙箱、AST 静态检查、超时 / 内存限制、错误分类器 |
| L4 验证 | `validation/` | 四层检查器、指标插件注册、报告生成 |
| L5 接入 | `cli/`（`__main__.py`）、`api/` | Typer CLI、FastAPI；Web UI（Streamlit）按裁剪顺序未做，题目「或」已由 CLI + API 满足 |
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
| 真实仓库抽取 | 标准库 `ast` + `RepoExtractor` | 只需「函数签名 / module 级依赖 / docstring 能力描述 / 行号证据」四类信息，标准库足够且零新增依赖 | `griffe` / `pydoc-markdown` 能导出 API 文档对象，但映射到本项目 `Capability` / `Evidence` 契约仍需同等量适配代码；`radon` / `pydeps` 只给复杂度和依赖图，不产出能力描述。故未引入 |
| cassette 回放 | `RecordedLLM`（`BaseLLM` 层按角色 + prompt 命中） | 无 key、断网可原样回放；未命中显式报错，不静默造假 | `vcrpy` 拦截 HTTP 层，而 `provider=cassette` 根本不构造 `openai` client，无法工作；已录制的脱敏 cassette 也会失效 |
| 四层验证 | 自研组合器 + `pytest` + 子进程沙箱 | 题目任务 5 要的是「统一验证机制」这一组合，无单一现成库覆盖；指标用 `sklearn.metrics`、报告用 `Jinja2` | 无对应单一库；组合编排属项目职责 |
| 项目业务规则 | 时间外划分、禁 `ID` / 敏感字段、T1–T4 列名映射、成本比阈值、证据 SHA-256、`verify_*.yaml` 门槛 | 题目场景的合规约束，任何通用库都不会内置，属必须自研部分 | 无对应现成库 |
| 算法模板 | 装饰器注册表（`factory/agents/templates.py`），内置表格分类（LR / HGB / RF）、文本分类（TF-IDF + LR / LinearSVC / ComplementNB）、回归（Ridge / HGBR / RFR） | 与指标插件同一模式，新增算法族只需一个 `@register` 函数；`Coder` 按 `model_family` 渲染，三个候选因此真的代表三种算法 | 代码模板用标准库 `str.format`，不为单文件模板引入 Jinja2（Jinja2 仅用于报告） |
| 算法栈 | pandas + scikit-learn + imbalanced-learn | 全 CPU、秒级、确定性强，`Pipeline` 天然防泄漏 | — |
| 文本特征与分类 | sklearn `TfidfVectorizer` + LogisticRegression / LinearSVC / ComplementNB | 现成库、纯 CPU、单次 2s 级；英文短信用 sklearn 默认分词即可，无需额外分词器 | `jieba` 只在中文语料必要，本场景不引入；`sentence-transformers` 需下载模型、体积与推理成本远超原型；`transformers` 微调破坏「断网秒级复现」 |
| 接入 | Typer CLI + FastAPI | 现成 CLI / Web 框架，CLI 有 `--version` / `--check` / `run` / `api` 入口，API 有 `/health`、`/templates`、`/run` 三端点并自动导出 OpenAPI | `argparse` 已替换；Streamlit 权衡后未做——题目为「或」，多一个前端只增加依赖与演示成本，不增加评分点 |
| 报告 / 可视化 | Jinja2 Markdown + PyVis HTML | 交付验证报告样例与图谱可视化 | — |

**当前仓库结构**

```
algo-capability-factory/
├── README.md  requirements.txt  .env.example  pyproject.toml  .gitignore
├── .codebuddy/{CODEBUDDY.md, rules/}
├── configs/{default.yaml, verify_credit.yaml, verify_regression.yaml, verify_text.yaml}
├── scripts/{download_data.py, build_kg.py, verify_baseline.py, run_ablation.py,
│            record_llm.py, resource_benchmark.py, extract_repo.py,
│            prepare_text_data.py, prepare_regression_data.py, build_text_kg.py}
├── assets/
│   ├── data/{UCI_Credit_Card.csv, sms_spam.csv, synthetic_demand.csv}
│   ├── docs/{data_dictionary.md, risk_policy.md, expert_rules.md,
│   │   │     experiment_log.md, failure_review.md, test_report.md}
│   │   └── text/{sms_data_dictionary.md, sms_policy.md, sms_failure_review.md}
│   ├── legacy/legacy_default_model.py
│   ├── repo/scorecardpy/       # 真实开源仓库快照（MIT），见 PROVENANCE.md
│   └── llm_cassettes/          # 脱敏后的真实 LLM 对话与响应，入库
├── factory/
│   ├── __init__.py  __main__.py  config.py  logging_setup.py
│   ├── contracts/{models.py, knowledge.py, llm.py, validation.py, workflow.py}
│   ├── knowledge/{extractor.py, repo_extractor.py, parsing.py, graph.py,
│   │              retrieval.py, pipeline.py, visualize.py}
│   ├── agents/{roles.py, templates.py}
│   ├── workflow/pipeline.py    # LangGraph 七步编排
│   ├── llm/{base.py, mock.py, openai_compat.py, recorded.py, cassette.py, routing.py, demo.py}
│   ├── runtime/{sandbox.py, dataset_sandbox.py, static_check.py}
│   ├── validation/{checks.py, metrics.py, split.py, report.py}
│   └── api/app.py
├── outputs/{generated/{,text/}, reports/, kg/, runs/}   # runs/ 为临时轨迹，不入库
└── tests/                      # 14 个测试文件、128 个用例
```

`knowledge/`、`agents/`、`workflow/`、`runtime/`、`validation/`、`api/` 均已实现并入库。内部规划文档（`PLAN.md`）、原始数据包与 `_archive/` 不纳入版本控制。

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

### 边（13 类，与 `factory/contracts/knowledge.py` 的关系枚举一致）

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

### 按场景拆分子图

能力知识不混在一张图里：`verify_*.yaml` 的 `knowledge.docs` 指向该场景的材料目录，工作流从中抽独立子图，检索只命中本场景的约束与失败经验——避免「文本任务拿到 `PAY_1` 列名约束」这类跨域噪声。

| 场景 | 材料目录 | 子图规模 | 产物 |
|---|---|---|---|
| 信用卡违约（主） | `assets/docs/` + `assets/legacy/` | 95 节点 / 259 边 / 36 类能力 | `capabilities.json`、`graph.graphml`、`kg.html` |
| 短信垃圾过滤 | `assets/docs/text/` | 17 节点 / 33 边 / 10 类能力 / 2 个 `FailureCase` | `text_capabilities.json`、`text_graph.graphml`、`text_kg.html` |

文本子图复现：`python scripts/build_text_kg.py`。两套材料结构一致（适用条件表、验收门槛表、`FR-xx` 复盘小节），因此**抽取器与检索器代码一行未改**。

**真实开源仓库抽取（`RepoExtractor`）**

除 6 份自建材料外，还从真实开源仓库 `scorecardpy`（MIT，快照与来源见 `assets/repo/PROVENANCE.md`）做 AST 抽取，实测产出 **95 节点 / 248 边 / 79 个公开能力**：

| 抽取内容 | 来源 | 落地 |
|---|---|---|
| 函数 / 方法 | `ast.FunctionDef` | 每个公开函数一个 `Capability` 节点（id `cap.repo.scorecardpy.<module>.<func>`） |
| 参数与返回 | docstring `Params` / `Returns` 段 | `attributes.parameters` / `attributes.returns`（21 个函数有结构化参数，其余用签名兜底） |
| 能力描述 | docstring 首行 | 节点 `name`，例如 `WOE Binning`、`Information Value`、`KS, ROC, Lift, PR` |
| 依赖 | module 级 import 减去标准库与包内自引用 | `Environment` 节点 `env.repo.scorecardpy`，实测 8 个第三方依赖 |
| 可回溯证据 | 签名行 + docstring 首行，含文件与行号 | `Evidence`（`sha256` 可重算）+ `EVIDENCED_BY` 边 |
| 能力组合 | 函数体内的点号调用 | `USES` 边，表示一个能力复用另一个能力 |

产物：`outputs/kg/repo_capabilities.json`、`repo_capabilities.csv`、`repo_graph.graphml`；复现命令 `python scripts/extract_repo.py`。抽取器只做 `ast.parse`，**不 import、不执行**被抽取仓库代码。

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

# 4b) 跨场景迁移：同一套框架跑文本分类，只换 --task-config（PowerShell 单行执行）
python -m factory run --spec "把短信分类为垃圾短信或正常短信，输出准确率与宏平均F1" --mock --task-config configs/verify_text.yaml --run-id text_demo --kg-out capabilities_text_after_run.json --gen-dir text

# 4c) 第二种任务类型：回归（主指标 RMSE，direction: minimize）
python -m factory run --spec "根据多期特征预测日需求量，最小化RMSE，输出RMSE/MAE/R2" --mock --task-config configs/verify_regression.yaml --run-id regression_demo --kg-out capabilities_regression_after_run.json --gen-dir regression

# 5) 分阶段可复现入口
python scripts/build_kg.py               # 构建主场景能力图谱与检索产物
python scripts/build_text_kg.py          # 构建文本场景子图（outputs/kg/text_*）
python scripts/verify_baseline.py        # baseline 四层验证自检
python scripts/run_ablation.py           # 有 KG / 无 KG 消融对比
python scripts/resource_benchmark.py     # 1× / 10× 资源消耗与性能基准
python scripts/extract_repo.py           # 从真实开源仓库抽取函数 / 依赖 / 能力描述
python scripts/record_llm.py             # 录制真实 DeepSeek 调用（需 key）
python -m unittest discover -s tests -v  # 全量测试

# 6) 接入层（API）
python -m factory api --export-openapi   # 导出 OpenAPI 文档到 outputs/reports/
python -m factory api --port 8000        # 启动 FastAPI 服务（/health、/templates、/run）

# 7) 入口自检
python -m factory --version
python -m factory --check
```

> 接入层现状：CLI 与 FastAPI 均已可用（`factory api --port 8000` 启动服务）；Streamlit 前端按裁剪顺序未做，题目要求为「Web 界面、CLI 或 API」三者之一，CLI + API 已满足。

**最小依赖**：核心闭环需 `pydantic`、`PyYAML`、`pandas`、`scikit-learn`、`networkx`、`langgraph`、`rank-bm25`、`markdown-it-py`、`psutil`、`structlog`（全部为现成库，`requirements.txt` 已锁版本区间）；若只需验证数据契约与配置，可先 `pip install pydantic PyYAML` 再运行 `python -m unittest discover -s tests -v`。`pyvis`、`Jinja2`、`Typer`、`openai` 按入口加载，全量清单见 `requirements.txt`。

**干净环境实测（P5 记录）**：在系统临时目录新建空 venv，仅执行一次 `pip install -r requirements.txt`（106 个包，无冲突），随后直接跑通 `ruff check`（全绿）、当时的 104 个用例与端到端 `factory run`（`四层全通过=True`、`理解来源=cassette`、退出码 0），未安装任何清单外依赖。P6 未引入任何新的第三方依赖（文本与仓库抽取均用已有的 pandas / scikit-learn / 标准库），因此该结论继续成立；补充用例后当前全量测试为 **128 个**，在项目 venv 中全部通过。

**持续集成**：`.github/workflows/ci.yml` 在 Python 3.11 / 3.12 上依次执行 `ruff check`、全量单元测试、两条端到端命令（信用卡违约 + 短信文本），并对输出断言 `四层全通过=True`；端到端走默认 provider（Interpreter 用已入库 cassette），因此 CI 不依赖任何 API key。

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

**配置说明**：三份 `verify_*.yaml` 均为 `status: active`，全部端到端跑通过——`verify_credit.yaml`（表格二分类，主指标 AUC）、`verify_text.yaml`（文本分类，主指标 accuracy）、`verify_regression.yaml`（回归，主指标 RMSE，`direction: minimize`）。切换任务只换 `--task-config`，核心验证器、沙箱与工作流代码不改。

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

**文本场景数据集（跨场景迁移用）**：UCI SMS Spam Collection（dataset 228，**CC BY 4.0**），5,574 条短信、spam 占 13.4%。`scripts/prepare_text_data.py` 下载原包并转成 UTF-8 CSV（`assets/data/sms_spam.csv`，列为 `text,label`），固定种子洗牌后按 60/20/20 切分；文本任务没有「下月」这类时序语义，因此配置里显式使用 `random_holdout` 而非时间外划分。

**模拟业务材料（6 份，对应题目背景的五类能力来源）**

| 文件 | 类型 | 提供的能力 |
|---|---|---|
| `docs/risk_policy.md`、`docs/data_dictionary.md` | 业务文档 | 成本比、额度区间、字段字典、适用条件 |
| `legacy/legacy_default_model.py` | 历史代码仓库（自建示例） | 旧评分卡实现、依赖、可抽取函数 |
| `repo/scorecardpy/` | 真实开源仓库（MIT，来源见 `PROVENANCE.md`） | 13 个模块 / 81 个函数的签名、依赖、docstring 能力描述与行号证据 |
| `docs/expert_rules.md` | 专家经验 | WOE 分箱、还款状态衍生、阈值经验 |
| `docs/experiment_log.md` | 实验记录 | 历史模型与调参结果 |
| `docs/test_report.md`、`docs/failure_review.md` | 测试报告 / 失败复盘 | 失败案例、泄漏事故、评价指标口径 |

**文本场景材料（3 份，`assets/docs/text/`）**：`sms_data_dictionary.md`（字段与 ST1–ST4 数据问题）、`sms_policy.md`（S1–S6 适用条件与 accuracy / macro-F1 门槛）、`sms_failure_review.md`（FR-01 词表泄漏、FR-02 只看 accuracy 掩盖少数类误杀）。结构与主场景一致，因此复用同一抽取与检索路径。

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
| T-regression 需求量回归 | `verify_regression.yaml` | 第二种任务类型端到端：合成数据 3,000 条（`status: active`），主指标 RMSE，3 候选全通过，报告 `outputs/reports/run_regression_demo.md` |
| T-text 短信垃圾文本二分类 | `verify_text.yaml` | 跨场景迁移实测：`status: active`，数据 5,574 条（正例 13.4%），3 候选全部通过，报告 `outputs/reports/run_text_demo.md` |

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

首轮 `Coder` 规则模板按直觉把最近一期写成 `PAY_1`（T1 陷阱），在子进程用真实数据集触发 `KeyError: PAY_1`；`Repairer` 按策略表替换为 `PAY_0` 后重新通过沙箱。三个候选由算法模板插件按不同模型族渲染（逻辑回归 ×2 + 直方图梯度提升 ×1），AUC 实测见第 8 节。

实现要点：

1. 所有预处理置于 `sklearn.Pipeline` 内，fit 仅作用于训练集；
2. 特征列由配置与数据字典推导，显式排除 `ID`、标签与四个敏感字段；
3. 不含文件写入、网络访问、危险 import，可在沙箱内重复运行且结果确定；
4. 生成代码在独立子进程中执行，超时与内存上限由 `configs/default.yaml` 控制。

**文本场景生成的候选（同一 Coder，按任务模板渲染）**

```python
# outputs/generated/text/candidate_plan.02.py（完整文件）
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

TEXT_COLUMN = "text"

def build_pipeline(config):
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 1), min_df=2,
                                 max_features=50000, sublinear_tf=True)),
        ("model", LinearSVC(C=1.0, max_iter=5000, random_state=42,
                            class_weight="balanced")),
    ])
```

同一 `Coder` 只按 `model_family`+`task_type` 取模板：表格走 `StandardScaler/SimpleImputer`，文本走 `TfidfVectorizer`，没有第二套生成逻辑。

完整的「能力描述 → 检索证据 → 3 个候选 → 代码 → 修复 diff」示例见 `outputs/reports/run_demo.md`，生成代码见 `outputs/generated/candidate_plan.0*.py`；文本场景对应 `outputs/generated/text/candidate_plan.0*.py`。

---

## 8. 验证结果和报告样例

> 以下为一次真实运行的实测结果，不做数值填充或美化。候选按 Beam Top-3 比较不同算法族，最好的候选指标达标；未达标的候选如实判 FAIL 并保留失败记录回写 `FailureCase`。

**端到端报告**：`outputs/reports/run_demo.md`（七步轨迹、检索证据、候选排名、四层结论、修复轨迹、设计依据、图谱 diff）。**框架自检样例**：`outputs/reports/validation_sample.md`（标注为 baseline，非最终验收）。

| 项目 | 实测结果 |
|---|---|
| 七步流程 | a–g 全部执行完成，CLI 退出码 0 |
| 能力理解 | `能力理解来源=cassette`、`spec_id=spec.next_month_default`（真实 DeepSeek 响应，离线回放） |
| 候选方案 | 3 个（Beam Top-3）：LR(C=0.5) AUC 0.72061、LR(C=1.0) AUC 0.72063、**HGB AUC 0.78434** |
| 修复轨迹 | 首次运行复现 `KeyError: PAY_1` → 列名映射为 `PAY_0`（3 轮）；有 KG 时首轮避开（2 轮），见下方消融 |
| 四层结论 | **`plan.03`（HGB）四层全 PASS**；LR 两个候选指标层 FAIL（AUC < 0.78、F1 < 0.45） |
| 图谱沉淀 | `outputs/kg/capabilities_after_run.json`，新增 ValidationRun / FailureCase / 能力 v2 节点 |

> 说明：`Curator` 按 `run_id` 去重，重复运行同一个 `run_id` 时报告里的「图谱沉淀 diff」会显示 0（新增节点已在首轮写入）；新增节点的完整清单以 `capabilities_after_run.json` 为准，两轮差异见第 8 节消融表与 `outputs/reports/ablation.md`。

**四层验证结论（实测，最佳候选 HGB）**

| 层级 | 检查项 | 结果 | 说明 |
|---|---|---|---|
| 接口规范 | 契约签名 / AST 白名单 / 禁 `ID` 入模 | PASS | 静态检查 |
| 功能正确性 | smoke / 无异常 / 确定性 | PASS | 子进程用真实数据 fit / predict |
| 指标表现 | AUC 0.7843 ≥ 0.78、F1 0.4899 ≥ 0.45、KS 0.4400 ≥ 0.35 | PASS | 时间外划分；HGB 达标 |
| 运行稳定性 | 超时 60s / 内存 2GB / 重复运行 | PASS | 单次约 2.1–2.6s，峰值内存 150–180MB（进程树实测），子进程隔离 |

**可复现的真实修复轨迹（实测）**

无 KG 对照组（`scripts/run_ablation.py` 的 `without_kg` 组，图谱不含历史经验）：

| 轮次 | 错误签名 | 定向修复 | 结果 |
|---|---|---|---|
| 1 | `KeyError: PAY_1` | 按 `Dataset` 列名映射改为 `PAY_0` | 沙箱从 FAIL 恢复为 PASS |
| 2–3 | `MetricBelowThreshold` | 策略表命中「切换模型族 / 按成本比调阈值」，LR 模板无可执行动作 | 如实标记 `no_change`；同批 HGB 候选直接达标 |

有 KG 默认路径：`Interpreter` 走真实录制、图谱含首轮 `FailureCase`，Coder 首轮即用 `PAY_0`，`KeyError` 不再出现，修复轮次由 3 降为 2；差异见下方消融表。

> LR 候选未达标是 baseline 级方案的真实表现，不是流程失败；引入 HGB / RF 后指标层已达标，阈值仍以 `verify_credit.yaml` 为准，未做任何下调。

**沉淀闭环消融（实测，`scripts/run_ablation.py`）**

同一 spec、同一候选方案、同一数据集，唯一变量是是否检索并注入图谱证据：

| 指标 | 有 KG | 无 KG |
|---|---|---|
| 图谱来源 | 上一轮回写 `capabilities_after_run.json` | 源材料重抽 |
| 命中历史失败经验 | 是 | 否 |
| 修复轮次 | 2 | 3 |
| 是否首轮避开 T1 | 是 | 否 |
| 错误签名 | `MetricBelowThreshold` ×2 | `KeyError: PAY_1` + `MetricBelowThreshold` ×2 |
| 候选 AUC（降序） | 0.784337 / 0.720629 / 0.720612 | 0.784337 / 0.720629 / 0.720612 |

有 KG 组从回写图谱读到上一轮的 `KeyError: PAY_1` 失败案例，Coder 首轮即改用 `PAY_0`，省掉一次失败执行；无 KG 组没有这条证据，先踩 T1 再修复。两组 AUC 完全一致，说明沉淀改变的是过程效率而非指标口径，未做任何数值美化。完整对比见 `outputs/reports/ablation.md`。

**性能与资源消耗（实测，`scripts/resource_benchmark.py`）**

同一批模板候选在 1×（30,000 行）与 10×（300,000 行、有放回抽样）数据上的实测值，全部取自子进程沙箱，不是估算：

| 模型族 | 样本数 | 耗时中位数 (s) | 峰值内存 (MB) | 推理 P95 (ms/行) | 放大后耗时 | 放大后内存 |
|---|---|---|---|---|---|---|
| logistic_regression | 30,000 | 2.34 | 175.14 | 0.013 | 3.28 s（1.40×） | 352.89（2.01×） |
| hist_gradient_boosting | 30,000 | 2.45 | 179.17 | 0.032 | 7.36 s（3.00×） | 330.95（1.85×） |
| random_forest | 30,000 | 5.45 | 178.32 | 0.112 | 29.69 s（5.44×） | 355.88（2.00×） |

结论：样本量 10 倍时，内存约为 2×（主要来自 pandas 数据框常驻），耗时按模型复杂度分化——线性模型 1.4×、梯度提升 3.0×、随机森林 5.4×；三者都在 60s / 2GB 沙箱上限内。完整表格与口径说明见 `outputs/reports/resources.md`，复现命令 `python scripts/resource_benchmark.py`。

**跨场景迁移（实测，`configs/verify_text.yaml`）**

同一套工作流、沙箱与四层验证器，只换一份任务配置（`--task-config`）就从表格分类切到文本分类，报告见 `outputs/reports/run_text_demo.md`：

| 候选 | 模型族 | accuracy | macro-F1 | 四层结论 |
|---|---|---|---|---|
| plan.02 | linear_svc（TF-IDF + LinearSVC） | **0.9803** | 0.9564 | 全 PASS |
| plan.01 | logistic_regression（TF-IDF + LR） | 0.9785 | 0.9535 | 全 PASS |
| plan.03 | complement_nb（TF-IDF + ComplementNB） | 0.9731 | 0.9447 | 全 PASS |

差异被收敛到配置与模板两处：`verify_text.yaml` 声明 `text_column`、`knowledge.docs` 与 `candidates.model_families`，`factory/agents/templates.py` 注册 `text_classification.*` 模板；核心验证器、沙箱与工作流代码**未改**。修复轮次为 0——文本场景没有表格列名陷阱，失败修复能力由表格场景的 T1 轨迹证明，不在这里硬造失败。

检索证据也已按场景隔离：报告第 1 节列出的是 `S1 文本长度`、`S3 类别严重不平衡`、`LeakageDetected → 向量器进 Pipeline` 等短信域约束与失败项，不再是信用卡的 `PAY_*` 约束——这是 `knowledge.docs` 拆分子图的直接效果。

**第二种任务类型（实测，`configs/verify_regression.yaml`）**

数据为 `sklearn.datasets.make_regression` 生成的合成需求量（3,000 × 8，固定种子），配置里如实标注「非真实业务数据」；主指标是 **RMSE（`direction: minimize`）**，用来验证候选排序对指标方向的处理：

| 候选 | 模型族 | RMSE ↓ | MAE ↓ | R² ↑ | 四层结论 |
|---|---|---|---|---|---|
| plan.02 | ridge | **19.31** | 15.58 | 0.9776 | 全 PASS |
| plan.01 | hist_gradient_boosting_regressor | 28.53 | 22.02 | 0.9511 | 全 PASS |
| plan.03 | random_forest_regressor | 37.01 | 28.33 | 0.9177 | 全 PASS |

`rmse` 越小越好，报告与 CLI 仍按「越大越靠前」的 `score` 排序——打分时对 `minimize` 指标取负号，因此 plan.02（RMSE 最低）排第一而不是最后。原始值保留在 `metrics` 里，未被符号污染。报告见 `outputs/reports/run_regression_demo.md`。

---

## 9. 遇到的挑战和解决方案

以下为设计阶段已识别的挑战、以及实现过程中补记的解决方案（含「复用优先」整改与沉淀闭环返工）。

| 挑战 | 解决方案 |
|---|---|
| **数据字典与实际数据不一致**（T1、T2），生成代码易按直觉写错列名与类别枚举 | 把 T1–T4 全部抽成 `Dataset.known_issues` 与能力节点，验证期做 schema 断言，失败后按列名表定向修复，并把修复结果回写为可复用经验 |
| **时间泄漏**：标签为「下月」违约，随机划分会让模型看到未来信息，指标虚高 | 时间外划分 + `PRECEDES` 约束强制 `Pipeline` 且 fit 仅 on train + AST 静态泄漏检查；test 集仅在终评使用一次 |
| **无大模型 / 无额度时 demo 跑不起来** | `BaseLLM` 抽象 + `MockLLM` 规则模板为默认路径，真实 LLM 仅作增强，prompt 模板与输出 schema 落盘以保证确定性 |
| **生成代码不可信** | 独立子进程沙箱 + 超时 / 内存限制 + AST import 白名单 + 临时目录 + 禁读标签路径；网络库（`socket` / `urllib` / `requests` / `httpx`）不在白名单内，生成代码无法 import 出网 |
| **内存上限曾是纸面约束**：Windows 下 venv 的 `python.exe` 是 redirector，会再拉起真正的解释器子进程，只读父进程 RSS 只有 4MB 左右，看门狗永远不触发 | 改为对整棵进程树求和（`psutil.children(recursive=True)`），超限时按进程树终止；报告中峰值内存从 4MB 级假数据变为 170MB 级实测值，并新增 `test_peak_memory_covers_whole_process_tree`、`test_memory_limit_is_enforced` 两个回归用例 |
| **知识图谱容易沦为静态展示** | 检索结果强制进入 Planner / Coder prompt，`PRECEDES` 参与验证，并做「有 KG / 无 KG」消融对比写入报告 |
| **修复退化为反复重试** | 先做错误分类再按签名定向修复，最多 3 轮，每轮记录 `(错误签名, 修复动作, 结果)` 三元组 |
| **敏感属性与公平性** | 敏感字段不入模，仅用于分组 AUC 审计，README 明确不作部署建议；把公平性做成 `Metric` 插件 |
| **数据时效与分布漂移** | 用 PSI 指标 + 时间外验证量化漂移，作为「真实行业落地复杂问题」写入报告，不回避 |
| **小数据下资源分析缺说服力** | 构造 10× 合成扩展集，记录各候选耗时 / 峰值内存 / 推理 P95 |
| **指标口径不统一** | 成本比、KS 门槛、baseline 定义全部配置化到 `verify_*.yaml`，避免硬编码 |
| **早期为快速打通闭环写了若干自研轻量件，与开发要求 f「可使用现成工具但需说明选择理由」有张力** | 中途把「复用优先」写进 `.codebuddy/rules/architecture.md` 作为不可裁剪规则，逐项评估现成方案后替换：自研状态机 → LangGraph `StateGraph`、`ctypes` 内存监控 → `psutil`、手写日志格式 → `structlog`、`argparse` → `Typer`、手写 Markdown 正则 → `markdown-it-py`、手写词元计数 → `rank_bm25`；`vcrpy` / `bandit` / CrewAI / LlamaIndex 评估后因粒度或契约冲突未采用，理由逐项写在第 2 节选型表。全部替换以「功能不变」验收：ruff 全绿、测试全过（当时 104 个用例，当前 128 个）、图谱仍 95 节点 / 259 边、端到端 3 候选 AUC 与修复轨迹逐字一致 |
| **真实仓库的 docstring 格式不统一**：`scorecardpy` 用 `Params` 段、参数说明还跨行，部分函数完全没有结构化段 | 解析器同时接受 `Params` / `Parameters` / `Args`，跨行说明取首行；无结构化段时用签名兜底。81 个函数全部产出能力描述，其中 21 个有结构化参数——差异如实写进第 3 节，不补造内容 |
| **跨场景迁移暴露隐藏耦合**：数据集路径写死取全局 `paths.data`，文本任务仍去读信用卡 CSV 而报 `KeyError: 'label'`；两场景都写 `outputs/generated/candidate_plan.*.py`，后跑的覆盖先跑的 | 数据集路径改为 `dataset.path` 优先、全局配置兜底；新增 `--run-id` / `--kg-out` / `--gen-dir`，让两个场景的代码、图谱、报告、轨迹互不覆盖；场景差异收敛到 `verify_*.yaml` 与 `templates.py` 两处 |
| **候选排序默认「越大越好」**：换成回归后主指标是 RMSE，原实现会把最差候选排到第一 | 打分按指标 `direction` 归一（`minimize` 取负号），原始值仍原样存在 `metrics`；`test_end_to_end_ranks_by_minimized_metric` 用「排序后的 RMSE 必须单调不减」守住这条语义 |
| **跨平台 lint 盲区**：本地 `ruff` 全绿，CI 首跑却在代码规范步骤挂掉——`scripts/download_data.py` 带 shebang 但索引里是 100644，`EXE001` 只对 POSIX 文件模式生效，Windows 看不到 | 用 `git update-index --chmod=+x` 置为 100755（保留 shebang 与直接执行能力），并把 ruff 输出改成 `--output-format=github`，失败时具体文件与规则直接进 check-run 注解，不必拉日志 |
| **知识图谱一开始是单场景的**：文本任务检索到的是信用卡域约束，`PAY_0`、成本比 5:1 这些噪音会进 Planner / Coder prompt | `verify_*.yaml` 增加 `knowledge.docs`，工作流按场景抽独立子图；两套材料结构一致（适用条件表 / 验收门槛表 / `FR-xx`），抽取器与检索器代码零改动即支持第二领域 |
| **沉淀只写不读**：Curator 已把结果写入 `capabilities_after_run.json`，但工作流每轮都从源材料重抽，下一轮看不到上一轮经验 | 让 `Workflow` 启动时优先加载回写图谱（不存在才回退源材料），检索器优先返回本项目实测 `FailureCase`，Coder 命中 T1 历史经验时首轮即避开，Curator 按 `run_id` 去重避免膨胀。消融实测：修复轮次 2（有 KG）vs 3（无 KG）、有 KG 首轮避开 `PAY_1`、两组 AUC 完全一致 |

---

## 10. 后续可扩展方向

1. 以真实向量检索替换 BM25，保留可解释打分作为对照；
2. 用 MCTS 替代 Beam Search，比较方案搜索效率与最终指标；
3. 增加 PSI 漂移监控与能力自动降级策略；
4. 从真实业务仓库持续增量抽取，形成能力版本谱系与血缘追踪；
5. 扩展回归、多标签、时序任务的验证插件，成为多任务能力工厂；
6. 引入成本敏感多目标优化，同时优化 AUC、成本损失与公平性约束；
7. 对接在线评分服务的部署配置（OpenAPI 文档已由 FastAPI 自动生成并导出为 `outputs/reports/openapi.json`，见第 5 节 `python -m factory api --export-openapi`；部署配置仍属后续方向）；
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
- [x] P5 补接入层与最终验收指标：FastAPI 三端点 + `outputs/reports/openapi.json`，第 8 节替换为实测数值；Streamlit 前端按裁剪顺序未做（题目「或」已满足）

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
| 算法模板插件 | `e3873f7` | 装饰器注册表 + LR / HGB / RF 三个内置模板；Coder 按 `family` 渲染，修掉候选族被忽略的缺陷，HGB 候选四层达标 |
| 接入层 | `d04c517` | FastAPI 三个端点 + CLI `api` 子命令；OpenAPI 由框架自动生成并导出 `outputs/reports/openapi.json` |
| 收尾补强 | `db58c34`、`6c04b87`、`5a8e214` 及本次提交 | 文档按实测回填并消除自相矛盾；资源基准与内存看门狗修复；真实开源仓库 AST 抽取；文本分类跨场景迁移 |

> 完整历史以 `git --no-pager log` 为准。所有提交时间由 Git 按实际提交时刻记录，未做调整；评审可据此还原 P0 → P3 的演进。

---

## 附录 E · 交付物对照表（题目「交付内容」逐条索引）

### 基础要求（11 项）

| # | 题目交付物 | 本仓库对应位置 |
|---|---|---|
| 1 | 完整的项目代码库 | 仓库根目录；`factory/` 六层 82 个文件，git 历史按 P0 → P6 分阶段提交 |
| 2 | 示例行业数据、文档或模拟业务材料 | `assets/data/{UCI_Credit_Card.csv, sms_spam.csv, synthetic_demand.csv}`；`assets/docs/`（6 份主场景材料 + `text/` 3 份文本材料）；`assets/legacy/legacy_default_model.py` |
| 3 | 能力知识图谱 schema 设计说明 | 第 3 节：9 类节点 / 13 类关系 / 六要素落地映射 / 按场景拆分子图 |
| 4 | 知识抽取结果文件（JSON / CSV / GraphML） | `outputs/kg/capabilities.json`、`capabilities.csv`、`graph.graphml`；文本场景 `text_capabilities.*`、`text_graph.graphml`；真实仓库 `repo_capabilities.*`、`repo_graph.graphml` |
| 5 | Agent 工作流代码或流程配置 | `factory/workflow/pipeline.py`（LangGraph `StateGraph`）+ `factory/agents/roles.py`（8 角色）；流程图见第 4 节 |
| 6 | 至少 1 个从能力描述到代码生成的完整示例 | `outputs/reports/run_demo.md`（能力描述 → 检索证据 → 3 候选 → 代码 → 修复 diff）+ `outputs/generated/candidate_plan.0*.py`；文本 / 回归场景另有 `run_text_demo.md`、`run_regression_demo.md` |
| 7 | 自动验证脚本 | `python -m factory run`；`scripts/verify_baseline.py`；CI `.github/workflows/ci.yml`（lint + 128 用例 + 3 条端到端） |
| 8 | 验证报告样例 | `outputs/reports/`：`run_demo.md`（四层结论 + 候选排名 + 修复轨迹）、`run_text_demo.md`、`run_regression_demo.md`、`validation_sample.md`、`ablation.md`、`resources.md`、`openapi.json` |
| 9 | 项目文档 README.md | `README.md`（十节 + 附录 A–E） |
| 10 | 环境依赖文件 | `requirements.txt`（106 个包；干净 venv 实测无清单外依赖） |
| 11 | 使用示例和测试用例 | 第 5 节命令清单 + `tests/`（14 个文件 / 128 个用例，含泄漏拦截、沙箱、cassette 回放、跨场景等） |

### 进阶与加分证据位置

| 类别 | 证据 |
|---|---|
| 进阶 8 项 | 第 4 节（多轮修复 / 多候选 / 插件式接入 / 三份验证配置）+ 第 8 节（报告样例）；CLI 见 `factory/__main__.py`，API 见 `factory/api/app.py` 与 `outputs/reports/openapi.json` |
| 加分 10 项 | 第 3 节（真实仓库抽取）、第 7 节（生成代码示例）、第 8 节（资源消耗分析、跨场景迁移、消融对比）、第 4 节（Beam Search、8 角色、失败经验复用、版本谱系、设计依据） |

---

本 README 随各阶段实现进度持续更新，每次更新对应一次独立提交。
