# 短信分类失败复盘（能力抽取源 · 模拟业务材料）

> 用于演示「失败经验沉淀为可复用知识」在文本场景同样成立：
> `FR-xx` 小节会被抽成 `FailureCase` 节点，并在下一轮检索时作为规避项注入 Planner / Coder prompt。

## FR-01 向量器在测试集上 fit 导致指标虚高

| 项 | 内容 |
|---|---|
| 现象 | accuracy 0.997、macro-F1 0.985，上线后掉到 0.94 |
| 根因 | 划分前对全量文本 `TfidfVectorizer.fit`，测试集词表与 IDF 泄漏进训练 |
| 错误签名 | `LeakageDetected` |
| 修复策略 | 向量器放进 `sklearn.Pipeline`，只在训练集 fit；划分前不触碰测试集 |
| 可复用经验 | 文本任务的泄漏比表格更隐蔽，必须由 Pipeline 结构保证，而不是靠人工纪律 |

## FR-02 只看 accuracy 掩盖少数类误杀

| 项 | 内容 |
|---|---|
| 现象 | accuracy 0.98 看似达标，但 spam 召回只有 0.71，大量垃圾短信漏过 |
| 根因 | 正例仅 13.4%，全判 ham 也能拿到 0.866 的 accuracy |
| 错误签名 | `MetricBelowThreshold` |
| 修复策略 | 主指标改为 macro-F1 与 spam 召回，配合 `class_weight="balanced"` |
| 可复用经验 | 类别不平衡场景禁止用 accuracy 单独验收 |
