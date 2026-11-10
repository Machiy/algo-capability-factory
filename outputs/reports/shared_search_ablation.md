# 搜索消融对比（多轮分层 Successive Halving）

> 同一 capability spec、同一数据集、同一离线规则模板（`provider=mock`，确定性），
> 唯一变量是是否开启搜索（`search.halving_enabled`）。
> 关闭：Planner 生成 3 候选后直接完整评估；
> 开启：3 候选扩到 12（model_family × sampler × threshold 组合）→ 第 1 轮用 40% 训练行粗评全部候选 → 按算法族分层，族内保留前一半变体 → 第 2 轮把训练预算升到全量复评 6 个晋级者 → 按族去重保留 3 个完整评估。
> 边界：预算递增体现在「训练行比例 40%→100%」与「候选数减半」，评估段始终是完整
> valid；不是 MCTS / 贝叶斯优化，也不在多轮之间改搜索空间。

| 指标 | 关闭搜索 | 开启搜索 |
|---|---|---|
| 完整评估候选数 | 3 | 3 |
| 最终 Top-1 主指标 | 0.788149 | 0.789905 |
| 最佳候选 | plan.03 | plan.01 |
| 修复轮次 | 1 | 2 |
| 四层全通过 | True | True |
| run 总耗时（含沙箱） | 31.8s | 123.7s |

## 结论

- Top-1 主指标高于基线（+0.001756）：搜索在 12 个组合里按粗评淘汰，两组 test 段都只消费一次，未出现「多跑几次就把指标刷高」的虚高。
- 代价：run 总耗时增加 91.9s（+289%），来自粗评阶段的额外沙箱执行。
- 两组 test 段均只消费一次（TestGate 硬保证），搜索不改变「test 只看一次」的纪律。

- 关闭搜索报告：`outputs/reports/credit_run_search_off.md`
- 开启搜索报告：`outputs/reports/credit_run_search_on.md`
