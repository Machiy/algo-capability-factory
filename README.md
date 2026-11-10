# AlgoCap Factory · 基于 AI Agent 的算法能力工厂

[![ci](https://github.com/Machiy/algo-capability-factory/actions/workflows/ci.yml/badge.svg)](https://github.com/Machiy/algo-capability-factory/actions/workflows/ci.yml)

**一句话**：给它一句中文需求，它从业务材料里查出相关算法能力，规划 3 个候选、生成可运行代码、在沙箱里做四层验证、按错误签名定向修复，最后把踩过的坑沉淀成下次能用的知识。

> 对应题目：《基于 AI Agent 的算法能力系统开发》。行业场景为 UCI 信用卡下月违约预测（30,000 行真实数据，自带列名 / 类别 / 泄漏陷阱，不需要人工埋 bug）。

## 30 秒看懂

| 你给它 | 它给你 |
|---|---|
| 一句自然语言需求，例如「预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。」 | ① 3 份可运行代码 ② 一份四层验证报告（接口 / 功能 / 指标 / 稳定性）③ 一段修复轨迹 ④ 回写到知识图谱的失败经验与教训 |
| 不知道需求怎么写 | `python -m factory guide` 打印要素清单、合格示例与可用场景，不合格的描述直接被拦下 |
| 想换任务（短信分类 / 需求量回归） | 换一份 `--task-config`，核心验证器、沙箱与工作流一行不改 |

**它要解决的三个问题**

1. **算法能力散落在文档、旧代码、专家经验和失败复盘里**，新人复刻一遍等于重踩一遍坑 → 把这些能力抽成图谱，检索结果直接进 Planner / Coder 的 prompt，不是拿来做展示。
2. **LLM 写的代码不能直接信** → 生成代码只在子进程沙箱跑（超时、内存上限、AST import 白名单），并且必须过四层验证才算通过。
3. **失败经验用完就丢** → 失败按错误签名累积，独立运行中出现 ≥2 次才升级为「教训」，写清根因 / 处置 / 预防，下次运行自动注入。

**和「直接让 LLM 写代码」的区别**

| | 直接问 LLM | 本项目 |
|---|---|---|
| 依据 | 模型记忆 | 从你的材料里检索出的能力、约束与历史失败项，带证据哈希 |
| 正确性 | 看运气 | 子进程沙箱实测 + 四层验证，指标门槛写在 yaml 里 |
| 失败后 | 重新问一遍 | 按错误签名定向修复（≤3 轮），并回写为可复用经验 |
| 换任务 | 重新写 prompt | 换 `verify_*.yaml`，验证器与沙箱不动 |
| 断网 / 无 key | 不可用 | 默认 `MockLLM` + 已入库 cassette，全程离线可复现 |

**不想装环境？先看这几份现成结论**

| 想知道 | 打开 |
|---|---|
| 一句话需求如何一步步变成可运行代码 | [`outputs/reports/run_demo.md`](outputs/reports/run_demo.md) |
| 生成的代码长什么样 | [`outputs/generated/candidate_plan.01.py`](outputs/generated/candidate_plan.01.py) |
| 知识图谱长什么样 | 浏览器打开 `outputs/kg/kg.html`，或看第 3 节的 JSON 示例 |
| 实测指标与四层结论 | 第 8 节 |

**你是哪类读者**

- **评审 / 面试官**：第 1 节（做什么）→ 第 2 节（怎么分层）→ 第 4 节（Agent 怎么跑）→ 第 8 节（实测结果）→ 附录 A（十项要求对照）。
- **想跑起来**：直接跳到下面「快速上手」，三条命令出结果。
- **想接新场景**：第 5 节的配置说明 + 第 4 节的入口引导 + 第 6 节的测试任务表。

## 目录

| 章节 | 回答什么问题 |
|---|---|
| 快速上手 | 三条命令怎么跑出结果？跑完看哪几个文件？报错怎么办？ |
| 核心闭环 | 从一句话到产物，中间经过哪几步？ |
| 1. 项目背景和目标 | 为什么要做、做成什么样算成功 |
| 2. 系统架构和模块设计 | 六层怎么分、为什么这么选、题目点名的工具各自用没用 |
| 3. 能力知识图谱 schema 和示例 | 10 类节点 / 13 类边、六要素怎么落、知识怎么和日志分开 |
| 4. Agent 工作流设计 | 8 个角色、状态机、四层验证、修复策略、教训怎么沉淀 |
| 5. 环境配置和运行方法 | 装环境、跑分阶段脚本、主要产物在哪、真实 LLM 怎么接 |
| 6. 示例数据和测试任务说明 | 用了哪些数据、材料长什么样、三个测试任务、已知陷阱 |
| 7. 生成算法代码示例 | 生成的代码片段与实现约束 |
| 8. 验证结果和报告样例 | 实测指标、消融、知识沉淀三轮、性能、跨场景迁移 |
| 9. 遇到的挑战和解决方案 | 16 个真实问题与处理方式 |
| 10. 后续可扩展方向 | 还能往哪里做 |
| 附录 A / B / C / D | 十项要求对照、交付物索引、数据引用、术语表 |

> **项目状态**：v1.3.0（变更见 [`CHANGELOG.md`](CHANGELOG.md)，阶段与提交对照见 [`AGENTS.md`](AGENTS.md)）；`ruff` 全绿、179 个用例通过；CI 覆盖 Python 3.11 / 3.12 与三条端到端；最近一次实测最佳候选 `random_forest` 四层全 PASS（valid AUC 0.7899，test AUC 0.7883）。

---

## 快速上手（5 分钟，断网可跑）

> 前提：Python 3.11+。无需 GPU、Docker、数据库，也无需 API key——数据和 LLM 回放文件都在仓库里。

### 第 1 步：拿到代码并装依赖

```bash
git clone https://github.com/Machiy/algo-capability-factory.git
cd algo-capability-factory
python -m venv .venv
.venv\Scripts\activate              # Windows；Linux/macOS 用 source .venv/bin/activate
pip install -r requirements.txt
```

### 第 2 步：跑一次

```bash
python -m factory run --spec "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"
```

终端会打印（真实输出，节选）：

```text
[P3] 七步闭环执行完成；四层全通过=True 理解来源=cassette 候选=3 修复=1 报告=outputs/reports/run_demo.md
  plan.02: auc=0.7899049146031963 passed=True repairs=0
  plan.03: auc=0.784336717195967 passed=True repairs=0
  plan.01: auc=0.7206124391247685 passed=False repairs=2
  修复[1] KeyError: PAY_1 -> 按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）
  修复[2] MetricBelowThreshold -> 检索历史高分方案，切换模型族或按成本比调阈值
```

修复轮次取决于有没有历史图谱：仓库自带回写图谱时为 **1 轮**（T1 经验命中，首轮就避开 `PAY_1`）；删掉 `outputs/kg/capabilities_after_run.json` 再跑为 **2 轮**（现场触发 `KeyError: PAY_1` → 定向修复 → 再处理指标层）。

### 第 3 步：看结果（三个文件）

| 文件 | 看什么 |
|---|---|
| `outputs/reports/run_demo.md` | 主报告：七步轨迹、检索证据、候选排名、四层结论、修复轨迹、图谱 diff |
| `outputs/generated/candidate_plan.0{1,2,3}.py` | 三个候选的最终源码（可直接阅读） |
| `outputs/kg/kg.html` | 知识图谱可视化，浏览器直接打开 |

想看「为什么会失败又怎么修好的」：删掉 `outputs/kg/capabilities_after_run.json` 重跑，报告第 4 节会出现 `KeyError: PAY_1 → 按 Dataset 列名映射把 PAY_1 改为 PAY_0`。`PAY_1` 是首轮按直觉命名习惯生成的列名，报错由子进程在真实数据集上抛出（数据字典里最近一期实为 `PAY_0`，即 T1），再由 `Repairer` 定向修复——注入的是命名习惯，错误本身不是伪造的。

### 其余常用命令

| 想做什么 | 命令 |
|---|---|
| 不知道需求怎么写 | `python -m factory guide`（要素清单 + 合格示例 + 可用场景） |
| 只体检一条描述，不跑闭环 | `python -m factory guide --spec "随便写点什么"` |
| 换短信分类场景 | `python -m factory run --spec "把短信分类为垃圾短信或正常短信，输出准确率与宏平均F1" --mock --task-config configs/verify_text.yaml --run-id text_demo --kg-out capabilities_text_after_run.json --gen-dir text` |
| 换需求量回归场景 | `python -m factory run --spec "根据多期特征预测日需求量，最小化RMSE，输出RMSE/MAE/R2" --mock --task-config configs/verify_regression.yaml --run-id regression_demo --kg-out capabilities_regression_after_run.json --gen-dir regression` |
| 全链路规则模板（最稳） | 在任意命令后加 `--mock` |
| 跑全量测试 / 检查代码规范 | `python -m unittest discover -s tests` / `python -m ruff check .` |

### 卡住了怎么办

| 现象 | 处理 |
|---|---|
| `pip install` 失败 | 确认 `python -V` ≥ 3.11；建议新建 venv 后重装 |
| 提示数据文件缺失 | 仓库已内置数据；也可 `python scripts/download_data.py` 重新拉取 |
| Windows 终端中文乱码 | PowerShell 先执行 `$env:PYTHONIOENCODING="utf-8"` |
| 生成的报告打不开 / 想定位产物 | 产物目录见第 5 节「主要产物」表 |
| 想接真实 LLM | `cp .env.example .env`，填 `LLM_API_KEY` 并设 `LLM_PROVIDER=openai_compat`；不带 `--mock` 运行才读 `.env` |
| 想知道自己能写什么需求 | 第 4 节「入口引导」；三档结论分别是直接跑、给追问、直接拦下 |

---

## 核心闭环

> 本节回答：从一句话到产物，中间经过哪几步。

```
自然语言能力描述
   ↓ 0 引导                 IntakeGuide → OK / CLARIFY / REJECT（缺什么要素、是否换场景）
   ↓ a 理解                 Interpreter → CapabilitySpec
   ↓ b 检索                 Retriever  → 能力子图 / 约束 / 历史失败经验
   ↓ c 规划                 Planner    → Beam Top-3 候选方案
   ↓ d 生成                 Coder      → 可运行代码（build_pipeline 契约）
   ↓ e 验证                 Verifier   → 四层验证（接口 / 功能 / 指标 / 稳定性）
   ↓ f 修复                 Repairer   → 错误签名定向修复，最多 3 轮
   ↓ g 沉淀                 Curator    → 失败案例按签名累积 → 教训提升 / 能力 v+1，运行日志另存
                              ↓
                     验证报告 + 候选排名 + 设计依据 + 图谱 diff
```

最短路径：`pip install -r requirements.txt` → 上方「快速上手」第 2 步即可跑通全链路。`--mock` 使用内置规则模板 LLM，全程离线；去掉该参数并配置 `.env` 即切换真实 LLM，细节见第 5 节。

---

## 1. 项目背景和目标

> 本节回答：为什么要做这个系统，做成什么样算成功。

真实行业中的算法能力往往分散在业务文档、历史代码仓库、专家经验、实验记录和测试报告中，包括数据预处理方法、模型选择经验、特征工程策略、评价指标、失败案例、调参经验与业务约束。本项目构建一个小型「算法能力工厂」原型，把这些能力自动抽取为结构化知识并沉淀到能力图谱，再由多智能体协作完成算法复刻与自动验证。

**目标**：

1. 验证「能力抽取 — 能力复刻 — 能力验证 — 能力沉淀」核心闭环，而非仅做一次性代码生成；
2. 让知识图谱**真实参与**检索、规划、生成与验证，而非静态展示；
3. 让验证结果**驱动**定向修复，并让失败经验**回写**后可在下一轮被检索命中；
4. 在断网、无本地大模型、无 GPU、无 API key 的环境中完整复现端到端运行（默认 `MockLLM` + 脱敏 cassette 回放）。

**场景选择**：信用卡客户下月违约预测。原题场景列表为开放式举例（「例如……等」），本场景合规；选它是因为业务约束丰富（成本矩阵、合规、群体稳定性、公平性）、指标族完整、数据集自带真实数据质量陷阱，可产生无需人为埋 bug 的真实失败修复轨迹。

---

## 2. 系统架构和模块设计

> 本节回答：代码分几层、每层管什么、为什么不用别的框架。

| 层 | 模块 | 职责 |
|---|---|---|
| L0 契约 | `contracts/` | `CapabilitySpec`、`CandidatePlan`、`ValidationReport`（Pydantic），全系统唯一数据协议 |
| L1 知识 | `knowledge/` | Schema、材料抽取器、真实仓库 AST 抽取器、NetworkX 图 + SQLite、混合检索、教训提炼（`lessons.py`）、图谱合并（`merge.py`）、PyVis 可视化 |
| L2 Agent | `agents/`、`workflow/` | 8 个角色、LangGraph 状态机、Beam Search、修复策略表 |
| L2 支撑 | `llm/` | `BaseLLM` 抽象与三实现：`MockLLM`（默认）、`OpenAICompatLLM`（DeepSeek）、`RecordedLLM`（cassette 回放） |
| L3 执行 | `runtime/` | 子进程沙箱、AST 静态检查、超时 / 内存限制、错误分类器 |
| L4 验证 | `validation/` | 四层检查器、指标插件注册、报告生成 |
| L5 接入 | `cli/`（`__main__.py`）、`api/`、`intake/` | Typer CLI、FastAPI；`intake/` 在入口做输入体检与引导（要素追问、跑题拦截、换场景提示）；Web UI 按裁剪顺序未做，题目「或」已由 CLI + API 满足 |
| L6 资产 | `assets/` | 数据、业务材料、模板、示例、报告样例与 LLM cassette |

**设计原则**：契约先行（模块间只依赖 Pydantic 数据类）、LLM 可替换、验证与场景解耦（换 yaml 即换任务）、执行与验证隔离（生成代码只在子进程沙箱内运行）。

**技术选型与理由**（对应开发要求 f；末列记录「先查现成库」的评估结论）

| 组件 | 选择 | 理由 | 评估过的现成方案 / 未采用原因 |
|---|---|---|---|
| LLM | `BaseLLM` 抽象：`MockLLM` / `OpenAICompatLLM` / `RecordedLLM` | 默认 mock 保证断网复现；本地 CPU 跑开源模型过慢，按开发要求 g 的「API 调用方式」接 DeepSeek | LangChain / LlamaIndex 的 LLM 包装只需一行配置即可替代，不必引入整套链路；`openai` SDK 已直接使用 |
| 编排 | LangGraph `StateGraph` | 条件边、状态传递与循环上限由框架提供，8 个角色作为节点动作 | 曾自研轻量状态机，按「有现成的不要重复造轮子」已替换；AutoGen / CrewAI 的 `Agent` / `Task` 会接管 LLM 调用链，破坏「检索证据显式进 prompt」与 `MockLLM` 默认路径 |
| 知识图谱 | NetworkX（GraphML / Cypher）+ SQLite | 零部署、可直接交付 GraphML / CSV；另导出 Cypher，需要时用 `cypher-shell` 导入 Neo4j | Neo4j 需 Docker 服务，伤「本地一键复现」；百节点级规模用 NetworkX 足够 |
| 检索 | `rank_bm25.BM25Okapi` + 一跳图邻域扩展 | 相关性由现成库计算，权重来自 `configs/default.yaml`；Top-K 命中后按边类型加权（`EVALUATED_BY` / `USES` 1.0，`APPLIES_TO` 0.4） | 手写词元计数已替换；LlamaIndex retrievers 需向量库或 LLM，离线成本高 |
| Markdown 解析 | `markdown-it-py` | 章节 / 表格 / 代码块结构由现成解析器识别，原始行仍作证据摘录 | 手写正则已替换；LlamaIndex loaders 过重且改动证据哈希口径 |
| 沙箱资源监控 | `psutil` + 标准库 `subprocess` | 跨平台读取子进程内存；POSIX 另有 `RLIMIT_AS` 硬限制 | `ctypes` 手写 Win32 结构已替换；RestrictedPython / Docker 过重 |
| 日志 | `structlog` + 标准库 `logging` | 结构化渲染用现成库，模块内仍用 `getLogger(__name__)` | 手写 `basicConfig` 格式已替换 |
| 静态检查 | 标准库 `ast` + 配置驱动白名单 | 规则全部来自 `default.yaml` / `verify_*.yaml` | `bandit` 只查通用漏洞，抓不到禁 `ID` 入模、`build_pipeline` 签名等项目规则，且会改变 `StaticCheckResult.checks` |
| 真实仓库抽取 | 标准库 `ast` + `RepoExtractor` | 只需签名 / module 级依赖 / docstring / 行号证据四类信息 | `griffe` / `pydoc-markdown` 映射到本项目契约仍需同等适配；`radon` / `pydeps` 不产出能力描述 |
| cassette 回放 | `RecordedLLM`（按角色 + prompt 命中） | 无 key、断网原样回放；未命中显式报错，不静默造假 | `vcrpy` 拦截 HTTP 层，而 `provider=cassette` 根本不构造 `openai` client |
| 四层验证 | 自研组合器 + `pytest` + 子进程沙箱 | 题目要的是「统一验证机制」这一组合，无单一库覆盖；指标用 `sklearn.metrics`、报告用 `Jinja2` | 无对应单一库，组合编排属项目职责 |
| 项目业务规则 | 时间外划分、禁 `ID` / 敏感字段、T1–T4 列名映射、成本比阈值、证据 SHA-256、`verify_*.yaml` 门槛 | 场景合规约束，通用库不会内置 | 无对应现成库 |
| 接入 | Typer CLI + FastAPI | 现成框架，CLI 有 `--version` / `--check` / `guide` / `run` / `api`，API 五端点并自动导出 OpenAPI | `argparse` 已替换；Streamlit 权衡后未做——题目为「或」，只增依赖不增评分点 |
| 输入引导 | 自研规则引擎 `factory/intake/` | 判据是项目特定语义（目标 / 数据 / 指标 / 约束是否表达、描述更像哪个场景），结论要同时进终端、API 与报告 | Guardrails / NeMo Guardrails 面向 LLM 输出安全与对话流程，需额外模型与配置；Pydantic 只校验字段类型与字符集，覆盖不到「要素完备度」与「场景错配」 |
| 知识沉淀 | 自研教训层 `factory/knowledge/lessons.py`（签名规则表 + 提升逻辑） | 需要「错误签名 → 根因 → 处置 → 预防」的项目特定映射、可解释的置信度，且必须离线可复现 | MLflow / W&B 记录的是 run 级指标与参数，正是「日志」，不做知识抽象也不会进 prompt；Neo4j / RDF 推理需要额外服务与 schema，本项目规模用不上；LangGraph 的 checkpoint 只存会话状态，不区分知识与日志 |
| 算法栈 | pandas + scikit-learn + imbalanced-learn | 全 CPU、秒级、确定性强，`Pipeline` 天然防泄漏 | 算法模板用标准库 `str.format`，不为单文件模板引入 Jinja2（Jinja2 仅用于报告） |

### 题目点名工具：用了哪些、为什么（逐项对照）

题目给出的可选工具清单较长，这里逐项说明「用 / 不用」与理由，避免「到底用了什么」需要读者自己从代码里猜。

| 工具 | 是否采用 | 落在哪里 | 选择理由 |
|---|---|---|---|
| **LangChain** | 部分采用：用同一生态的 **LangGraph**（+ `langchain-core` 依赖） | `factory/workflow/pipeline.py` 的 `StateGraph`；`requirements.txt` | 本项目真正需要的是「确定性状态机 + 条件边 + 循环上限」，LangGraph 是 LangChain 官方的图编排层，正好对应；**不用** LangChain 的 Agent / Chain，因为它会把 LLM 调用链与 prompt 拼装藏进框架，破坏「检索证据显式进 Planner / Coder prompt」这一评分点，也让 `MockLLM` 默认路径与单测变复杂 |
| **LlamaIndex** | 未采用 | — | 强项是文档索引 + 向量检索；本项目要求检索**可解释**（BM25 分值 + 图邻域加权，权重写在 yaml）、**离线**（不依赖 embedding 服务），它的 LLM / retriever 包装又会与 `BaseLLM` 抽象重复 |
| **AutoGen** | 未采用 | — | 面向「多 Agent 自由对话」；本项目 8 个角色是确定性节点，每个都有输入输出 schema，便于单测与复现。对话式编排难以保证「检索结果必然进入 prompt」 |
| **CrewAI** | 未采用 | — | 同上。role / goal 配置适合开放式协作，但无法约束「必须先检索再规划」，也无法让同一份 `RunTrace` 逐节点回放 |
| **OpenAI API** | 采用（OpenAI 兼容协议，默认接 DeepSeek） | `factory/llm/openai_compat.py`；`configs/default.yaml` 的 `llm.base_url` | 只需一次 Chat Completions 调用，`openai` SDK 即标准客户端；用兼容端点便于换供应商（改 `LLM_BASE_URL` 即可），key 只从环境变量读取 |
| **本地开源模型** | 未采用 | — | CPU 环境跑 7B 级模型单次响应超分钟级，与 60s 沙箱预算冲突；题目允许 API 方式；同时默认 `MockLLM` 保证无模型、断网也能复现全链路 |
| **Neo4j** | 未采用服务，但提供导入文件 | `outputs/kg/*.cypher`（`scripts/export_cypher.py`） | 需要 Docker 服务，与「本地一键复现」冲突；百节点级规模用 NetworkX + SQLite 足够。为覆盖交付物里的「Neo4j 导入文件」，额外导出 Cypher：把 `outputs/kg/capabilities.cypher` 交给 `cypher-shell` 即可导入，不引入驱动依赖 |
| **NetworkX** | 采用 | `factory/knowledge/graph.py`（属性图构建、`GraphML` 导出）；`pyvis` 做可视化 | 零部署、纯 Python，属性图与 MultiDiGraph 语义足够表达能力—算子—指标—失败案例；导出 GraphML 可交给任意图工具查看 |
| **SQLite** | 采用 | `factory/knowledge/graph.py` 的 `persist_sqlite`（`outputs/kg/*.db`） | 标准库自带，用来承载节点 / 边表，供版本谱系与验证记录按 SQL 查询，不引入数据库服务 |
| **FastAPI** | 采用 | `factory/api/app.py`（`/health`、`/templates`、`/intake/guide`、`/intake/review`、`/run`，并自动导出 OpenAPI） | 题目要求「API 或 Web UI」；FastAPI 自带 OpenAPI 文档与 Pydantic 校验，正好复用项目已有的契约模型，交付物里还能附一份 `openapi.json` |
| **Streamlit** | 未采用 | — | 题目为「或」，CLI（Typer）+ REST API 已覆盖自动化验收与集成两种用法；再引入一个前端框架只增加依赖，不增加评分点 |

> 库级别的更细理由（为什么换掉自研状态机、为什么用 `rank_bm25` / `markdown-it-py` / `psutil` / `structlog`）见上方选型表；「评估过什么、为何不用」也逐行写在那里。

**仓库结构**

```
algo-capability-factory/
├── README.md  CHANGELOG.md  AGENTS.md  requirements.txt  .env.example  pyproject.toml  .gitignore
├── configs/     default.yaml + verify_{credit,text,regression}.yaml
├── factory/     48 个模块：contracts / knowledge / agents / llm / runtime / validation / workflow / intake / api
├── scripts/     数据准备、图谱构建、Cypher 导出、消融、资源基准、仓库抽取、cassette 录制（11 个）
├── assets/      data/、docs/(+text/)、legacy/、repo/scorecardpy/、llm_cassettes/
├── outputs/     generated/、reports/、kg/（产物地图见 outputs/README.md；runs/ 不入库）
└── tests/       17 个测试文件 / 179 个用例
```

内部规划文档（`PLAN.md`）、原始数据包与 `_archive/` 不纳入版本控制。

---

## 3. 能力知识图谱 schema 和示例

> 本节回答：知识存成什么形状、一条能力长什么样、知识怎么和运行日志分开。

**节点（10 类）**

| 节点 | 关键属性 |
|---|---|
| `Capability` | id、name、version、task_type、input_schema、output_schema、constraints、source_ref、status、hash |
| `Operator` | Imputer / Encoder / WOEBinner / Sampler / Scaler / Model / ThresholdTuner / FairnessAuditor |
| `Algorithm` | family、hyperparams、lib_deps、code_template_ref |
| `Metric` | name、direction、applicable_task、threshold、plugin_ref |
| `Dataset` | columns、target、split_policy、known_issues |
| `Environment` | python_version、packages、seed、resource_limit |
| `ValidationRun` | run_id、candidate_id、metrics、passed、duration、peak_memory（**运行日志**，可丢弃） |
| `FailureCase` | error_signature、fix_strategy、run_ids、occurrences（单次现象，按签名累积） |
| `Lesson` | scope、symptom、root_cause、action、prevention、applies_to、occurrences、confidence（**系统级知识**） |
| `Evidence` | path、excerpt、sha256、doc_type |

**知识 ≠ 日志（1.3.0）**：`ValidationRun` 只说明「某次跑了什么」，可被同一 run 重跑覆盖，并且**不参与检索**；`Lesson` 回答「什么条件下会遇到什么现象、为什么、怎么处置、怎么预防」，随独立 run 数累积置信度并注入 Planner / Coder 的 prompt。两者在 schema、检索与产物文件三个层面分开：

| 层面 | 运行日志 | 系统级知识 |
|---|---|---|
| Schema | `ValidationRun`（`attributes.run_id`） | `Lesson` + `FailureCase`（按签名累积） |
| 检索 | 排除，不占 prompt 名额 | 教训单独一段注入，实测教训优先 |
| 产物 | 同目录 `*_runs.json`，仅追溯 | `<kg>.json` 主图，可直接复用 |

**边（13 类，与 `factory/contracts/knowledge.py` 的 `EdgeType` 枚举一致）**

| 边组 | 用途 |
|---|---|
| `REQUIRES`、`USES`、`EVALUATED_BY`、`APPLIES_TO`、`DEPENDS_ON`、`EVIDENCED_BY` | 输入输出、适用条件、评价指标、依赖环境与证据来源 |
| `PRECEDES` | 编码 pipeline 顺序与「fit 仅 on train」约束，验证期做静态泄漏检查 |
| `HAS_RUN` → `RESULTED_IN` → `FIXED_BY` | 沉淀闭环：`Capability → ValidationRun(日志) → FailureCase → Capability(v+1)` |
| `DERIVED_FROM` | 版本谱系，以及 `Lesson ← FailureCase` 的教训溯源 |
| `TRANSFERABLE_TO`、`SIMILAR_TO` | 跨场景迁移、检索邻域扩展 |

**六要素落地**

| 题目要素 | 本场景内容 |
|---|---|
| 算法能力 | WOE 分箱与评分卡 LR、还款状态序列特征、未文档化类别清洗、负数账单处理、类别不平衡与成本敏感阈值、PSI 稳定性、公平性审计 |
| 输入输出 | 输入 23 维结构化特征；输出违约概率 `pd` ∈ [0,1]、阈值标签、标准评分卡分数 |
| 适用条件 | 额度区间、需 ≥6 期账单历史、样本期 2005-04 至 2005-09、敏感字段使用限制、漏报/误报成本比 5:1、最低 KS 门槛、仅作辅助决策 |
| 评价指标 | AUC、KS、PR-AUC、F1、成本加权损失、PSI、分组 AUC |
| 依赖环境 | Python 3.11、pandas / scikit-learn / imbalanced-learn，纯 CPU，固定 seed，60s / 2GB 上限 |
| 历史验证结果 | 每轮 `ValidationRun` 的指标、耗时与内存（日志层）；由失败案例按签名提升的 `Lesson`（知识层：根因 / 处置 / 预防 / 置信度） |

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

**按场景拆分子图**：`verify_*.yaml` 的 `knowledge.docs` 指向该场景材料目录，工作流从中抽独立子图，检索只命中本场景的约束与失败经验——避免「文本任务拿到 `PAY_1` 列名约束」这类跨域噪声。**但工程教训库例外**：`knowledge.shared_docs` 让它进入每个场景，系统级知识不按业务领域切分。

| 场景 | 材料 | 子图规模 | 产物 |
|---|---|---|---|
| 信用卡违约（主） | `assets/docs/`（7 份）+ `assets/legacy/` | 108 节点 / 200 边 / 36 类能力 / 12 条教训 | `capabilities.json`、`graph.graphml`、`capabilities.cypher`、`kg.html` |
| 短信垃圾过滤 | `assets/docs/text/`（3 份）+ 共享教训库 | 30 节点 / 27 边 / 10 类能力 / 12 条教训 | `text_capabilities.json`、`text_graph.graphml`、`text_capabilities.cypher`、`text_kg.html` |
| 真实开源仓库 `scorecardpy`（MIT） | `assets/repo/` | 95 节点 / 248 边 / 81 个公开能力 | `repo_capabilities.json`、`repo_graph.graphml`、`repo_capabilities.cypher` |

源图谱覆盖 10 类关系（主场景）/ 3 类（仓库子图）；`RESULTED_IN` / `DERIVED_FROM` / `FIXED_BY` 由 Curator 回写补齐，回写后的知识图覆盖 12 类。`HAS_RUN` 只在内存里连接运行日志，日志另存 `*_runs.json`，不写进交付图谱。

**仓库抽取细节**：函数 / 方法 → `Capability`（id `cap.repo.scorecardpy.<module>.<func>`）；docstring `Params` / `Returns` 段 → 结构化参数（21 个函数有，其余用签名兜底）；module 级 import → `Environment`（实测 8 个第三方依赖）；签名行 + docstring 首行 → `Evidence`（`sha256` 可重算）；函数体内点号调用 → `USES`。抽取器只做 `ast.parse`，**不 import、不执行**被抽取代码。复现：`python scripts/extract_repo.py`。

---

## 4. Agent 工作流设计

> 本节回答：一句需求进来后，8 个角色如何接力、失败怎么修、经验怎么写回。

**入口引导（`factory/intake/`，1.2.0）**

自然语言入口最容易失效：用户可能只写「做个预测」，也可能把短信分类的需求提给信用卡任务。因此在 a.Parse 之前加一层规则体检，结论固定为三档：

| 结论 | 触发条件 | 行为 |
|---|---|---|
| `OK` | 必填要素（任务目标 + 输入数据）齐全 | 直接进入七步闭环 |
| `CLARIFY` | 缺必填要素，或描述更像另一个场景 | 照常运行，但打印 / 回传追问与应使用的 `--task-config`，结论写入 `RunTrace.intake` 与报告第 0 节 |
| `REJECT` | 空白、过短、命中闲聊 / 创作模式且完全不沾场景 | 拦在闭环之前，给出可复制的合格示例；CLI 退出码 3、API 返回 422，`--force` 可强制放行 |

可选要素（评价指标、业务约束）缺失只提示不拦；描述里直接引用 `cap.*` 能力 id 时视为复刻已有能力，缺字段由图谱补齐。要素关键词、跑题模式与追问话术在 `configs/default.yaml` 的 `intake` 段，场景名、场景关键词与示例在各自 `verify_*.yaml`——**换场景只改 yaml，判定是纯字符串匹配，不调用 LLM，断网可复现**。三份官方示例由测试锁定，防止引导误伤正常输入。

**八个角色**（不是单次 prompt 生成代码，每个角色有独立 system prompt、输入输出 schema，可独立测试）

| 角色 | 输入 → 输出 |
|---|---|
| Interpreter | 自然语言 → `CapabilitySpec` |
| Retriever | Spec → Top-K 能力子图 + 约束清单 + 历史失败规避项 |
| Planner | Spec + 子图 → N 个 `CandidatePlan`（Beam 宽度 3） |
| Coder | Plan → 可运行代码：LLM 代码先过 AST 静态检查，通过才采用，否则回退模板（`RunTrace.code_sources` 记录来源） |
| Reviewer | 代码 → AST 静态评审（危险 import、泄漏、契约签名） |
| Verifier | 沙箱结果 → 四层 `ValidationReport` |
| Repairer | 错误签名 → 定向修复补丁（不重写全量） |
| Curator | 报告 → 失败案例累积 → 教训提升 + 能力版本 + 日志分离 + 设计依据说明 |

**状态机**

```
IntakeGuide（OK / CLARIFY 放行；REJECT 直接返回引导，不进状态机）
  ↓
Parse → Retrieve → Plan → Generate → StaticCheck → Execute → Validate
                                                       ├─ Pass → Compare → Explain → Sink
                                                       └─ Fail → Diagnose → Repair → Generate (≤3 轮)
```

**统一验证机制（对应题目四层）**

| 层 | 检查内容 |
|---|---|
| 接口规范 | `build_pipeline()` 签名、DataFrame schema、输出列名与 dtype、`pd` ∈ [0,1]、AST import 白名单、禁读标签路径、禁 `ID` 入模 |
| 功能正确性 | 小样本 smoke、无 NaN、单类别 / 全缺失边界输入；**确定性 = 同一子进程内重建并二次 fit，两次输出最大绝对差 < 1e-6**（`workflow.determinism_repeat`，实测差值写进报告第 3 节） |
| 指标表现 | 时间外划分，AUC / KS / F1 / PR-AUC / 成本加权损失在 valid 段比较；**候选比较结束后对最佳候选消费一次 test 段终评**，终评指标只进报告，不参与排序与修复（`workflow.evaluate_on_test`） |
| 运行稳定性 | 子进程超时 60s、内存上限（进程树求和）、推理 P95、异常捕获与分类 |

**错误签名 → 定向修复**

| 错误签名 | 修复动作 |
|---|---|
| `KeyError: PAY_1` | 映射为真实的 `PAY_0`、`PAY_2`…`PAY_6`，写入列名映射能力节点 |
| `SchemaError` | 未文档化类别归入 `others`，`PAY_* = -2` 重编码，记录清洗 `Operator` |
| `LeakageDetected` | 强制 `sklearn.Pipeline`，按 `PRECEDES` 重排，改时间外划分 |
| `MetricBelowThreshold` | 检索历史高分方案 → 切换模型族 / 加采样 / 网格搜成本最优阈值 |
| `ImportError` / `Timeout` / `Nondeterminism` | 换白名单库 / 降采样换轻量模型 / 注入 `random_state` |

每个 `(错误签名 → 修复动作 → 结果)` 三元组先回写为 `FailureCase`（带 `run_ids` 与 `occurrences`），同一签名在**独立 run** 中出现 ≥ `knowledge.lesson_promote_threshold`（默认 2）次后提升为 `Lesson`：写明根因、处置、预防、适用面与置信度，并连 `DERIVED_FROM` 回到失败案例。一个 run 内重跑不会重复计数，因此偶发失败不会被重跑次数"喂"成知识。

**记忆分层：什么该被记住**

| 层 | 内容 | 归属 | 参与检索 |
|---|---|---|---|
| 运行日志 | 本轮每个候选的指标、耗时、是否通过 | `*_runs.json`、`trace_*.json` | 否，不占 prompt 名额 |
| 单次现象 | `FailureCase`：错误签名、当次处置、独立 run 数 | 知识图谱 | 是（历史失败规避项） |
| 系统级知识 | `Lesson`：现象 / 根因 / 处置 / 预防 / 适用面 / 置信度 | 知识图谱 | 是（`## 系统级教训`，实测优先） |
| 能力版本 | `Capability(v+1)`：因哪些签名升版、引用了哪些教训 | 知识图谱 | 是 |

图谱加载方式也随之调整：**本次材料抽取 + 上次回写的运行沉淀合并**。材料是唯一事实来源（改了 `assets/docs/` 立即生效，不会因为"有回写文件"而永远读旧内容），沉淀只继承失败案例、教训与能力版本，`run.*` 日志不进交付图谱。

---

## 5. 环境配置和运行方法

> 本节回答：怎么装、怎么分阶段跑、产物在哪、真实 LLM 怎么接。

**环境**：Python 3.11+（实测 3.12.9），纯 CPU，无需 GPU、无需 Docker、无需数据库服务。

```bash
# 1) 创建环境
python -m venv .venv
.venv\Scripts\activate            # Windows PowerShell；Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# 2) 可选：配置真实 LLM（不配置则用默认 cassette / mock 路径）
cp .env.example .env              # 填 LLM_API_KEY，并把 LLM_PROVIDER 改成 openai_compat
# 注意：LLM_PROVIDER 默认 mock，只填 key 不会产生请求；只有不带 --mock 才读 .env

# 3) 可选：重新拉取数据（仓库已内置，断网可跳过）
python scripts/download_data.py

# 4) 端到端命令见上方「快速上手」第 2 步；下面是分阶段入口
python scripts/build_kg.py               # 主场景能力图谱与检索产物
python scripts/build_text_kg.py          # 文本场景子图
python scripts/verify_baseline.py        # baseline 四层验证自检
python scripts/run_ablation.py           # 有 KG / 无 KG 消融对比
python scripts/resource_benchmark.py     # 1× / 10× 资源消耗与性能基准
python scripts/extract_repo.py           # 真实开源仓库函数 / 依赖 / 能力抽取
python scripts/export_cypher.py          # 知识图谱导出 Cypher（Neo4j 导入文件）
python scripts/record_llm.py             # 录制真实 DeepSeek 调用（需 key）

# 5) 接入层与自检
python -m factory guide                  # 输入引导：要素、示例、可用场景、已沉淀能力
python -m factory guide --spec "随便写点什么"   # 只体检一条描述，不跑闭环
python -m factory api --export-openapi   # 导出 OpenAPI 到 outputs/reports/
python -m factory api --port 8000        # /health、/templates、/intake/guide、/intake/review、/run
python -m factory --version
python -m factory --check
python -m unittest discover -s tests -v
```

**主要产物**

| 路径 | 内容 |
|---|---|
| `outputs/generated/{,text/,regression/}candidate_*.py` | 生成 / 修复后的算法代码 |
| `outputs/reports/run_*.md` | 四层验证报告、候选排名、修复轨迹、设计依据 |
| `outputs/kg/capabilities_after_run.json` | 回写后的**知识图谱**：能力 + 失败案例 + 教训（不含运行日志） |
| `outputs/kg/capabilities_after_run_runs.json` | 本轮**运行日志**：仅追溯用，不参与检索 |
| `outputs/kg/graph.graphml`、`kg.html` | 回写后的能力图谱与可视化 |
| `outputs/runs/trace_*.json` | 七步流程可回放轨迹（运行时临时产物，不入库） |
| `assets/llm_cassettes/*.json` | 脱敏后的真实 LLM 对话与响应，供离线回放（入库） |

**最小依赖**：核心闭环需 `pydantic`、`PyYAML`、`pandas`、`scikit-learn`、`networkx`、`langgraph`、`rank-bm25`、`markdown-it-py`、`psutil`、`structlog`（全部为现成库，`requirements.txt` 已锁版本区间）；`pyvis`、`Jinja2`、`Typer`、`openai` 按入口加载。全量清单 23 个直接依赖，含传递依赖共 106 个安装包。

**干净环境实测（P5 记录）**：空 venv 仅执行一次 `pip install -r requirements.txt`（无冲突），随后跑通 `ruff check`（全绿）、端到端 `factory run`（`四层全通过=True`、退出码 0），未安装任何清单外依赖；P6、1.1.x、1.2.0 与 1.3.0 均未新增第三方依赖（教训提炼与日志分离只用标准库 + 现有 pydantic），当前全量测试 179 个。

**持续集成**：`.github/workflows/ci.yml` 用 matrix 并行 **Python 3.11**（最低版本）与 **3.12**（本地实测版本），各自执行 `ruff check`、全量单元测试与三条端到端（信用卡 / 短信 / 回归），断言 `四层全通过=True`。端到端走默认 provider（Interpreter 用已入库 cassette），CI 不依赖任何 API key。

**关于 LLM**：默认配置是「`Interpreter` 走 cassette（真实 DeepSeek 录制响应），其余角色走规则模板」——能力理解由真实 LLM 驱动，其余环节保持确定性；`llm.role_providers` 控制按角色路由，`--mock` 强制全链路规则模板。本地部署模型在 CPU 上过慢，因此按开发要求 g 的「API 调用方式」接入 **DeepSeek 的 OpenAI 兼容接口**。

**凭据与录制回放**：`LLM_API_KEY` 只从环境变量 / `.env` 读取，`.gitignore` 已排除 `.env` 与 `.env.*`；key、token、Authorization header 不会写入仓库文件、日志或 cassette。真实响应脱敏后落盘 `assets/llm_cassettes/`（当前 2 条 Interpreter 录制，回放一致性由 `tests/test_cassette_replay.py` 离线校验）；1.1.1 另做过一次全链路实时复测，真实出站调用 7 次（Planner 1、Coder 3、Repairer 2、Curator 1），结论见 `CHANGELOG.md`。回放未命中按 `cassette.on_miss` 显式报错或回退 `MockLLM`，不静默造假；引用回放结果的报告段落均标注「离线回放」。

**配置说明**：三份 `verify_*.yaml` 均为 `status: active`，全部端到端跑通——`verify_credit.yaml`（表格二分类，主指标 AUC）、`verify_text.yaml`（文本分类，accuracy）、`verify_regression.yaml`（回归，RMSE，`direction: minimize`）。切换任务只换 `--task-config`，核心验证器、沙箱与工作流代码不改。

---

## 6. 示例数据和测试任务说明

> 本节回答：用了什么数据、模拟材料有哪些、三个测试任务分别验证什么。

**主数据集**：UCI Default of Credit Card Clients（Yeh & Lien, 2009，DOI `10.24432/C55S3H`），30,000 实例、23 特征 + 1 标签，正例约 22.1%。UCI 页面标注 **CC BY 4.0**，OpenML `d/43435` 提供 **CC0** 版本，均可随仓库分发。

| 字段组 | 列 |
|---|---|
| 标识 | `ID`（禁止入模） |
| 额度 | `LIMIT_BAL` |
| 人口属性 | `SEX`、`EDUCATION`、`MARRIAGE`、`AGE`（敏感属性，仅用于公平性审计） |
| 还款状态 | `PAY_0`、`PAY_2` … `PAY_6` |
| 账单 / 付款金额 | `BILL_AMT1`…`BILL_AMT6`、`PAY_AMT1`…`PAY_AMT6` |
| 标签 | `default.payment.next.month` |

**其他数据集**：短信分类用 UCI SMS Spam Collection（CC BY 4.0，5,574 条，spam 13.4%，按 60/20/20 固定种子切分，文本任务无时序语义故用 `random_holdout`）；回归用 `make_regression` 合成需求量（3,000 × 8，固定种子，配置中如实标注非真实业务数据）。

**模拟业务材料（对应题目背景的能力来源）**

| 文件 | 类型 | 提供的能力 |
|---|---|---|
| `docs/risk_policy.md`、`docs/data_dictionary.md` | 业务文档 | 成本比、额度区间、字段字典、适用条件 |
| `legacy/legacy_default_model.py` | 历史代码仓库 | 旧评分卡实现、依赖、可抽取函数 |
| `repo/scorecardpy/` | 真实开源仓库（MIT） | 13 个模块 / 81 个函数的签名、依赖、docstring 与行号证据 |
| `docs/expert_rules.md`、`docs/experiment_log.md` | 专家经验 / 实验记录 | WOE 分箱、还款状态衍生、阈值经验、历史调参结果 |
| `docs/test_report.md`、`docs/failure_review.md` | 测试报告 / 失败复盘 | 失败案例、泄漏事故、指标口径 |
| `docs/engineering_lessons.md` | 工程教训库（跨场景共享） | LE1–LE12 系统级坑点：现象 / 根因 / 处置 / 预防 / 适用面 |
| `docs/text/{sms_data_dictionary,sms_policy,sms_failure_review}.md` | 文本场景材料（3 份） | 字段与 ST1–ST4 问题、S1–S6 条件与门槛、FR-01/02 复盘 |

**已知数据陷阱**（核心领域知识与真实失败案例来源）

| 编号 | 陷阱 |
|---|---|
| T1 | 字段名为 `PAY_0` 而非直觉的 `PAY_1`，`PAY_1` 不存在 |
| T2 | `EDUCATION` 有未文档化的 0 / 5 / 6；`MARRIAGE` 有 0（54 条）；`PAY_*` 最小 -2 未在数据字典中 |
| T3 | `BILL_AMT*` 可为负；账单期与付款期存在错位 |
| T4 | 标签是「下月」违约，随机划分会引入未来信息泄漏 |

**测试任务**

| 任务 | 配置 | 用途 |
|---|---|---|
| T-credit 信用卡违约二分类（主） | `verify_credit.yaml` | 端到端闭环演示，含 2 轮真实修复（有回写图谱时 1 轮） |
| T-text 短信垃圾文本二分类 | `verify_text.yaml` | 跨场景迁移实测，3 候选全通过，报告 `run_text_demo.md` |
| T-regression 需求量回归 | `verify_regression.yaml` | 第二种任务类型（RMSE / `minimize`），报告 `run_regression_demo.md` |

**数据使用声明**：数据仅用于算法原型研究。敏感字段仅用于分组公平性审计，不构成任何授信或部署建议；样本来自 2005 年 4–9 月单一时段，结论不外推至当前客群。

---

## 7. 生成算法代码示例

> 本节回答：生成的代码长什么样、有哪些硬约束。

`python -m factory run --spec "..." --mock` 会在 `outputs/generated/` 落盘 3 个候选的最终源码，均由 `Coder` 按方案渲染、经 `Reviewer` 静态检查与 `Repairer` 定向修复。

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

首轮 `Coder` 规则模板按直觉把最近一期写成 `PAY_1`（T1 陷阱），在子进程用真实数据集触发 `KeyError: PAY_1`；`Repairer` 按策略表替换为 `PAY_0` 后重新通过沙箱。三个候选由算法模板插件按不同模型族渲染（LR / RF / HGB 各一，族去重后不再出现同族占满 Beam 宽度）。

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

同一 `Coder` 只按 `model_family` + `task_type` 取模板：表格走 `StandardScaler/SimpleImputer`，文本走 `TfidfVectorizer`，没有第二套生成逻辑。实现要点：

1. 所有预处理置于 `sklearn.Pipeline` 内，fit 仅作用于训练集；
2. 特征列由配置与数据字典推导，显式排除 `ID`、标签与四个敏感字段；
3. 不含文件写入、网络访问、危险 import，可在沙箱内重复运行且结果确定；
4. 生成代码在独立子进程中执行，超时与内存上限由 `configs/default.yaml` 控制。

完整的「能力描述 → 检索证据 → 3 个候选 → 代码 → 修复 diff」见 `outputs/reports/run_demo.md`。

---

## 8. 验证结果和报告样例

> 本节回答：实测指标是多少、消融与沉淀带来什么差别、性能边界在哪。

> 以下为一次真实运行的实测结果，不做数值填充或美化。候选按 Beam Top-3 比较不同算法族；未达标候选如实判 FAIL 并回写 `FailureCase`。明细见 `outputs/reports/`。

| 项目 | 实测结果 |
|---|---|
| 七步流程 | a–g 全部执行完成，CLI 退出码 0 |
| 能力理解 | `能力理解来源=cassette`、`spec_id=spec.next_month_default`（真实 DeepSeek 响应，离线回放） |
| 候选方案 | 3 个（三种算法族）：LR 0.72061（FAIL）、**RF 0.78990（PASS）**、HGB 0.78434（PASS） |
| 修复轨迹 | 源材料首轮复现 `KeyError: PAY_1` → 映射为 `PAY_0`，再处理指标层（2 轮）；有回写图谱时 T1 经验命中，仅剩指标层（1 轮） |
| 图谱沉淀 | `capabilities_after_run.json`（知识：112 节点含 13 条教训、14 个失败案例）+ `capabilities_after_run_runs.json`（运行日志 3 条）；失败案例按错误签名去重，教训按签名去重并累积独立 run 数 |
| 确定性实测 | 三个候选同一子进程内二次 fit，两次输出最大绝对差均为 `0.00e+00` |
| test 终评 | 最佳候选 `plan.02` 一次性评估：AUC 0.7883、KS 0.4399、F1 0.4590、PSI 0.0681、分组 AUC 差 0.0201；不参与排序与修复 |
| 代码来源 | 默认 mock 路径全为 `template`（Mock 输出不冒充模型生成）；真实 DeepSeek 下 3 候选有 2 个采用 LLM 代码（`plan.02` AUC 0.78992，可区分于模板 0.78990），采用前均过 AST 静态检查 |
| 输入引导 | 三份官方示例均判 `OK`（完备度 0.83），不被误拦；空白 / 乱码判 `REJECT` 并附可复制示例（CLI 退出码 3、API 422）；缺「输入数据」判 `CLARIFY` 并给出追问；把短信需求提给信用卡任务时提示 `--task-config configs/verify_text.yaml`。结论写入 `RunTrace.intake` 与报告第 0 节 |

**四层验证结论（最佳候选 random_forest）**

| 层级 | 检查项 | 结果 | 说明 |
|---|---|---|---|
| 接口规范 | 契约签名 / AST 白名单 / 禁 `ID` 入模 | PASS | 静态检查 |
| 功能正确性 | smoke / 无异常 / 确定性 | PASS | 子进程用真实数据 fit / predict |
| 指标表现 | AUC 0.7899 ≥ 0.78、F1 0.4737 ≥ 0.45、KS 0.4459 ≥ 0.35、分组 AUC 差 0.0067 ≤ 0.10 | PASS | 时间外划分 |
| 运行稳定性 | 超时 60s / 内存 2GB / 确定性 Δ = 0 | PASS | 单次约 2.1–2.6s，峰值内存 150–180MB |

**沉淀闭环消融**（`scripts/run_ablation.py`，唯一变量是是否检索并注入图谱证据）

| 指标 | 有 KG | 无 KG |
|---|---|---|
| 命中历史失败经验 | 是 | 否 |
| 修复轮次 / 是否首轮避开 T1 | 1 / 是 | 2 / 否 |
| 错误签名 | `MetricBelowThreshold` | `KeyError: PAY_1` + `MetricBelowThreshold` |
| 候选 AUC（降序） | 0.789905 / 0.784337 / 0.720612 | 0.789905 / 0.784337 / 0.720612 |

两组 AUC 完全一致，说明沉淀改变的是过程效率而非指标口径；完整对比见 `outputs/reports/ablation.md` 与 `run_ablation.{with,without}_kg.md`。

**知识沉淀实测（三轮，同一份回写图谱）**

| 轮次 | 失败签名 | 图谱变化 | 效果 |
|---|---|---|---|
| 第 1 轮 `lesson_demo_1` | `KeyError: PAY_1`、`MetricBelowThreshold` | 两个失败案例各记 1 个独立 run，不提教训 | 修复 2 轮 |
| 第 2 轮 `lesson_demo_2` | 仅 `MetricBelowThreshold`（T1 已被经验规避） | 该签名达 2 次 → 提升 `lesson.workflow.metricbelowthreshold`（置信度 0.65），连 `DERIVED_FROM` 回到失败案例 | 修复 1 轮 |
| 第 3 轮 `lesson_demo_3` | 仅 `MetricBelowThreshold` | 检索命中上一轮沉淀的教训，`## 系统级教训` 首条即它 | 修复 1 轮 |

教训在第 2 轮末尾沉淀、第 3 轮生效——这是学习闭环的真实时间语义，不虚构「同一轮内自我改进」。复现：

```bash
for i in 1 2 3; do
  python -m factory run --spec "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。" \
    --mock --run-id lesson_demo_$i --kg-out capabilities_lesson_demo.json
done
```

产物：`capabilities_lesson_demo.json`（知识，13 条教训）、`capabilities_lesson_demo_runs.json`（日志）、`run_lesson_demo_{1,2,3}.md`。

**性能与资源消耗**（`scripts/resource_benchmark.py`，1× = 30,000 行，10× = 300,000 行有放回抽样，均取自子进程沙箱）

| 模型族 | 耗时中位数 | 峰值内存 | 推理 P95 | 10× 耗时 | 10× 内存 |
|---|---|---|---|---|---|
| logistic_regression | 2.34 s | 175.14 MB | 0.013 ms/行 | 3.28 s（1.40×） | 352.89 MB（2.01×） |
| hist_gradient_boosting | 2.45 s | 179.17 MB | 0.032 ms/行 | 7.36 s（3.00×） | 330.95 MB（1.85×） |
| random_forest | 5.45 s | 178.32 MB | 0.112 ms/行 | 29.69 s（5.44×） | 355.88 MB（2.00×） |

三者都在 60s / 2GB 沙箱上限内；内存约 2× 主要来自 pandas 常驻。完整口径见 `outputs/reports/resources.md`。

**跨场景迁移（`verify_text.yaml`）**：同一套工作流、沙箱与四层验证器，只换一份任务配置就从表格分类切到文本分类。

| 候选 | 模型族 | accuracy | macro-F1 | 四层 |
|---|---|---|---|---|
| plan.02 | linear_svc | **0.9803** | 0.9564 | 全 PASS |
| plan.01 | logistic_regression | 0.9785 | 0.9535 | 全 PASS |
| plan.03 | complement_nb | 0.9731 | 0.9447 | 全 PASS |

差异收敛到配置与模板两处：`verify_text.yaml` 声明 `text_column`、`knowledge.docs` 与 `candidates.model_families`，`templates.py` 注册 `text_classification.*` 模板；核心验证器、沙箱与工作流**未改**。检索证据也已按场景隔离（报告第 1 节列的是 `S1 文本长度`、`S3 类别不平衡`、`LeakageDetected → 向量器进 Pipeline`，不再是信用卡 `PAY_*` 约束）。修复轮次为 0——文本场景没有表格列名陷阱，失败修复能力由表格场景的 T1 轨迹证明，不硬造失败。

**第二种任务类型（`verify_regression.yaml`）**：主指标 RMSE（`direction: minimize`），用于验证候选排序对指标方向的处理。

| 候选 | 模型族 | RMSE ↓ | MAE ↓ | R² ↑ | 四层 |
|---|---|---|---|---|---|
| plan.02 | ridge | **19.31** | 15.58 | 0.9776 | 全 PASS |
| plan.01 | hist_gradient_boosting_regressor | 28.53 | 22.02 | 0.9511 | 全 PASS |
| plan.03 | random_forest_regressor | 37.01 | 28.33 | 0.9177 | 全 PASS |

打分时对 `minimize` 指标取负号，因此 plan.02 排第一；原始值保留在 `metrics` 里未被污染。报告见 `outputs/reports/run_regression_demo.md`。

---

## 9. 遇到的挑战和解决方案

> 本节回答：踩过哪些真实的坑，每个坑怎么定位与修掉的。

| 挑战 | 解决方案 |
|---|---|
| **数据字典与实际数据不一致**（T1、T2），生成代码易按直觉写错列名与类别枚举 | 把 T1–T4 抽成 `Dataset.known_issues` 与能力节点，验证期做 schema 断言，失败后按列名表定向修复并回写为可复用经验 |
| **时间泄漏**：标签为「下月」违约，随机划分会让模型看到未来信息 | 时间外划分 + `PRECEDES` 约束强制 `Pipeline` 且 fit 仅 on train + AST 静态泄漏检查；test 仅在终评使用一次 |
| **无大模型 / 无额度时 demo 跑不起来** | `BaseLLM` 抽象 + `MockLLM` 规则模板为默认路径，真实 LLM 仅作增强，prompt 与输出 schema 落盘保证确定性 |
| **生成代码不可信** | 独立子进程沙箱 + 超时 / 内存限制 + AST import 白名单 + 临时目录 + 禁读标签路径；网络库不在白名单内，生成代码无法出网 |
| **内存上限曾是纸面约束**：Windows 下 venv 的 `python.exe` 是 redirector，只读父进程 RSS 只有 4MB，看门狗永不触发 | 改为对整棵进程树求和（`psutil.children(recursive=True)`）并超限终止；峰值内存从 4MB 假数据变为 170MB 实测，新增两个回归用例 |
| **知识图谱容易沦为静态展示** | 检索结果强制进入 Planner / Coder prompt，`PRECEDES` 参与验证，并做有 KG / 无 KG 消融写入报告 |
| **修复退化为反复重试；沉淀只写不读、经验只活一轮** | 先分类错误签名再定向修复（≤3 轮）；工作流启动时优先加载回写图谱，`FailureCase` 按 `error_signature` 复用而非按 `run_id` 覆盖 |
| **四层验证里有两项只是标签**：`deterministic` 恒为 True、test 段从未被读取 | 沙箱支持 `repeat>=2`（同进程二次 fit）与 `segment="test"`；工作流在比较结束后对最佳候选消费一次 test，指标只进报告。新增 4 个回归用例 |
| **知识图谱的边看着多、其实语义随机**（`index % len(metrics)` 轮转） | 改为名称 / 属性文本命中才连边，边数 259→188 但每条都能答出「凭什么连」 |
| **Coder 调了 LLM 却不用结果** | LLM 代码先过 AST 静态检查，通过才采用；解析失败、缺 `FEATURE_COLUMNS`、危险 import 均回退模板并记入 `RunTrace.code_sources` |
| **跨场景迁移暴露隐藏耦合**：数据集路径写死、两场景产物互相覆盖、回归主指标方向被忽略 | 路径改 `dataset.path` 优先 + 全局兜底；新增 `--run-id` / `--kg-out` / `--gen-dir`；打分按 `direction` 归一，新增单调性回归用例 |
| **跨平台盲区**：Typer 着色破坏 CLI 断言、CRLF 改变证据哈希、shebang 文件模式差异导致 `EXE001` | 子进程设 `NO_COLOR=1` / `TERM=dumb` 并剥离 ANSI；`read_sources` 归一化换行；`git update-index --chmod=+x` 修正模式 |
| **接口层把用户输入直接当文件名**：`POST /run` 传 `../../x` 可写出产物目录 | 双层校验（接口 Pydantic pattern + 拒绝 `..` → 422；工作流 `_RUN_ID_PATTERN` 兜底 → 退出码 2），API 区分 400 / 500 |
| **早期自研轻量件与「复用优先」有张力** | 逐项评估现成库后替换（LangGraph、`psutil`、`structlog`、`Typer`、`markdown-it-py`、`rank_bm25`），未采用的写入选型表，规则与过程见 `.codebuddy/rules/architecture.md` |
| **用户输入不可控**：描述可能过短、跑题，或把另一个场景的需求提给当前任务，让七步闭环在 a.Parse 就失败并浪费一次完整运行 | 入口加规则体检（`factory/intake/`）：缺要素给追问、跑题直接拦、场景错配直接给 `--task-config`；结论写入报告第 0 节，CLI 与 API 都拿得到。三份官方示例由测试锁定，避免误判 |
| **知识沉淀退化成了日志**：每轮回写 `run_id + 指标 + 报错`，下次既检索不到也用不上，图谱越跑越像流水账 | 新增 `Lesson` 节点承载系统级知识（现象 / 根因 / 处置 / 预防 / 适用面 / 置信度），失败案例按独立 run 数累积后提升；运行日志与知识分文件导出、且日志不参与检索；材料知识与沉淀知识合并加载，避免「有回写文件就永远读旧材料」 |

---

## 10. 后续可扩展方向

> 本节回答：如果继续做，优先补哪几块。

1. 以真实向量检索替换 BM25，保留可解释打分作为对照；
2. 用 MCTS 替代 Beam Search，比较方案搜索效率与最终指标；
3. 增加 PSI 漂移监控与能力自动降级策略；
4. 从真实业务仓库持续增量抽取，形成能力版本谱系与血缘追踪；
5. 扩展多标签、时序任务的验证插件，并接入在线评分服务的部署配置（OpenAPI 已自动生成）；
6. 教训生命周期管理：失效标记（`status: deprecated`）、按场景自动降权、跨项目迁移后的有效性回归。

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

**开发要求 a–g**：a Git 版本控制与清晰提交信息（历史与阶段对照见 `AGENTS.md`）、b 完整文档（本文件）、c 模块化与注释（第 2 节）、d 本地可复现（第 5 节 + 干净环境实测）、e Python 3.11+、f 工具选择理由（第 2 节选型表 + 「题目点名工具：用了哪些、为什么」逐项对照）、g mock LLM 兜底（`--mock` 与 cassette 回放）。

## 附录 B · 交付物对照（题目「交付内容」逐条索引）

| # | 题目交付物 | 本仓库对应位置 |
|---|---|---|
| 1 | 完整的项目代码库 | 仓库根目录；`factory/` 六层 48 个模块，git 历史按 P0 → P6 分阶段提交（对照见 `AGENTS.md`） |
| 2 | 示例行业数据、文档或模拟业务材料 | `assets/data/`、`assets/docs/`（7 份 + `text/` 3 份）、`assets/legacy/`、`assets/repo/scorecardpy/` |
| 3 | 能力知识图谱 schema 设计说明 | 第 3 节：10 类节点 / 13 类关系 / 六要素映射 / 按场景拆分子图 |
| 4 | 知识抽取结果文件（JSON / CSV / GraphML / Neo4j 导入文件） | `outputs/kg/{capabilities,text_capabilities,repo_capabilities}.json` + `.csv` + `*.graphml` + `.cypher`（Cypher 导入脚本）；SQLite 表 `*.db`；回写后的知识图谱 `capabilities_after_run.json`（能力 + 失败案例 + 教训）与运行日志 `capabilities_after_run_runs.json`；教训演进示例 `capabilities_lesson_demo.json` |
| 5 | Agent 工作流代码或流程配置 | `factory/workflow/pipeline.py`（LangGraph `StateGraph`）+ `factory/agents/roles.py`（8 角色）；流程图见第 4 节 |
| 6 | 至少 1 个从能力描述到代码生成的完整示例 | `outputs/reports/run_demo.md`（描述 → 检索证据 → 3 候选 → 代码 → 修复 diff）+ `outputs/generated/candidate_plan.0*.py` |
| 7 | 自动验证脚本 | `python -m factory run`；`scripts/verify_baseline.py`；CI（lint + 179 用例 + 3 条端到端） |
| 8 | 验证报告样例 | `outputs/reports/`：`run_demo.md`、`run_text_demo.md`、`run_regression_demo.md`、`run_lesson_demo_{1,2,3}.md`（知识沉淀三轮）、`validation_sample.md`、`ablation.md`、`resources.md`、`openapi.json` |
| 9 | 项目文档 README.md | 本文件（十节 + 附录 A/B/C） |
| 10 | 环境依赖文件 | `requirements.txt`（23 个直接依赖；含传递依赖共 106 个安装包） |
| 11 | 使用示例和测试用例 | 第 5 节命令清单 + `tests/`（17 个测试文件 / 179 个用例） |

**进阶 8 项**：CLI/API（第 5 节，`factory/api/app.py` 与 `outputs/reports/openapi.json`）、多轮修复与多候选比较（第 4 节）、图谱可视化（`outputs/kg/kg.html`）、自动验证报告（第 8 节）、结果回写（第 4、8 节）、不同任务类型配置（三份 `verify_*.yaml`）、插件式接入（指标插件 + 算法模板装饰器注册）、入口输入引导（第 4 节，`factory/intake/`）。
**加分 10 项**：Beam Search、8 角色多智能体、真实仓库 AST 抽取（第 3 节）、沙箱与 AST 安全检查（第 4、9 节）、失败案例复用与教训沉淀（第 3、4、8 节）、能力版本递增、设计依据生成、跨场景迁移（第 8 节）、OpenAPI 自动生成、资源消耗分析（第 8 节）。

## 附录 C · 数据与引用

```
Yeh, I. C., & Lien, C. H. (2009). Default of Credit Card Clients [Dataset].
UCI Machine Learning Repository. https://doi.org/10.24432/C55S3H
License: CC BY 4.0 (UCI) / CC0 Public Domain (OpenML d/43435)
```

衍生材料 `assets/docs/` 与 `assets/legacy/` 为本项目构造的模拟业务材料，仅用于演示能力抽取流程。开发阶段与提交对照、内部规划文档见 `AGENTS.md` 与 `.codebuddy/rules/`（`PLAN.md` 不入库）。

## 附录 D · 术语表（读正文卡住时回来查）

| 术语 | 在本项目里指什么 |
|---|---|
| 能力（`Capability`） | 一条可复用的算法能力：输入输出、适用条件、指标、依赖、证据 |
| `CapabilitySpec` | 把「那句中文需求」解析成的结构化契约，后续所有角色都读它 |
| 候选（`CandidatePlan`） | 一个待验证的方案：算法族 + 超参 + 特征处理方式 |
| Beam Top-3 | 同时保留 3 个候选比较，而不是只赌一个方案 |
| 四层验证 | 接口规范 / 功能正确性 / 指标表现 / 运行稳定性，缺一不可 |
| 知识图谱（KG） | 能力 + 约束 + 指标 + 失败案例 + 教训组成的图，检索结果会进 prompt |
| 回写（Sink） | 把本轮结果写回图谱，供下一轮检索；对应流程的 g 步 |
| `FailureCase` | 一次失败的现象记录：错误签名、当次处置、出现在哪些运行里 |
| `Lesson` | 跨运行成立的系统级教训：现象 / 根因 / 处置 / 预防 / 适用面 / 置信度 |
| 错误签名 | 对错误做归一化后的标签（如 `KeyError: PAY_1`），用于定向修复与经验复用 |
| 沙箱 | 独立子进程执行生成代码，带超时、内存上限与 AST import 白名单 |
| cassette | 录制好的真实 LLM 响应，断网时按角色 + prompt 命中回放 |
| `MockLLM` | 内置规则模板，不调用任何模型，保证离线与确定性（`--mock`） |
| 时间外划分 | 用过去预测未来，禁止随机打散，避免模型看到未来信息 |
| T1–T4 | 数据集自带的四个真实陷阱：`PAY_0` 列名、未文档化类别、负账单、标签为「下月」 |
