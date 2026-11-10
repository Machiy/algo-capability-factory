# 变更日志

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。每个版本对应一个 annotated tag 与 GitHub Release。

## [1.4.6] - 2026-11-10

修复「一键复现」与「定向修复覆盖面」两处真实缺口。

### 修复

- **`pyproject.toml` 去除 UTF-8 BOM**：文件首字节为 `EF BB BF`，导致 Python 3.11+ 标准库
  `tomllib` 解析失败，`pytest` 直接报 `Invalid statement (at line 1, column 1)` 退出。此前
  CI 用 `python -m unittest` 跑测试因此未暴露，但文档声称的「pytest 全绿」实际无法复现。
  去 BOM 后 `pytest` 可正常启动，`unittest` / `pytest` 两条路径均可用。
- **`Nondeterminism` 从「死签名」变为可触发**：`FourLayerValidator` 此前把确定性失败归入
  `ValidationFailed`，策略表里的 `Nondeterminism` 永远不会命中。现按沙箱实测的
  `repeat_variance >= 1e-6` 独立成签名，`Repairer` 据此注入 `random_state`。
- **`ForbiddenFeature` / `LeakageDetected` 增加确定性源码补丁**：`Repairer` 从任务配置派生的
  禁入模字段集合，按 AST 定位 `FEATURE_COLUMNS` 列表并剔除 ID / 标签 / 敏感字段，不再一律
  `no_change`；`Nondeterminism` 按 AST 给缺 `random_state` 的随机估计器实例化补
  `random_state=42`（已有则幂等跳过）。补丁不调用 LLM，失败字段不写死在修复逻辑里。

### 测试

- 新增 6 个用例：禁入模字段剔除、`LeakageDetected` 复用同一补丁、`random_state` 注入、
  幂等跳过、修复后确定性恢复（沙箱实测 `repeat_variance` 归零）、`Nondeterminism` 签名。
  全量 209 个用例通过，`ruff` 全绿。

### 文档

- README 第 4 节与附录 B 同步「确定性源码补丁」的真实覆盖面，不再写「仅 `KeyError: PAY_1`
  有真实补丁」。

## [1.4.5] - 2026-11-10

按「加分 10 项」逐项核查：10 项全部涉及，其中 2 项只做到「写进图谱 / 模板话术」，本轮补齐读侧与解释质量。

### 补齐（完整 6 项 → 8 项）

- **能力版本管理（第 6 项）**：此前只有 v1→v2 增量节点与 `DERIVED_FROM` 版本链，不能查询。新增 `factory/knowledge/versions.py` 与 `scripts/capability_versions.py`，支持 `--list` 列出有版本演进的能力、`--show` 查看版本链、`--diff` 对比两版属性差异（含 `fixed_signatures` / `lesson_ids`），均可 `--json`。交付图谱里 `cap.data_dictionary.T1.v2` 的查询结果已验证。回滚（切换检索证据源）仍未做，如实写明。
- **设计依据解释（第 7 项）**：`Curator.explain()` 原为 4 行固定话术，连「为什么排除某个候选」都答不出。改为按「评价口径与门槛 → 命中的证据节点 id 与硬约束 → 每个候选的实测指标 / PASS / FAIL → 选择依据与排除原因 → 失败签名与经验复用」组织因果链；纯确定性拼接，不调用 LLM，每句结论可按节点 id 回溯。三场景报告重新生成，报告「设计依据」节已是实测内容。

### 核查与文档

- 附录 A 新增「加分 10 项逐项对照」表：完整 8 项、部分 2 项，逐项列落地位置、自检方式与边界。
- 明确两项「部分」：① 方案搜索是一次生成 N 候选后按指标排序，无迭代扩展 / 剪枝 / 树搜索；检索层的一跳图邻域用于证据排序，不是方案搜索。② `resource_benchmark.py` 只做 1× / 10× 耗时 / 内存 / 推理 P95 测量分析，未做调参 / 降采样 / 缓存 / 并行等优化动作与 A/B 收益。
- 措辞校正：`Beam Top-3` / `Beam 宽度` 改为「Top-N 候选比较（一次生成后按指标排序）」；能力版本「参与检索：是」改为「图谱保留 + 版本查询 / 对比已补齐，回滚未做」。

新增 `tests/test_versions.py`（6 个）与 `tests/test_rationale.py`（5 个），`ruff` 全绿、203 个用例通过。

## [1.4.4] - 2026-11-10

补齐 **GitHub Release**：1.4.3 只把发布动作固化到 tag，漏了 Release 这一步。

- `scripts/tag_release.py` 扩展为「tag + Release」两步：用标准库 `urllib` 调 GitHub REST API，先查 `/releases/tags/<tag>`，404 才 POST 创建；Release 正文直接取 CHANGELOG 对应版本段落，`draft=false`、`prerelease=false`。tag 与 Release 各自幂等，已存在就跳过、绝不覆盖。
- token 只从 `GITHUB_TOKEN` / `GH_TOKEN` / `git credential fill` 读取，不打印、不落盘；缺凭据或 API 失败时返回非 0 并如实提示。支持 `--no-release`、`--dry-run`，补历史用 `--version X --target <sha>` 一次补齐 tag 与 Release。
- `.codebuddy/rules/git-commit.md` 的发布动作改为明确三步：`push → tag → Release`，**缺一视为发布未完成**；`AGENTS.md` 同步。
- 补齐 `v1.2.0`–`v1.4.3` 的 GitHub Release，并由脚本创建 `v1.4.4` 的 tag 与 Release。
- 新增 `tests/test_release.py` 5 个用例（CHANGELOG 段落提取、https/SSH remote 解析、Release 已存在跳过、缺失时创建），不联网。

`ruff` 全绿、192 个用例通过。

## [1.4.3] - 2026-11-10

路径规范化与发布标签固化。

### 路径核查

- 全仓扫描已跟踪文件中的绝对路径 / 盘符 / 本机用户目录，发现一处真实泄漏：`RepoExtractor.scan()` 把 `repo_dir.resolve()` 写进 `RepoScan.root`，于是 `repo_kg.{json,graphml,cypher}` 的 `repository` 属性带了本机盘符开头的绝对路径。
- 改为 `_relative_repo_label()`：优先取相对当前工作区 / 项目根的路径，取不到就退回目录名；产物现在是 `assets/repo/scorecardpy`。新增 `tests/test_repo_extractor.py` 的回归用例，禁止绝对路径再次进入交付物，三份产物已重建。
- 其余核查结论：配置（`default.yaml` / `verify_*.yaml`）、代码（`ROOT / ...`）、报告与图谱产物里的路径均为相对路径；`Path(__file__).resolve().parents[n]` 只用于定位项目根，不是写死绝对路径；`ROOT` 只参与拼接，不落盘为字符串。

### 发布标签固化为动作

- 新增 `scripts/tag_release.py`：读取 `factory.__version__`，校验工作区干净、`HEAD` 已在 `origin/main`、同名 tag 不存在，然后创建 annotated tag `v<version>` 并推送；支持 `--dry-run`、`--version` / `--target` 补历史标签，重复执行幂等，绝不 force 覆盖。
- `.codebuddy/rules/git-commit.md` 新增「版本标签（发布动作，必须执行）」一节：每次 `git push origin main` 成功后立即执行该脚本，push 后未打 tag 视为发布流程未完成；`AGENTS.md` 的 Git 规范同步。
- 仓库已有 `v1.0.0`–`v1.1.1` 标签序列；本次补齐 `v1.2.0` / `v1.3.0` / `v1.4.0` / `v1.4.1` / `v1.4.2`（均指向对应版本提交，已核对 `factory/__init__.py`），并由脚本创建 `v1.4.3`。

`ruff` 全绿、187 个用例通过。

## [1.4.2] - 2026-11-10

按「进阶 8 项」逐项核查后，补齐两处「有机制但不够彻底」的短板，并修正文档与实现不符的表述。

### 补齐

- **插件式接入改为真正不改核心代码**：新增 `factory/plugins.py` 与 `plugins/` 目录，运行时用标准库 `importlib` 扫描 `plugins/*.py`，外部文件里的 `@register` 自动生效；`Workflow` 与 `create_app` 启动时加载，`/templates` 和 `POST /run` 都能看到。此前新增插件仍需在包内显式 import。单个插件失败只记 warning、按路径去重、重复加载幂等。新增 `tests/test_plugins.py` 3 个用例。
- **API 也能换场景**：`POST /run` 新增 `task_config` 字段（默认 `configs/verify_credit.yaml`，白名单校验防路径穿越），传给 `Workflow`；此前换任务只能走 CLI `--task-config`。新增 2 个接口用例。

### 文档校正

- 状态机图原写 `Repair → Generate (≤3 轮)`，实际是 `Repair → Execute`（修复补丁回到沙箱复验），`Generate` 只用于切换下一候选。
- 明确写出：目前只有 `KeyError: PAY_1` 会真正改写源码，其余签名给出策略并复验（`no_change`），不伪造补丁。
- `Beam Search` 改为准确表述「一次生成 N 候选后按主指标排序（无迭代扩展 / 剪枝）」。
- 修正遗留的 `outputs/kg/kg.html` 路径笔误（现为 `credit_kg.html`），并把「进阶 8 项」从一句话改成逐项对照表（含落地位置与自检方式）。

`ruff` 全绿、186 个用例通过。

## [1.4.1] - 2026-11-10

真实 LLM 全链路实测，并修掉这次实测暴露的两个真实性问题。

### 实测

- 清空 `role_providers` 让 Interpreter / Planner / Coder / Repairer / Curator **全部实时调用 DeepSeek**（8 次请求全部 200 OK）；`理解来源=deepseek_api`，三个候选代码来源全部为 `llm`（先过 AST 静态检查才采用）。
- 修复 2 轮：`KeyError: PAY_1` → 列名映射为 `PAY_0`（LLM 自己按直觉写错，子进程在真实数据上实测触发）；`MetricBelowThreshold` → 换族 / 调阈值（该策略本轮 `no_change`）。
- 结果：plan.02 random_forest AUC 0.7872 PASS、plan.03 HGB 0.7851 PASS、plan.01 LR 0.7206 FAIL；test 终评 AUC 0.7853 / KS 0.4355 / PSI 0.0158。
- 产物：`credit_run_live.md`、`outputs/generated/live/candidate_plan.0*.py`、`credit_kg_live.json`。单独落盘，不覆盖离线可复现的样例报告。

### 修复

- **报告页眉说谎**：真实 LLM 运行时，页眉仍写「核心闭环演示走 MockLLM 规则模板路径」。改为按 `interpreter_source` / `code_sources` 动态生成，新增 2 个回归用例。
- **`ruff check .` 扫到 LLM 生成代码**：新生成的 `outputs/generated/live/*.py` 带未使用 import 等风格瑕疵（不影响功能，已过 AST 检查与沙箱实测）。`pyproject.toml` 排除 `outputs/generated`，ruff 只检查手写源码、脚本与测试。

> 实时 LLM 输出不确定，本次数值不代表基线；离线可复现结果仍以 mock / cassette 报告为准。

## [1.4.0] - 2026-11-10

产物命名统一：同一个场景的图谱、报告、代码、轨迹一眼可归，不再需要逐个猜文件名。

### 变更

- **新增 `factory/artifacts.py`**：命名规则单点定义 `<scope>_<kind>[_<variant>].<ext>`。`scope` 取 `credit` / `text` / `regression` / `repo`，跨场景实验与文档用 `shared`；`kind` 取 `kg` / `run` / `candidate` / `trace`；`variant` 是 `after_run`、`demo`、`lesson_1` 等。
- **知识图谱产物**：`capabilities.json` / `graph.graphml` / `kg.html` / `text_capabilities.json` / `text_graph.graphml` / `repo_capabilities.json` 等 → `credit_kg.*` / `text_kg.*` / `repo_kg.*`（每场景 `json` / `csv` / `graphml` / `cypher` / `db` / `html` 六件套）。
- **回写图谱与日志**：`capabilities_after_run.json` → `credit_kg_after_run.json`，日志 → `credit_kg_after_run_runs.json`；其他场景 → `text_kg_after_run.json` / `regression_kg_after_run.json`。
- **报告**：`run_demo.md` → `credit_run_demo.md`，`run_text_demo.md` → `text_run_demo.md`，`run_lesson_demo_1.md` → `credit_run_lesson_1.md`；跨场景实验与文档统一 `shared_` 前缀（`shared_ablation.md`、`shared_resources.md`、`shared_validation_sample.md`、`shared_openapi.json`）。
- **生成代码**：主场景不再平铺在 `generated/` 根下，统一 `generated/<scope>/candidate_plan.0X.py`。
- **运行轨迹**：`trace_<run_id>.json` → `trace_<scope>_<variant>.json`（仍不入库）。
- **CLI 简化**：`--kg-out` / `--gen-dir` 默认按场景自动推导，跨场景只需换 `--task-config`；两个参数保留用于覆盖。`--run-id` 现在只表示变体名（`demo`、`lesson_1`），不再承担场景前缀。
- **`scripts/extract_repo.py`** 补齐 `.cypher` 与 `.html` 产物，三种场景产物结构一致。

### 兼容性

- 这是产物路径的破坏性变更：外部脚本若硬编码旧路径需要改。
- **配置精简**：删除 `knowledge.graph_path` / `sqlite_path` / `extraction_results` 三项——产物路径统一由 `factory/artifacts.py` 推导，避免「配置写一份、代码拼一份」两个命名来源；`knowledge` 段只剩 `shared_docs`、`retrieval` 与教训阈值。
- 全量 179 个用例通过，`ruff` 全绿；三场景端到端重跑，报告与图谱均按新命名落盘。

## [1.3.0] - 2026-11-10

知识沉淀分层：图谱里存的不再是「某次跑出了什么」，而是「系统在什么条件下会怎么坏、为什么、怎么处置」。导师反馈的原话是「你的知识沉淀看起来就是个日志」，这一版把日志与知识在 schema、检索与产物三个层面拆开。

### 新增

- **`Lesson` 节点（第 10 类）与 `LessonRecord` 契约**：`scope`（runtime / data / llm / validation / knowledge / platform / workflow）、`symptom`、`root_cause`、`action`、`prevention`、`applies_to`、`occurrences`、`confidence`。缺根因或缺处置的条目不允许作为教训。
- **工程教训库 `assets/docs/engineering_lessons.md`**：LE1–LE12 条真实系统级坑点（进程树内存口径、CLI ANSI 断言、CRLF 哈希、四层验证只有两层生效、图谱边语义随机、修复退化、路径穿越、回放冒充实测、LLM 代码未采用、确定性靠声明、检索不进 prompt、任务假设写死）。由抽取器折成 `Lesson` 节点，带可重算的证据哈希。
- **`factory/knowledge/lessons.py`**：错误签名 → 系统级教训的确定性映射；失败案例在**独立 run** 中出现 ≥ `knowledge.lesson_promote_threshold`（默认 2）次后提升为教训，置信度随次数递增；教训按 `signatures` 去重、跨运行刷新次数。
- **`factory/knowledge/merge.py`**：图谱加载改为「本次材料抽取 + 上次回写的运行沉淀」合并。材料是唯一事实来源（改了材料立即生效），沉淀只继承失败案例、教训与能力版本。
- **检索注入**：`RetrievalResult.lessons` 新增 `## 系统级教训（跨运行成立，生成代码必须遵守）` 段，进入 Planner 与 Coder 的 prompt；排序为「本任务实测优先 → 出现次数 → 置信度 → 编号自然序」。运行日志（`ValidationRun`）被排除在检索候选之外，不再占用 prompt 名额。
- **产物分离**：`capabilities_after_run.json` 只含知识，运行日志另存 `capabilities_after_run_runs.json`；报告第 6 节改为「图谱沉淀（知识 vs 运行记录）」并给出日志路径。

### 修复

- **回写图谱会老化**：此前一旦存在回写文件就整份加载，新增材料与新增规则永远不生效；现在每次运行都与材料抽取合并。主图谱因此从 95 节点（缺教训）恢复为 108 节点 / 12 条教训。
- **失败案例「经验只活一轮」**：`occurrences` 此前恒为 1，无法区分偶发与系统性问题；现在按独立 `run_ids` 计数，同一 run 重跑不重复计数。

### 测试

- 新增 `tests/test_lessons.py` 14 个用例：种子教训字段完整性、证据可回溯、共享教训跨场景生效、教训注入 prompt、运行日志不进检索、单次失败不提升、独立 run 累积后提升、同 run 重跑幂等、教训去重、报告口径。
- 更新 `tests/test_knowledge.py`（10 类节点 / 8 份材料）与 `tests/test_workflow.py`（知识图与日志文件分离、双文件幂等）。全量 177 个用例通过，`ruff check` 全绿。

### 实测

同一份回写图谱连跑三轮：第 1 轮 2 次修复（`KeyError: PAY_1` + `MetricBelowThreshold`）→ 第 2 轮该签名达 2 次、提升为教训、修复降至 1 轮 → 第 3 轮检索首条即这条教训。报告见 `outputs/reports/run_lesson_demo_{1,2,3}.md`。

## [1.2.0] - 2026-11-10

入口输入引导：用户提交的自然语言描述不再直接灌进七步闭环。导师反馈「用户可能会瞎说」，因此把「引导」做成一层可测试的规则引擎，而不是靠文档提醒。

### 新增

- **`factory/intake/`（L5 接入前的引导层）**：`IntakeGuide.review()` 给出 `OK` / `CLARIFY` / `REJECT` 三档结论，附缺失要素、针对性追问、可复制的合格示例。判定全部是字符串匹配，不调用 LLM，断网可复现。
- **契约 `IntakeGuidance`**：结论、完备度、已表达/未提及要素、问题清单、追问、示例、场景建议；写入 `RunTrace.intake` 并在报告新增第 0 节，证明「输入被体检过」而不是只做终端提示。
- **配置驱动**：要素关键词、跑题模式、追问话术在 `configs/default.yaml` 的 `intake` 段；场景名、场景关键词与示例在各自 `verify_*.yaml` 的 `intake` 段。换场景只改 yaml。
- **场景错配提示**：在信用卡任务里描述短信分类时，直接给出 `--task-config configs/verify_text.yaml`，并把示例换成对应场景的示例。
- **能力 id 引用**：描述里出现 `cap.*` 时视为复刻已有能力，缺字段由图谱补齐，不再追问。
- **CLI**：`factory guide`（菜单 / `--spec` 体检 / `--json`）；`run --spec` 改为可选，留空进入交互向导（非交互环境打印菜单并以退出码 2 结束，不挂起）；新增 `--force` 跳过拦截；拒绝时退出码 3。
- **API**：`GET /intake/guide`、`POST /intake/review`；`POST /run` 前置体检，`REJECT` 返回 422 并携带结构化 `guidance`，`CLARIFY` 照常运行并在响应 `intake` 字段回传结论；`force` 可跳过拦截。

### 测试

- 新增 `tests/test_intake.py` 15 个用例：三份官方示例不被误拦、空白/乱码/跑题拦截、缺要素追问、场景错配、能力 id 引用、工作流前置拦截与报告第 0 节、CLI 菜单与不挂起、API 两个新端点与 422。全量 163 个用例通过，`ruff check` 全绿。

## [1.1.1] - 2026-11-09

真实 LLM 通路实测后的健壮性补丁。mock 路径永远返回结构化 JSON，测不出「模型输出与契约不一致」这一类问题，只有切到 `openai_compat` 才会暴露。

### 修复

- **Planner 空候选导致工作流崩溃**：`_parse` 只认纯 JSON，模型把结果包在 `json` 代码块里时解析失败，`candidates` 为空，工作流在 `generate` 节点 `plans[0]` 处抛 `IndexError`。现在先剥离代码块再解析；空候选按任务配置的算法族兜底并记 warning；`generate` 节点改为可读的 `ValueError`。
- **Planner 缺输出格式约束**：system prompt 只写「结合检索证据规划多个候选算法方案」，从未告诉模型要输出什么结构。现补 JSON 契约。
- **Coder 缺输出格式约束**：生成的代码普遍没有 `FEATURE_COLUMNS` 常量，被契约检查拒收后全部回退模板，「LLM 生成代码」实际上从未生效。prompt 现明确要求：`FEATURE_COLUMNS`（或文本任务的 `TEXT_COLUMN`）、`build_pipeline()`、使用方案指定的 `model_family`、预处理全部放进 Pipeline、只用 import 白名单内的库。

### 实测（真实 DeepSeek，`LLM_PROVIDER=openai_compat`）

| 项目 | 结果 |
|---|---|
| 真实调用 | 7 次（Planner 1、Coder 3、Repairer 2、Curator 1） |
| 四层结论 | 全通过，候选 3、修复 2 轮 |
| LLM 代码采用 | 3 个候选中 2 个采用：`plan.02` AUC 0.78992（模板 RF 为 0.78990，可区分），`plan.01` AUC 0.7643 如实判 FAIL；`plan.03` 无有效响应回退模板 |
| 产物差异 | 采用代码与模板产物相差 149 行，确认不是模板回退 |

### 测试

- 新增 3 个用例：代码块包裹的 JSON 解析、纯文本解析、Planner 兜底候选。全量 148 个用例通过，`ruff check` 全绿。

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
