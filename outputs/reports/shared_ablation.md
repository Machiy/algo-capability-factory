# 有 KG / 无 KG 消融对比

> 同一 capability spec、同一候选方案与数据集，唯一变量是是否检索并注入图谱证据。
> 两组指标均为实测；模型、特征与数据完全相同，主指标不因证据注入而改变。
> 差异体现在「指标层失败后，能否按图谱里的历史高分记录换族修复」。
> 无 KG 组不回写图谱，避免污染实验。

| 指标 | 有 KG | 无 KG |
|---|---|---|
| 图谱来源 | sources+after_run | sources |
| 历史经验实际生效 | 是 | 否 |
| 修复轮次 | 2 | 1 |
| 修复动作 | kg_escalation、kg_escalation | none |
| 错误签名 | MetricBelowThreshold、MetricBelowThreshold | MetricBelowThreshold |
| 四层通过的候选数 | 3/3 | 2/3 |
| 候选 AUC（降序） | 0.789905 / 0.788149 / 0.782806 | 0.789905 / 0.788149 / 0.721586 |

## 结论

- 有 KG 组从历史实验记录里拿到「主指标更高的算法族」排序，指标层失败后按该排序
  换族重生成并复验，把原本不达标的候选救回；无 KG 组没有这条证据，指标层失败只能
  如实记为 `no_change`，候选维持 FAIL。
- 两组 AUC 的绝对值由模型与数据决定，不因证据注入而变化；沉淀改变的是「修复是否
  有据可依」与「候选通过率」，未做任何数值美化。

- 有 KG 报告：`outputs/reports/credit_run_ablation_with_kg.md`
- 无 KG 报告：`outputs/reports/credit_run_ablation_without_kg.md`
