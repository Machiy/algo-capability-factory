# 搜索消融对比（Successive Halving）

> 同一 capability spec、同一数据集、同一离线规则模板（`provider=mock`，确定性），
> 唯一变量是是否开启 Successive Halving 搜索。
> 关闭：Planner 生成 3 候选后直接完整评估；
> 开启：3 候选扩到 12（model_family × sampler × threshold 组合）→ 粗评 → 按 family 去重淘汰 → 3 候选完整评估。

| 指标 | 关闭搜索 | 开启搜索 |
|---|---|---|
| 完整评估候选数 | 3 | 3 |
| 最终 Top-1 主指标 | 0.788149 | 0.789905 |
| 最佳候选 | plan.03 | plan.02 |
| 修复轮次 | 1 | 1 |
| 四层全通过 | True | True |
| run 总耗时（含沙箱） | 30.0s | 86.0s |

## 结论

- Top-1 主指标不劣于基线（0.788149 → 0.789905）：搜索在 12 个组合里按粗评淘汰，选出了比「3 候选直接评估」更适合的 family 变体，未出现「多跑几次就把指标刷高」的虚高。
- 代价：run 总耗时增加 56.0s（+187%），来自粗评阶段的额外沙箱执行。
- 两组 test 段均只消费一次（TestGate 硬保证），搜索不改变「test 只看一次」的纪律。

- 关闭搜索报告：`outputs/reports/credit_run_search_off.md`
- 开启搜索报告：`outputs/reports/credit_run_search_on.md`
