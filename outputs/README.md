# outputs 产物地图

本目录全部是**运行产物**，不是源码。文件较多但只有四类：知识图谱、生成代码、报告、运行轨迹。
标「入库」的随仓库提交（交付物 / 报告样例），其余可由命令重建，可以安全删除。

## kg/ · 知识图谱

| 文件 | 内容 | 入库 | 重建命令 |
|---|---|---|---|
| `capabilities.json` / `.csv` / `.graphml` / `.cypher` | 主场景（信用卡）材料抽取结果，四种格式同一份图 | 是 | `python scripts/build_kg.py` → `python scripts/export_cypher.py` |
| `capabilities.db` | 节点 / 边 SQLite 表，供版本谱系查询 | 否 | 同上 |
| `kg.html` | 交互式可视化（JS/CSS 内联，断网可直接打开） | 是 | 同上 |
| `text_capabilities.*` / `text_graph.graphml` / `text_kg.html` | 短信场景子图（含共享的工程教训） | 是 | `python scripts/build_text_kg.py` |
| `repo_capabilities.*` / `repo_graph.graphml` | `scorecardpy` 真实仓库抽取的 81 个公开能力 | 是 | `python scripts/extract_repo.py` |
| `capabilities_after_run.json` | **回写后的知识图谱**：能力 + 失败案例 + 教训 | 是 | `python -m factory run ...` |
| `capabilities_after_run_runs.json` | 本轮**运行日志**（不参与检索，只追溯） | 是 | 同上 |
| `capabilities_{text,regression}_after_run.json` | 其他场景的回写图谱 | 是 | 带 `--kg-out` 运行 |
| `capabilities_lesson_demo*.json` | 知识沉淀三轮演示（第 1 次攒证据 → 第 2 次提升教训 → 第 3 次被检索命中） | 是 | 见 README 第 8 节 |

## generated/ · 生成的算法代码

| 路径 | 内容 |
|---|---|
| `candidate_plan.0{1,2,3}.py` | 主场景三个候选的最终源码（默认规则模板；接真实 LLM 时可能是 LLM 生成） |
| `text/candidate_plan.0*.py` | 短信分类场景 |
| `regression/candidate_plan.0*.py` | 需求量回归场景 |

代码来源记录在报告「候选方案比较」表的“代码来源”列（`template` / `llm`），不靠文件名猜。

## reports/ · 报告与文档

| 文件 | 内容 |
|---|---|
| `run_demo.md` | **主场景端到端报告**（交付物样例）：七步轨迹、检索证据、候选排名、四层结论、修复轨迹、图谱 diff |
| `run_text_demo.md` / `run_regression_demo.md` | 跨场景迁移报告 |
| `run_lesson_demo_{1,2,3}.md` | 知识沉淀三轮，展示教训如何提升与被检索命中 |
| `ablation.md`、`run_ablation.{with,without}_kg.md` | 有 / 无知识图谱消融 |
| `validation_sample.md` | 四层验证报告样例 |
| `resources.md` | 1× / 10× 资源与性能基准 |
| `openapi.json` | 接口文档（`python -m factory api --export-openapi`） |

## runs/ · 运行轨迹

不入库。`trace_<run_id>.json` 是每次运行的七步状态与候选明细，随时可删；
`outputs/reports/` 与 `outputs/kg/` 里的交付物不依赖它。

## 想全部重新生成

```bash
python scripts/build_kg.py && python scripts/build_text_kg.py && python scripts/extract_repo.py
python scripts/export_cypher.py
python -m factory run --spec "预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。"
python scripts/run_ablation.py && python scripts/verify_baseline.py && python scripts/resource_benchmark.py
```

只想知道「哪个文件该看」：主报告 `reports/run_demo.md`、生成代码 `generated/candidate_plan.01.py`、图谱可视化 `kg/kg.html`。
