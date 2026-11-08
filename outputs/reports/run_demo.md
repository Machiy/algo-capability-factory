# 端到端运行报告 · demo

> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径
> （开发要求 g），T1 列名错误由规则模板模拟 LLM 的直觉命名，
> 并在子进程用真实数据集触发 `KeyError` 后定向修复；指标均为实测，未造数值。
> test 集全程未访问。引用 cassette 回放的内容须另标注「离线回放」。

- 能力描述：预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模
- 七步流程：执行完成（a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink 均有产物）
- 四层全通过：**FAIL**
- 七步轨迹：a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → e.Execute+Validate → f.Diagnose+Repair → d.Generate → e.Execute+Validate → f.Diagnose+Repair → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink

> 说明：四层全通过为 FAIL 时，通常是「指标表现」层未达 `verify_credit.yaml`
> 的业务门槛；接口 / 功能 / 稳定性结论见第 3 节，失败记录已回写 FailureCase。

## 1. 检索证据（进入 Planner / Coder prompt）

```text
# 检索证据（query=预测信用卡客户下月违约概率，时间外划分，按5:1成本比选阈值，禁止ID入模）
- [0.502] [C6] 标识字段 (cap.risk_policy.C6)
- [0.475] [r04] 禁 ID 入模、禁读标签路径 (metric.test_report.r04)
- [0.375] [T1] 最近一期列名是 PAY_0，不存在 PAY_1 (cap.data_dictionary.T1)
- [0.375] [T2] 存在未文档化类别 (cap.data_dictionary.T2)
- [0.375] [T2b] 还款状态含未文档化值 (cap.data_dictionary.T2b)
## 适用条件
- [C1] 客群范围：仅适用于持有 ≥6 期账单历史的存量客户；新客无 `PAY_*` / `BILL_AMT*` 序列，不在适用范围内
- [C2] 额度区间：`LIMIT_BAL` 在本样本覆盖区间内；超出区间需人工复核
- [C3] 时间范围：训练样本观测期为 2005-04 至 2005-09；上线前须做 PSI 群体稳定性检查，PSI > 0.25 触发重训
- [C4] 划分方式：必须时间外划分，禁止随机打乱；所有预处理在训练集内 fit
- [C5] 敏感字段：`SEX` / `AGE` / `EDUCATION` / `MARRIAGE` 不得进入模型特征，仅用于分组公平性审计
## 历史失败规避项
- KeyError → 按 `Dataset` 节点的列名映射表替换为 `PAY_0`、`PAY_2`…`PAY_6`；禁止按序号硬编码列名
- SchemaError → 0/5/6 归入「其他」类别；`PAY_* = -2` 保留为独立类别；编码前做取值域校验
- LeakageDetected → 改时间外划分；强制 `sklearn.Pipeline` 且所有预处理器仅 on train fit；按 `PRECEDES` 约束检查期次
- CostLossAboveBaseline → 在验证集上按成本加权损失网格搜索最优阈值，测试集不参与调阈
- LeakageDetected → 采样仅在训练集内、且在 Pipeline 内执行
```

## 2. 候选方案比较（Beam Top-3）

| 方案 | 模型族 | AUC | 通过 | 修复轮次 |
|---|---|---|---|---|
| plan.03 | hist_gradient_boosting | 0.7206 | FAIL | 1 |
| plan.02 | logistic_regression | 0.7206 | FAIL | 1 |
| plan.01 | logistic_regression | 0.7206 | FAIL | 2 |

## 3. 四层验证结论

| 运行 | 接口 | 功能 | 指标 | 稳定性 | 错误签名 |
|---|---|---|---|---|---|
| plan.01 | PASS | PASS | FAIL | PASS | MetricBelowThreshold |
| plan.02 | PASS | PASS | FAIL | PASS | MetricBelowThreshold |
| plan.03 | PASS | PASS | FAIL | PASS | MetricBelowThreshold |

## 4. 修复轨迹

- 第 1 轮：`KeyError: PAY_1` → 按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）（repaired）
- 第 2 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）
- 第 1 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）
- 第 1 轮：`MetricBelowThreshold` → 检索历史高分方案，切换模型族或按成本比调阈值（no_change）

## 设计依据
- 检索证据条目：18
- 候选排名：plan.03 > plan.02 > plan.01
- 修复轨迹：按 Dataset 列名映射把 PAY_1 改为 PAY_0（T1 陷阱）; 检索历史高分方案，切换模型族或按成本比调阈值; 检索历史高分方案，切换模型族或按成本比调阈值; 检索历史高分方案，切换模型族或按成本比调阈值
- 依据：检索到的适用条件约束候选方案，历史失败规避项触发列名映射修复。

## 5. 图谱沉淀 diff

- nodes_added：8
- edges_added：9

## 6. 产物

- `outputs/generated/candidate_plan.01.py`
- `outputs/generated/candidate_plan.02.py`
- `outputs/generated/candidate_plan.03.py`
- 回写图谱：`outputs/kg/capabilities_after_run.json`

候选 3 个；修复 4 轮；检索证据 5 项已注入 Planner 与 Coder prompt。
