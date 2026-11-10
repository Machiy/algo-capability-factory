# outputs 产物地图

本目录全部是**运行产物**，不是源码。命名统一为 `<scope>_<kind>[_<variant>].<ext>`，规则定义在
`factory/artifacts.py`：

- **scope**：`credit` / `text` / `regression` / `repo`，跨场景的实验与文档用 `shared`；
- **kind**：`kg`（图谱）、`run`（运行报告）、`candidate`（生成代码）、`trace`（轨迹）；
- **variant**：`after_run`（回写后）、`demo` / `lesson_1` 等运行变体。

标「入库」的随仓库提交（交付物 / 报告样例），其余可由命令重建，可安全删除。

## kg/ · 知识图谱

| 文件 | 内容 | 入库 |
|---|---|---|
| `credit_kg.json` / `.csv` / `.graphml` / `.cypher` / `.html` | 主场景材料抽取结果（四种格式同一份图 + 可视化） | 是 |
| `credit_kg.db` | 节点 / 边 SQLite 表 | 否（`*.db` 忽略） |
| `credit_kg_after_run.json` | **回写后的知识图谱**：能力 + 失败案例 + 教训 | 是 |
| `credit_kg_after_run_runs.json` | 对应**运行日志**（不参与检索，只追溯） | 是 |
| `text_kg.*` / `text_kg_after_run.json` | 短信场景抽取子图与回写图谱 | 是 |
| `repo_kg.*` | `scorecardpy` 真实仓库抽取的 81 个公开能力 | 是 |
| `regression_kg_after_run.json` | 回归场景回写图谱（无专属材料，复用通用知识） | 是 |
| `credit_kg_lesson.json` / `_runs.json` | 知识沉淀三轮演示：第 1 次攒证据 → 第 2 次提升教训 → 第 3 次被检索命中 | 是 |
| `credit_kg_live.json` / `_runs.json` | 真实 LLM 全链路实测的回写图谱与运行日志 | 是 |

## generated/ · 生成的算法代码

```
generated/credit/candidate_plan.0{1,2,3}.py      主场景三个候选（模板 / cassette 基线）
generated/text/…                                 短信分类
generated/regression/…                           需求量回归
generated/live/…                                 真实 LLM 实时生成的三个候选（页眉会标注来源）
```

代码来源看报告「候选方案比较」表的“代码来源”列（`template` / `llm`），不靠文件名猜。

## reports/ · 报告与文档

| 文件 | 内容 |
|---|---|
| `credit_run_demo.md` | **主场景端到端报告**（交付物样例）：七步轨迹、检索证据、候选排名、四层结论、修复轨迹、图谱 diff |
| `text_run_demo.md` / `regression_run_demo.md` | 跨场景迁移报告 |
| `credit_run_lesson_{1,2,3}.md` | 知识沉淀三轮，展示教训如何提升与被检索命中 |
| `credit_run_ablation_{with,without}_kg.md` | 有 / 无知识图谱两组运行的详细报告 |
| `shared_ablation.md` | 两组对比汇总（方法级，可扩展到更多场景） |
| `shared_validation_sample.md` | 四层验证报告样例 |
| `shared_resources.md` | 1× / 10× 资源与性能基准 |
| `credit_run_live.md` | 真实 LLM 全链路实测报告（8 次实时调用，三个候选代码均为 LLM 生成） |
| `shared_openapi.json` | 接口文档（`python -m factory api --export-openapi`） |

## runs/ · 运行轨迹

不入库。`trace_<scope>_<variant>.json` 是每次运行的七步状态与候选明细，随时可删；
`reports/` 与 `kg/` 里的交付物不依赖它。

## 想全部重新生成

```bash
python scripts/build_kg.py && python scripts/build_text_kg.py && python scripts/extract_repo.py
python scripts/export_cypher.py
python -m factory run --spec "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"
python -m factory run --spec "把短信分类为垃圾短信或正常短信，输出准确率与宏平均F1" --mock --task-config configs/verify_text.yaml
python -m factory run --spec "根据多期特征预测日需求量，最小化RMSE，输出RMSE/MAE/R2" --mock --task-config configs/verify_regression.yaml
python scripts/run_ablation.py && python scripts/verify_baseline.py && python scripts/resource_benchmark.py
```

只想知道「哪个文件该看」：主报告 `reports/credit_run_demo.md`、生成代码 `generated/credit/candidate_plan.01.py`、图谱可视化 `kg/credit_kg.html`。
