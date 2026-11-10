# 端到端运行报告 · live

> 本报告为真实运行的产物，本次**全链路接入真实 LLM**
> （DeepSeek OpenAI 兼容接口，Interpreter / Planner / Coder / Repairer / Curator 实时调用）。
> LLM 生成代码先过 AST 静态检查才采用；指标均为子进程沙箱在真实数据集上的实测，未造数值。
> T1 列名错误由 LLM 生成代码按直觉写成 `PAY_1`，在子进程用真实数据集触发 `KeyError` 后定向修复。
> test 段仅在候选比较结束后对最佳候选评估一次，不参与排序与修复。引用 cassette 回放的内容须另标注「离线回放」。

- 能力描述：预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。
- 能力理解来源：deepseek_api
- 知识图谱：with_kg（图谱来源 sources）
- 历史失败经验命中：否
- 七步流程：执行完成（a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink 均有产物）
- 四层全通过：**PASS**
- 七步轨迹：a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → e.Execute+Validate → f.Diagnose+Repair → d.Generate → e.Execute+Validate → d.Generate → e.Execute+Validate → g.Sink

> 说明：四层全通过为 FAIL 时，通常是「指标表现」层未达 `verify_credit.yaml`
> 的业务门槛；接口 / 功能 / 稳定性结论见第 3 节，失败记录已回写 FailureCase。

## 0. 输入引导（入口体检）

- 结论：**OK（要素齐全）**，要素完备度 0.83
- 已表达要素：goal、data、constraint
- 缺失要素：metric
- 引导建议：描述要素齐全，可直接进入七步闭环

## 1. 检索证据（进入 Planner / Coder prompt，含 5 条系统级教训）

```text
# 检索证据（query=预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。）
- [0.504] [C6] 标识字段 (cap.risk_policy.C6)
- [0.475] [r04] 禁 ID 入模、禁读标签路径 (metric.test_report.r04)
- [0.435] [E1] EDUCATION 的 0/5/6、MARRIAGE 的 0 统一归入「其他」 (cap.expert_rules.E1)
- [0.435] [E4] 所有预处理器置于 sklearn.Pipeline 内并仅在训练集 fit (cap.expert_rules.E4)
- [0.435] [C5] 敏感字段 (cap.risk_policy.C5)
## 适用条件
- [C1] 客群范围：仅适用于持有 ≥6 期账单历史的存量客户；新客无 `PAY_*` / `BILL_AMT*` 序列，不在适用范围内
- [C2] 额度区间：`LIMIT_BAL` 在本样本覆盖区间内；超出区间需人工复核
- [C3] 时间范围：训练样本观测期为 2005-04 至 2005-09；上线前须做 PSI 群体稳定性检查，PSI > 0.25 触发重训
- [C4] 划分方式：必须时间外划分，禁止随机打乱；所有预处理在训练集内 fit
- [C5] 敏感字段：`SEX` / `AGE` / `EDUCATION` / `MARRIAGE` 不得进入模型特征，仅用于分组公平性审计
## 系统级教训（跨运行成立，生成代码必须遵守）
- [runtime] 内存看门狗永不触发，占用早已超过 2GB 仍判定通过 → 根因：Windows 虚拟环境里的 `python.exe` 是重定向器，读父进程 RSS 只有约 4MB，按单进程计量完全失真 → 处置：改为 `psutil.Process.children(recursive=True)` 对整棵进程树求和，超限即终止子进程（出现 1 次，置信度 0.90）
- [platform] 本地跑通的 CLI 断言在 CI 上随机失败 → 根因：Typer 检测到终端后自动着色，输出里混入 ANSI 转义序列，按纯文本匹配必然失配 → 处置：子进程设 `NO_COLOR=1`、`TERM=dumb`，断言前统一剥离 ANSI（出现 1 次，置信度 0.90）
- [platform] 证据 SHA-256 在 Windows 上校验失败，Linux 正常 → 根因：Git 检出的换行是 CRLF，与原文 LF 不同，同一内容算出不同哈希 → 处置：`read_sources` 读入后归一化换行再计算哈希（出现 1 次，置信度 0.90）
- [validation] 报告写着四层验证，实际只有两层在生效：确定性恒为 True，test 段从未被读取 → 根因：检查项只存在于报告字段里，没有代码真正读取对应输入 → 处置：沙箱支持 `repeat>=2` 的同进程二次 fit 与 `segment="test"`；工作流在候选比较结束后消费一次 test（出现 1 次，置信度 0.90）
- [knowledge] 边很多，但追问「这两点为什么相连」答不出来 → 根因：连边按 `index % len(metrics)` 轮转，与内容无关，属于凑数量 → 处置：改为名称或属性文本命中才连边，宁可边少（出现 1 次，置信度 0.90）
## 历史失败规避项
- KeyError → 按 `Dataset` 节点的列名映射表替换为 `PAY_0`、`PAY_2`…`PAY_6`；禁止按序号硬编码列名
- SchemaError → 0/5/6 归入「其他」类别；`PAY_* = -2` 保留为独立类别；编码前做取值域校验
- LeakageDetected → 改时间外划分；强制 `sklearn.Pipeline` 且所有预处理器仅 on train fit；按 `PRECEDES` 约束检查期次
- CostLossAboveBaseline → 在验证集上按成本加权损失网格搜索最优阈值，测试集不参与调阈
- LeakageDetected → 采样仅在训练集内、且在 Pipeline 内执行
```

## 2. 候选方案比较（Beam Top-3，主指标 auc）

| 方案 | 模型族 | auc | 通过 | 代码来源 | 修复轮次 |
|---|---|---|---|---|---|
| plan.02 | random_forest | 0.7872 | PASS | llm | 0 |
| plan.03 | hist_gradient_boosting | 0.7851 | PASS | llm | 0 |
| plan.01 | logistic_regression | 0.7206 | FAIL | llm | 2 |

## 3. 四层验证结论

| 运行 | 接口 | 功能 | 指标 | 稳定性 | 确定性 Δ | 错误签名 |
|---|---|---|---|---|---|---|
| plan.01 | PASS | PASS | FAIL | PASS | 0.00e+00 | MetricBelowThreshold |
| plan.02 | PASS | PASS | PASS | PASS | 2.22e-16 | 无 |
| plan.03 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |

## 4. 修复轨迹

- 第 1 轮：`KeyError: PAY_1` → 按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）（repaired）
- 第 2 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）

## 设计依据
- 检索证据条目：24
- 候选排名：plan.02 > plan.03 > plan.01
- 修复轨迹：按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）; 检索历史高分方案，切换模型族或按成本比调阈值
- 依据：检索到的适用条件约束候选方案，历史失败规避项触发列名映射修复。

## 5. 终评（test 段，仅一次）

- 终评候选：`plan.02`；test 段本次一次性消费，未参与候选排序与修复决策

| 指标 | test 实测 |
|---|---|
| auc | 0.7853 |
| ks | 0.4355 |
| pr_auc | 0.5657 |
| f1 | 0.4410 |
| cost_weighted_loss | 0.7447 |
| psi | 0.0158 |
| grouped_auc_gap | 0.0201 |

## 6. 图谱沉淀（知识 vs 运行记录）

> 运行记录只用于追溯、可被重跑覆盖；教训跨运行成立，随证据累积置信度。

- 新增节点：6
- 新增边：7
- 运行记录 ValidationRun（本次留痕，可随重跑覆盖）：3
- 失败案例证据合并（独立 run 数累加）：0
- 本次提升为教训（跨运行知识）：0
- 图谱内教训总数：12

- 运行日志另存：`outputs/kg/credit_kg_live_runs.json`（仅追溯，不参与检索）

## 7. 产物

- `outputs/generated/live/candidate_plan.01.py`
- `outputs/generated/live/candidate_plan.02.py`
- `outputs/generated/live/candidate_plan.03.py`
- 回写图谱（知识）：`outputs/kg/credit_kg_live.json`

模式 with_kg（图谱来源 sources）；候选 3 个；修复 2 轮；历史失败经验命中 否；检索证据 5 项已注入 Planner 与 Coder prompt。
