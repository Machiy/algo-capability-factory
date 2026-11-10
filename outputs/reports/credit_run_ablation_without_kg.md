# 端到端运行报告 · ablation_without_kg

> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径
> （开发要求 g），生成代码在子进程用真实数据集执行，指标均为实测，未造数值。
> 失败来自沙箱实测或 `verify_*.yaml` 的真实门槛，不向生成代码注入人工错误；修复动作见第 4 节。
> test 段仅在候选比较结束后对最佳候选评估一次，不参与排序与修复。引用 cassette 回放的内容须另标注「离线回放」。

- 能力描述：预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模
- 能力理解来源：mock
- LLM 后端分布：Coder=规则模板、Interpreter=规则模板、Planner=规则模板、Repairer=规则模板
- 知识图谱：without_kg（图谱来源 sources）
- 历史经验实际生效：否
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

## 1. 检索证据（进入 Planner / Coder prompt，含 0 条系统级教训）

```text
# 检索证据（query=预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模）
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

- 第 1 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change；补丁来源 未改动源码）
  - 根因说明：按错误签名查表定向修复

## 设计依据

- 评价口径：主指标 `auc`（maximize，门槛 0.78）；候选在 valid 段实测后统一打分排名，test 段只在比较结束后消费一次。
- 检索证据：命中 0 项（无），适用条件 0 条、系统级教训 0 条已注入 Planner / Coder 的 prompt。
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

- 消融对照组不回写图谱（避免污染实验口径）

## 7. 产物

- `outputs/generated/credit/candidate_plan.01.py`
- `outputs/generated/credit/candidate_plan.02.py`
- `outputs/generated/credit/candidate_plan.03.py`
- 回写图谱（知识）：`outputs/kg/credit_kg_after_run.json`

模式 without_kg（图谱来源 sources）；候选 3 个；修复 1 轮；评审协作 0 次；历史经验实际生效 否；检索证据 0 项已注入 Planner 与 Coder prompt。
