# AGENTS.md

> 跨工具入口。**正文以 `.codebuddy/rules/` 为唯一事实来源**，本文件只做索引与摘要；若与规则冲突，以后者为准。
> CodeBuddy 用户请直接看 `.codebuddy/CODEBUDDY.md`（项目说明）与 `.codebuddy/rules/*.md`（工作区规则）。

## 项目是什么

基于 AI Agent 的算法能力工厂原型：从业务材料抽取**能力知识图谱** → 按自然语言描述**规划并生成算法代码** → 四层**验证** → 按错误签名**修复** → 结果**回写图谱**。行业场景为信用卡下月违约预测（UCI，30000 行）。

当前状态：a–g 七步闭环、P4 沉淀闭环、算法模板插件、FastAPI 接入层与 OpenAPI 均已落地；104 个用例全过、`ruff` 全绿、干净虚拟环境实测可复现。

## 常用命令

```bash
python -m venv .venv && pip install -r requirements.txt   # 干净环境
python -m factory run --spec "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"
python -m factory run --spec "..." --mock                 # 全链路规则模板
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
- 红线：**禁止 force push `main`**、**禁止改写已推送提交**。
- 提交前确认 `.env`、`PLAN.md`、`assets/data/raw/`、`_archive/` 均未被跟踪。

## 不要做的事

- 不要把 `.env`、key、token 写进仓库文件、日志或 cassette。
- 不要为「通过」而降低 `verify_*.yaml` 门槛，也不要编造指标数值。
- 不要把离线回放说成实时调用；引用回放结果的段落须标注「离线回放」。
- 不要声称已完成实际未做的操作（例如未真正创建的 PR）。
