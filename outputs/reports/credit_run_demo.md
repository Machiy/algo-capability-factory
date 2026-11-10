# 端到端运行报告 · demo

> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径
> （开发要求 g），生成代码在子进程用真实数据集执行，指标均为实测，未造数值。
> T1 列名错误由规则模板模拟 LLM 的直觉命名，并在子进程用真实数据集触发 `KeyError` 后定向修复。
> test 段仅在候选比较结束后对最佳候选评估一次，不参与排序与修复。引用 cassette 回放的内容须另标注「离线回放」。

- 能力描述：预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。
- 能力理解来源：mock
- LLM 后端分布：Coder=规则模板、Curator=规则模板、Interpreter=规则模板、Planner=规则模板、Repairer=规则模板
- 知识图谱：with_kg（图谱来源 sources+after_run）
- 历史失败经验命中：是
- 七步流程：执行完成（a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink 均有产物）
- 四层全通过：**PASS**
- 七步轨迹：a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → d.Generate → e.Execute+Validate → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink

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
- [0.505] [C6] 标识字段 (cap.risk_policy.C6)
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
- [workflow] MetricBelowThreshold → 根因：单一模型族在既有特征下达不到门槛，继续调参的边际收益低于换族或换阈值口径 → 处置：切换模型族或按成本比重选阈值，而不是在同一个族上反复调参（出现 2 次，置信度 0.65）
- [runtime] 内存看门狗永不触发，占用早已超过 2GB 仍判定通过 → 根因：Windows 虚拟环境里的 `python.exe` 是重定向器，读父进程 RSS 只有约 4MB，按单进程计量完全失真 → 处置：改为 `psutil.Process.children(recursive=True)` 对整棵进程树求和，超限即终止子进程（出现 1 次，置信度 0.90）
- [platform] 本地跑通的 CLI 断言在 CI 上随机失败 → 根因：Typer 检测到终端后自动着色，输出里混入 ANSI 转义序列，按纯文本匹配必然失配 → 处置：子进程设 `NO_COLOR=1`、`TERM=dumb`，断言前统一剥离 ANSI（出现 1 次，置信度 0.90）
- [platform] 证据 SHA-256 在 Windows 上校验失败，Linux 正常 → 根因：Git 检出的换行是 CRLF，与原文 LF 不同，同一内容算出不同哈希 → 处置：`read_sources` 读入后归一化换行再计算哈希（出现 1 次，置信度 0.90）
- [validation] 报告写着四层验证，实际只有两层在生效：确定性恒为 True，test 段从未被读取 → 根因：检查项只存在于报告字段里，没有代码真正读取对应输入 → 处置：沙箱支持 `repeat>=2` 的同进程二次 fit 与 `segment="test"`；工作流在候选比较结束后消费一次 test（出现 1 次，置信度 0.90）
## 历史失败规避项
- KeyError: PAY_1 → 按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）
- MetricBelowThreshold → 检索历史高分方案，切换模型族或按成本比调阈值
- KeyError → 按 `Dataset` 节点的列名映射表替换为 `PAY_0`、`PAY_2`…`PAY_6`；禁止按序号硬编码列名
- SchemaError → 0/5/6 归入「其他」类别；`PAY_* = -2` 保留为独立类别；编码前做取值域校验
- LeakageDetected → 改时间外划分；强制 `sklearn.Pipeline` 且所有预处理器仅 on train fit；按 `PRECEDES` 约束检查期次
```

## 2. 候选方案比较（主指标 auc 优先，成本损失收口）

> 阈值列：配置写策略名（如 `cost_optimal`），实际取值是评估段解析出的数值；两者并列，避免把策略名当成本次生效的阈值。

| 方案 | 模型族 | auc | 阈值（配置 → 实际） | 通过 | 代码来源 | 修复轮次 |
|---|---|---|---|---|---|---|
| plan.01 | random_forest | 0.7899 | cost_optimal → 0.201 | PASS | template | 0 |
| plan.02 | hist_gradient_boosting | 0.7881 | cost_optimal → 0.158 | PASS | template | 0 |
| plan.03 | logistic_regression | 0.7216 | 0.30 → 0.300 | FAIL | template | 1 |

## 3. 四层验证结论

| 运行 | 接口 | 功能 | 指标 | 稳定性 | 确定性 Δ | 错误签名 |
|---|---|---|---|---|---|---|
| plan.01 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |
| plan.02 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |
| plan.03 | PASS | PASS | FAIL | PASS | 0.00e+00 | MetricBelowThreshold |

## 4. 修复轨迹

- 第 1 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change；补丁来源 none）
  - LLM 根因推理：按错误签名查表定向修复

## 设计依据

- 评价口径：主指标 `auc`（maximize，门槛 0.78）；候选在 valid 段实测后统一打分排名，test 段只在比较结束后消费一次。
- 检索证据：命中 5 项（cap.risk_policy.C6、metric.test_report.r04、cap.expert_rules.E1、cap.expert_rules.E4、cap.risk_policy.C5），适用条件 5 条、系统级教训 5 条已注入 Planner / Coder 的 prompt。
- 硬约束：[C1] 客群范围：仅适用于持有 ≥6 期账单历史的存量客户；新客无 `PAY_*` / `BILL_AMT*` 序列，不在适用范围内；[C2] 额度区间：`LIMIT_BAL` 在本样本覆盖区间内；超出区间需人工复核；[C3] 时间范围：训练样本观测期为 2005-04 至 2005-09；上线前须做 PSI 群体稳定性检查，PSI > 0.25 触发重训
- 候选实测比较：
  - `plan.01`（random_forest）：auc=0.7899 PASS，修复 0 轮
  - `plan.02`（hist_gradient_boosting）：auc=0.7881 PASS，修复 0 轮
  - `plan.03`（logistic_regression）：auc=0.7216 FAIL，修复 1 轮
- 选择 `plan.01` 的依据：主指标实测 0.7899 排名第一且四层验证通过；未选 plan.03，因其未通过指标 / 四层门槛。
- 失败与定向修复：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）
- 这些签名已回写 `FailureCase`；同一签名在独立运行中出现达阈值后提升为 `Lesson`，下一轮由检索注入 prompt。
- 上述依据均可用节点 id 在图谱 / 报告中回溯，不含事后编造的数值。

## 5. 终评（test 段，仅一次）

- 终评候选：`plan.01`；test 段本次一次性消费，未参与候选排序与修复决策

| 指标 | test 实测 |
|---|---|
| auc | 0.7883 |
| ks | 0.4399 |
| pr_auc | 0.5679 |
| f1 | 0.5275 |
| cost_weighted_loss | 0.5367 |
| psi | 0.0681 |
| grouped_auc_gap | 0.0201 |

## 6. 图谱沉淀（知识 vs 运行记录）

> 运行记录只用于追溯、可被重跑覆盖；教训跨运行成立，随证据累积置信度。

- 新增节点：3
- 新增边：3
- 运行记录 ValidationRun（本次留痕，可随重跑覆盖）：3
- 失败案例证据合并（独立 run 数累加）：0
- 本次提升为教训（跨运行知识）：0
- 图谱内教训总数：13

- 运行日志另存：`outputs/kg/credit_kg_after_run_runs.json`（仅追溯，不参与检索）

## 7. 产物

- `outputs/generated/credit/candidate_plan.01.py`
- `outputs/generated/credit/candidate_plan.02.py`
- `outputs/generated/credit/candidate_plan.03.py`
- 回写图谱（知识）：`outputs/kg/credit_kg_after_run.json`

模式 with_kg（图谱来源 sources+after_run）；候选 3 个；修复 1 轮；评审协作 0 次；历史失败经验命中 是；检索证据 5 项已注入 Planner 与 Coder prompt。
