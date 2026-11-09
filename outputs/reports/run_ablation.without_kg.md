# 端到端运行报告 · ablation.without_kg

> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径
> （开发要求 g），生成代码在子进程用真实数据集执行，指标均为实测，未造数值。
> T1 列名错误由规则模板模拟 LLM 的直觉命名，并在子进程用真实数据集触发 `KeyError` 后定向修复。
> test 段仅在候选比较结束后对最佳候选评估一次，不参与排序与修复。引用 cassette 回放的内容须另标注「离线回放」。

- 能力描述：预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模
- 能力理解来源：mock
- 知识图谱：without_kg（图谱来源 sources）
- 历史失败经验命中：否
- 七步流程：执行完成（a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink 均有产物）
- 四层全通过：**PASS**
- 七步轨迹：a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → e.Execute+Validate → f.Diagnose+Repair → d.Generate → e.Execute+Validate → f.Diagnose+Repair → d.Generate → e.Execute+Validate → g.Sink

> 说明：四层全通过为 FAIL 时，通常是「指标表现」层未达 `verify_credit.yaml`
> 的业务门槛；接口 / 功能 / 稳定性结论见第 3 节，失败记录已回写 FailureCase。

## 1. 检索证据（进入 Planner / Coder prompt）

```text
# 检索证据（query=预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模）
```

## 2. 候选方案比较（Beam Top-3，主指标 auc）

| 方案 | 模型族 | auc | 通过 | 代码来源 | 修复轮次 |
|---|---|---|---|---|---|
| plan.03 | hist_gradient_boosting | 0.7843 | PASS | template | 0 |
| plan.02 | logistic_regression | 0.7206 | FAIL | template | 1 |
| plan.01 | logistic_regression | 0.7206 | FAIL | template | 2 |

## 3. 四层验证结论

| 运行 | 接口 | 功能 | 指标 | 稳定性 | 确定性 Δ | 错误签名 |
|---|---|---|---|---|---|---|
| plan.01 | PASS | PASS | FAIL | PASS | 0.00e+00 | MetricBelowThreshold |
| plan.02 | PASS | PASS | FAIL | PASS | 0.00e+00 | MetricBelowThreshold |
| plan.03 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |

## 4. 修复轨迹

- 第 1 轮：`KeyError: PAY_1` → 按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）（repaired）
- 第 2 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）
- 第 1 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）

## 设计依据
- 检索证据条目：1
- 候选排名：plan.03 > plan.02 > plan.01
- 修复轨迹：按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）; 检索历史高分方案，切换模型族或按成本比调阈值; 检索历史高分方案，切换模型族或按成本比调阈值
- 依据：检索到的适用条件约束候选方案，历史失败规避项触发列名映射修复。

## 5. 终评（test 段，仅一次）

- 终评候选：`plan.03`；test 段本次一次性消费，未参与候选排序与修复决策

| 指标 | test 实测 |
|---|---|
| auc | 0.7865 |
| ks | 0.4336 |
| pr_auc | 0.5618 |
| f1 | 0.4637 |
| cost_weighted_loss | 0.7200 |
| psi | 0.0163 |
| grouped_auc_gap | 0.0104 |

## 6. 图谱沉淀 diff


## 7. 产物

- `outputs/generated/candidate_plan.01.py`
- `outputs/generated/candidate_plan.02.py`
- `outputs/generated/candidate_plan.03.py`
- 回写图谱：`outputs/kg/capabilities_after_run.json`

模式 without_kg（图谱来源 sources）；候选 3 个；修复 3 轮；历史失败经验命中 否；检索证据 0 项已注入 Planner 与 Coder prompt。
