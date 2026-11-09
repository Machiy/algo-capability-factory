# 端到端运行报告 · demo

> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径
> （开发要求 g），生成代码在子进程用真实数据集执行，指标均为实测，未造数值。
> T1 列名错误由规则模板模拟 LLM 的直觉命名，并在子进程用真实数据集触发 `KeyError` 后定向修复。
> test 段仅在候选比较结束后对最佳候选评估一次，不参与排序与修复。引用 cassette 回放的内容须另标注「离线回放」。

- 能力描述：预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。
- 能力理解来源：cassette
- 知识图谱：with_kg（图谱来源 after_run）
- 历史失败经验命中：是
- 七步流程：执行完成（a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink 均有产物）
- 四层全通过：**PASS**
- 七步轨迹：a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → d.Generate → e.Execute+Validate → d.Generate → e.Execute+Validate → g.Sink

> 说明：四层全通过为 FAIL 时，通常是「指标表现」层未达 `verify_credit.yaml`
> 的业务门槛；接口 / 功能 / 稳定性结论见第 3 节，失败记录已回写 FailureCase。

## 1. 检索证据（进入 Planner / Coder prompt）

```text
# 检索证据（query=预测信用卡客户下月违约概率，时间外划分，按 5:1 成本比选阈值，禁止 ID 入模。）
- [0.503] [C6] 标识字段 (cap.risk_policy.C6)
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
## 历史失败规避项
- KeyError: PAY_1 → 按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）
- MetricBelowThreshold → 检索历史高分方案，切换模型族或按成本比调阈值
- KeyError → 按 `Dataset` 节点的列名映射表替换为 `PAY_0`、`PAY_2`…`PAY_6`；禁止按序号硬编码列名
- SchemaError → 0/5/6 归入「其他」类别；`PAY_* = -2` 保留为独立类别；编码前做取值域校验
- LeakageDetected → 改时间外划分；强制 `sklearn.Pipeline` 且所有预处理器仅 on train fit；按 `PRECEDES` 约束检查期次
```

## 2. 候选方案比较（Beam Top-3，主指标 auc）

| 方案 | 模型族 | auc | 通过 | 代码来源 | 修复轮次 |
|---|---|---|---|---|---|
| plan.02 | random_forest | 0.7899 | PASS | template | 0 |
| plan.03 | hist_gradient_boosting | 0.7843 | PASS | template | 0 |
| plan.01 | logistic_regression | 0.7206 | FAIL | template | 1 |

## 3. 四层验证结论

| 运行 | 接口 | 功能 | 指标 | 稳定性 | 确定性 Δ | 错误签名 |
|---|---|---|---|---|---|---|
| plan.01 | PASS | PASS | FAIL | PASS | 0.00e+00 | MetricBelowThreshold |
| plan.02 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |
| plan.03 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |

## 4. 修复轨迹

- 第 1 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）

## 设计依据
- 检索证据条目：18
- 候选排名：plan.02 > plan.03 > plan.01
- 修复轨迹：检索历史高分方案，切换模型族或按成本比调阈值
- 依据：检索到的适用条件约束候选方案，历史失败规避项触发列名映射修复。

## 5. 终评（test 段，仅一次）

- 终评候选：`plan.02`；test 段本次一次性消费，未参与候选排序与修复决策

| 指标 | test 实测 |
|---|---|
| auc | 0.7883 |
| ks | 0.4399 |
| pr_auc | 0.5679 |
| f1 | 0.4590 |
| cost_weighted_loss | 0.7260 |
| psi | 0.0681 |
| grouped_auc_gap | 0.0201 |

## 6. 图谱沉淀 diff

- nodes_added：0
- edges_added：0

## 7. 产物

- `outputs/generated/candidate_plan.01.py`
- `outputs/generated/candidate_plan.02.py`
- `outputs/generated/candidate_plan.03.py`
- 回写图谱：`outputs/kg/capabilities_after_run.json`

模式 with_kg（图谱来源 after_run）；候选 3 个；修复 1 轮；历史失败经验命中 是；检索证据 5 项已注入 Planner 与 Coder prompt。
