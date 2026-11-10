# AGENTS.md

> 跨工具入口。**正文以 `.codebuddy/rules/` 为唯一事实来源**，本文件只做索引与摘要；若与规则冲突，以后者为准。
> CodeBuddy 用户请直接看 `.codebuddy/CODEBUDDY.md`（项目说明）与 `.codebuddy/rules/*.md`（工作区规则）。

## 项目是什么

基于 AI Agent 的算法能力工厂原型：从业务材料抽取**能力知识图谱** → 按自然语言描述**规划并生成算法代码** → 四层**验证** → 按错误签名**修复** → 结果**回写图谱**。行业场景为信用卡下月违约预测（UCI，30000 行）。

当前状态：a–g 七步闭环、P4 沉淀闭环、算法模板插件、FastAPI 接入层与 OpenAPI 均已落地，1.1.1 完成了真实 LLM 通路的健壮性修复，1.2.0 补上入口输入引导，1.3.0 把知识沉淀分成「教训」与「运行日志」两层，1.4.0 统一了产物命名，1.4.1 完成真实 LLM 全链路实测并修正报告页眉与 lint 范围，1.9–1.10 补上搜索消融与 Reviewer 反馈环，1.11.0 让阈值策略真正生效（`cost_optimal`）、候选排序接入成本损失、LLM 补丁过复验才算修复；245 个用例全过、`ruff` 全绿、干净虚拟环境实测可复现。

## 文档分工

- `README.md` 只承载题目要求：背景目标、架构与选型、KG schema、工作流、环境运行、数据与任务、生成代码、验证结果、挑战、扩展方向，加附录 A（十项对照）/ B（交付物索引）/ C（数据引用）。
- 开发过程、阶段与提交对照、团队协作约束、内部规划留在本文件与 `.codebuddy/rules/`，不再往 README 里堆。
- 实测明细一律以 `outputs/reports/*.md` 为准，README 只写结论与链接，避免两处数字漂移。

## 常用命令

```bash
python -m venv .venv && pip install -r requirements.txt   # 干净环境
python -m factory run --spec "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"
python -m factory run --spec "..." --mock                 # 全链路规则模板
python -m factory guide                                    # 输入引导菜单
python -m factory guide --spec "随便写点什么"               # 只体检描述，不跑闭环
python -m factory api --export-openapi                     # 导出 OpenAPI 文档
python scripts/build_kg.py                                 # 能力图谱与检索产物
python scripts/run_ablation.py                             # 有 KG / 无 KG 消融
python scripts/record_llm.py                               # 录制真实 DeepSeek 调用（需 key）
python -m unittest discover -s tests -v                    # 全量测试
ruff check factory scripts tests
```

## 硬约束（摘要）

1. **四层验证缺一不可**：接口规范、功能正确性、指标表现、运行稳定性。
2. **图谱必须真正参与**：检索结果要进入 Planner 与 Coder 的 prompt，不能只做静态展示。
3. **生成代码必须在子进程沙箱执行**：超时、内存上限、AST import 白名单；数值以 `configs/default.yaml` 的 `runtime` 段为准。
4. **模块间只通过 `factory/contracts/` 的数据类交互**，不跨层直接依赖实现细节。
5. **换任务不改核心验证器**：新增 `verify_*.yaml` + 指标插件 / 算法模板插件即可。
6. **有现成的不要重复造轮子**：先查现成库或标准库；确需自研时在 README 选型表写明「评估过什么、为何不用」。
7. **修复先分类错误签名再定向处理**，最多 3 轮；每轮结果回写图谱。
8. **test 集仅终评使用一次**；指标门槛一律以 `verify_*.yaml` 为准，不硬编码。

## Git 规范

- Conventional Commits：`<type>(<scope>): <简述>`，body 说明「为什么」，每个阶段独立提交。
- 单人开发直接推 `main`；多人协作或需要评审时再启用 feature 分支 + PR（合并用 merge commit，不用 Squash）。
- **发布动作**：每次 `git push origin main` 成功后必须执行 `python scripts/tag_release.py`，按 `factory.__version__` 创建并推送 annotated tag `v<version>`；禁止 force 覆盖已推送 tag。规则见 `.codebuddy/rules/git-commit.md`。
- 红线：**禁止 force push `main`**、**禁止改写已推送提交**。
- 提交前确认 `.env`、`PLAN.md`、`assets/data/raw/`、`_archive/` 均未被跟踪。

## 开发阶段与提交对照

历史按 P0 → P6 分阶段独立提交（Conventional Commits + body 说明「为什么」），未改写任何已推送提交。演进主线：P0 骨架与规范 → P1 能力图谱与检索 → P2 沙箱与四层验证 → P3 三种 LLM 后端与 a–g 七步闭环 → 按「复用优先」把自研件替换为现成库 → P4 沉淀闭环 → 算法模板插件 → 接入层 → 收尾补强 → 1.1.x 真实性整改。最后一阶段不是推翻前期工作，而是在对外契约、产物与测试行为不变的前提下换成成熟实现。

| 阶段 | 代表性提交 | 内容 |
|---|---|---|
| P0 骨架与规范 | `7844ad8`、`0cc7f60`、`4c79d44`、`b108259` | 仓库初始化、示例数据、契约骨架、配置与业务材料、项目级规则 |
| 规范校准 / LLM 路线 | `71b9d75`、`020e665`、`6450a45`、`aa3dacf`、`dc4c148`、`cee2ed0` | 按 `llm_agent.md` 原文区分硬要求与设计选择；确定 DeepSeek API + cassette |
| P1 能力图谱 | `3463084`、`4dcff63` | 9 类节点 / 13 类关系、证据哈希、NetworkX + SQLite、混合检索、PyVis |
| P2 验证框架 | `9f7b6c4`、`6625bee`、`d1ce37b`、`1126ee9` | 交付 JSON 去时间戳改内容哈希、AST 静态检查 + 子进程沙箱、指标插件 / 时间外划分 / 四层检查器 / 报告 |
| 分支与流程调整 | `5f3290b`（PR #1，merge commit）、`20b70ac`、`7fe4f98`、`0b936d8` | 早期 feature 分支 + PR，单人开发后改为直推 `main`，两处 merge commit 保留分支节点 |
| P3 LLM 后端 | `3ceb961`、`ecd9e69`、`1a0148f` | 三种后端、脱敏 cassette 与断网回放、一次真实 DeepSeek 调用证据 |
| P3 七步闭环 | `677ab5b`、`4a6e5c6`、`208bbd7` | 8 角色、Beam Top-3、≤3 轮定向修复、Curator 回写、`run --spec` 与端到端产物 |
| 复用优先整改 | `5f26a87`、`379f7aa`、`f064a1b`、`82f6d4f` | 现成库替换基础设施 / 检索 / 解析；LangGraph 替换自研状态机；同步选型理由 |
| P4 沉淀闭环 | `c642c24` | 工作流优先加载回写图谱、检索优先实测失败经验、Coder 首轮避开 T1、回写去重 |
| 算法模板插件 | `e3873f7` | 装饰器注册表 + LR / HGB / RF 模板，Coder 按 `family` 渲染 |
| 接入层 | `d04c517` | FastAPI 三端点 + CLI `api` 子命令 + 导出 OpenAPI |
| 收尾补强 | `db58c34`、`6c04b87`、`5a8e214` | 文档按实测回填、资源基准与内存看门狗修复、真实仓库 AST 抽取、文本跨场景迁移 |
| 1.1.x 真实性整改 | `1.1.0` / `1.1.1` 两次提交 | 确定性重复 fit、test 终评接线、Coder 采用 LLM 代码、KG 边按文本命中、失败经验跨轮复用、Planner / Coder prompt 补输出契约 |
| 1.2.0 入口输入引导 | `1.2.0` 一次提交 | 新增 `factory/intake/` 与 `IntakeGuidance` 契约：要素体检（OK / CLARIFY / REJECT）、跑题拦截、场景错配提示、能力 id 引用；`guide` 子命令与交互向导、`/intake/guide` 与 `/intake/review`、`/run` 422 结构化引导；结论写入 `RunTrace.intake` 与报告第 0 节 |
| 1.3.0 知识沉淀分层 | `1.3.0` 一次提交 | 新增 `Lesson` 节点与 `LessonRecord` 契约、工程教训库 LE1–LE12、`lessons.py` 教训提炼（独立 run 达阈值提升）、`merge.py` 材料与沉淀合并；检索新增系统级教训段并排除运行日志；交付图谱与 `*_runs.json` 运行日志分离；修复「回写图谱老化」与「occurrences 恒为 1」 |
| 1.4.0 产物命名统一 | `1.4.0` 一次提交 | 新增 `factory/artifacts.py` 单点定义 `<scope>_<kind>[_<variant>]`；图谱 `/ kg`、报告 `/ run`、代码 `/ generated/<scope>/`、轨迹 `/ trace_<scope>_<variant>` 全部改名；`--kg-out` / `--gen-dir` 改为按场景自动推导；`extract_repo` 补齐 cypher 与 html |
| 1.4.1–1.4.2 实测与进阶补齐 | 两次提交 | 真实 DeepSeek 全链路实测（8 次实时调用，3 候选代码全为 LLM 生成）；修报告页眉动态化与 ruff 排除生成代码；新增 `plugins/` 外部插件自动发现与 `POST /run.task_config`，进阶 8 项逐项对照表 |
| 1.4.3 路径规范与标签固化 | `1.4.3` 一次提交 | 修 `RepoExtractor` 把本机绝对路径写进三类图谱产物的问题；全仓路径核查为相对路径；新增 `scripts/tag_release.py` 与「push 后必须打 tag」规则，补齐历史版本标签 |
| 1.4.4 Release 补齐 | `1.4.4` 一次提交 | `tag_release.py` 扩展为 tag + GitHub Release（REST API、CHANGELOG 正文、幂等）；发布动作固化为 push→tag→Release 三步；补齐历史 Release |
| 1.4.5 加分项核查补齐 | `1.4.5` 一次提交 | 加分 10 项逐项对照；补齐能力版本查询 / 对比（`capability_versions.py`）与设计依据因果说明（`Curator.explain`）；如实标注「方案搜索」「性能优化」两项为部分完成 |
| 1.9–1.10 搜索与协作 | `a640962`、`cca398d`、`c38f512` 等 | Successive Halving（单轮粗评）、多跳 BFS 检索、Reviewer 语义评审与反馈环、Repairer 双轨留证 |
| 1.11.0 阈值与修复实质化 | 单次提交 | `cost_optimal` 在 valid 段按成本比扫阈值且终评锁定；`y_pred` 按候选阈值重算（阈值维度真正影响 F1 / 成本损失）；粗评排序改为「主指标 + 成本损失」复合键并在淘汰后重编号；LLM 补丁须过静态检查 + 沙箱复验；`SourceRecorder` 逐角色记录实时 / 回放 / 模板 |

完整历史以 `git --no-pager log` 为准，提交时间由 Git 按实际时刻记录，未做调整。

## 不要做的事

- 不要把 `.env`、key、token 写进仓库文件、日志或 cassette。
- 不要为「通过」而降低 `verify_*.yaml` 门槛，也不要编造指标数值。
- 不要把离线回放说成实时调用；引用回放结果的段落须标注「离线回放」。
- 不要声称已完成实际未做的操作（例如未真正创建的 PR）。
