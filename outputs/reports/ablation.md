# 有 KG / 无 KG 消融对比

> 同一 capability spec、同一候选方案与数据集，唯一变量是是否检索并注入图谱证据。
> 两组指标均为实测；AUC 不因证据注入而改变（模型不使用证据作为特征），
> 差异体现在「是否重复踩已知错误」与修复轮次。无 KG 组不回写图谱，避免污染实验。

| 指标 | 有 KG | 无 KG |
|---|---|---|
| 图谱来源 | after_run | sources |
| 命中历史失败经验 | 是 | 否 |
| 修复轮次 | 1 | 2 |
| 错误签名 | MetricBelowThreshold | KeyError: PAY_1、MetricBelowThreshold |
| 是否首轮避开 T1 | 是 | 否 |
| 候选 AUC（降序） | 0.789905 / 0.784337 / 0.720612 | 0.789905 / 0.784337 / 0.720612 |

## 结论

- 有 KG 组从回写图谱读到上一轮的 `KeyError: PAY_1` 失败案例，Coder 首轮即改用 `PAY_0`，
  省掉一次失败执行；无 KG 组没有这条证据，先踩 T1 再修复。
- 两组业务指标结论一致，说明沉淀改变的是「过程效率」而非「指标口径」，未做任何数值美化。

- 有 KG 报告：`outputs/reports/run_ablation.with_kg.md`
- 无 KG 报告：`outputs/reports/run_ablation.without_kg.md`
