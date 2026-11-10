# 端到端运行报告 · demo

> 本报告为真实运行的产物。核心闭环演示走 `MockLLM` 规则模板路径
> （开发要求 g），生成代码在子进程用真实数据集执行，指标均为实测，未造数值。
> test 段仅在候选比较结束后对最佳候选评估一次，不参与排序与修复。引用 cassette 回放的内容须另标注「离线回放」。

- 能力描述：把短信分类为垃圾短信或正常短信，输出准确率与宏平均F1
- 能力理解来源：mock
- 知识图谱：with_kg（图谱来源 sources+after_run）
- 历史失败经验命中：否
- 七步流程：执行完成（a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → f.Diagnose+Repair → g.Sink 均有产物）
- 四层全通过：**PASS**
- 七步轨迹：a.Parse → b.Retrieve → c.Plan → d.Generate → e.Execute+Validate → d.Generate → e.Execute+Validate → d.Generate → e.Execute+Validate → g.Sink

> 说明：四层全通过为 FAIL 时，通常是「指标表现」层未达 `verify_text.yaml`
> 的业务门槛；接口 / 功能 / 稳定性结论见第 3 节，失败记录已回写 FailureCase。

## 0. 输入引导（入口体检）

- 结论：**OK（要素齐全）**，要素完备度 0.83
- 已表达要素：goal、data、metric
- 缺失要素：constraint
- 引导建议：描述要素齐全，可直接进入七步闭环

## 1. 检索证据（进入 Planner / Coder prompt，含 5 条系统级教训）

```text
# 检索证据（query=把短信分类为垃圾短信或正常短信，输出准确率与宏平均F1）
- [0.475] [macro_f1] 0.90 (metric.sms_policy.macro_f1)
- [0.460] [r01] 0.95 (metric.sms_policy.r01)
- [0.375] [ST1] 大小写与标点不统一 (cap.sms_data_dictionary.ST1)
- [0.375] [ST2] 正文含电话号码与短链接 (cap.sms_data_dictionary.ST2)
- [0.375] [ST3] 极短文本与重复文本 (cap.sms_data_dictionary.ST3)
## 适用条件
- [S1] 文本长度：少于 3 个字符的样本不参与训练，避免噪声主导词表
- [S2] 语言范围：当前仅覆盖英文短信；中文短信需要另行分词，不能直接复用本词表
- [S3] 类别严重不平衡：spam 约 13.4%，评估必须同时看 macro-F1，禁止只看 accuracy
- [S4] 词表边界：向量器只能在训练集 fit，禁止在验证集 / 测试集上统计词表
- [S5] 号码与链接：电话、URL 用占位符替换，禁止让模型记住具体号码
## 系统级教训（跨运行成立，生成代码必须遵守）
- [runtime] 内存看门狗永不触发，占用早已超过 2GB 仍判定通过 → 根因：Windows 虚拟环境里的 `python.exe` 是重定向器，读父进程 RSS 只有约 4MB，按单进程计量完全失真 → 处置：改为 `psutil.Process.children(recursive=True)` 对整棵进程树求和，超限即终止子进程（出现 1 次，置信度 0.90）
- [platform] 本地跑通的 CLI 断言在 CI 上随机失败 → 根因：Typer 检测到终端后自动着色，输出里混入 ANSI 转义序列，按纯文本匹配必然失配 → 处置：子进程设 `NO_COLOR=1`、`TERM=dumb`，断言前统一剥离 ANSI（出现 1 次，置信度 0.90）
- [platform] 证据 SHA-256 在 Windows 上校验失败，Linux 正常 → 根因：Git 检出的换行是 CRLF，与原文 LF 不同，同一内容算出不同哈希 → 处置：`read_sources` 读入后归一化换行再计算哈希（出现 1 次，置信度 0.90）
- [validation] 报告写着四层验证，实际只有两层在生效：确定性恒为 True，test 段从未被读取 → 根因：检查项只存在于报告字段里，没有代码真正读取对应输入 → 处置：沙箱支持 `repeat>=2` 的同进程二次 fit 与 `segment="test"`；工作流在候选比较结束后消费一次 test（出现 1 次，置信度 0.90）
- [knowledge] 边很多，但追问「这两点为什么相连」答不出来 → 根因：连边按 `index % len(metrics)` 轮转，与内容无关，属于凑数量 → 处置：改为名称或属性文本命中才连边，宁可边少（出现 1 次，置信度 0.90）
## 历史失败规避项
- LeakageDetected → 向量器放进 `sklearn.Pipeline`，只在训练集 fit；划分前不触碰测试集
- MetricBelowThreshold → 主指标改为 macro-F1 与 spam 召回，配合 `class_weight="balanced"`
```

## 2. 候选方案比较（Beam Top-3，主指标 accuracy）

| 方案 | 模型族 | accuracy | 通过 | 代码来源 | 修复轮次 |
|---|---|---|---|---|---|
| plan.02 | linear_svc | 0.9803 | PASS | template | 0 |
| plan.01 | logistic_regression | 0.9785 | PASS | template | 0 |
| plan.03 | complement_nb | 0.9731 | PASS | template | 0 |

## 3. 四层验证结论

| 运行 | 接口 | 功能 | 指标 | 稳定性 | 确定性 Δ | 错误签名 |
|---|---|---|---|---|---|---|
| plan.01 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |
| plan.02 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |
| plan.03 | PASS | PASS | PASS | PASS | 0.00e+00 | 无 |

## 4. 修复轨迹

- 无失败轮次

## 设计依据

- 评价口径：主指标 `accuracy`（maximize，门槛 0.95）；候选在 valid 段实测后统一打分排名，test 段只在比较结束后消费一次。
- 检索证据：命中 5 项（metric.sms_policy.macro_f1、metric.sms_policy.r01、cap.sms_data_dictionary.ST1、cap.sms_data_dictionary.ST2、cap.sms_data_dictionary.ST3），适用条件 5 条、系统级教训 5 条已注入 Planner / Coder 的 prompt。
- 硬约束：[S1] 文本长度：少于 3 个字符的样本不参与训练，避免噪声主导词表；[S2] 语言范围：当前仅覆盖英文短信；中文短信需要另行分词，不能直接复用本词表；[S3] 类别严重不平衡：spam 约 13.4%，评估必须同时看 macro-F1，禁止只看 accuracy
- 候选实测比较：
  - `plan.02`（linear_svc）：accuracy=0.9803 PASS，修复 0 轮
  - `plan.01`（logistic_regression）：accuracy=0.9785 PASS，修复 0 轮
  - `plan.03`（complement_nb）：accuracy=0.9731 PASS，修复 0 轮
- 选择 `plan.02` 的依据：主指标实测 0.9803 排名第一且四层验证通过；全部候选通过门槛，按主指标择优。
- 本轮未触发失败签名，无需定向修复。
- 上述依据均可用节点 id 在图谱 / 报告中回溯，不含事后编造的数值。

## 5. 终评（test 段，仅一次）

- 终评候选：`plan.02`；test 段本次一次性消费，未参与候选排序与修复决策

| 指标 | test 实测 |
|---|---|
| accuracy | 0.9821 |
| macro_f1 | 0.9625 |

## 6. 图谱沉淀（知识 vs 运行记录）

> 运行记录只用于追溯、可被重跑覆盖；教训跨运行成立，随证据累积置信度。

- 新增节点：3
- 新增边：3
- 运行记录 ValidationRun（本次留痕，可随重跑覆盖）：3
- 失败案例证据合并（独立 run 数累加）：0
- 本次提升为教训（跨运行知识）：0
- 图谱内教训总数：12

- 运行日志另存：`outputs/kg/text_kg_after_run_runs.json`（仅追溯，不参与检索）

## 7. 产物

- `outputs/generated/text/candidate_plan.01.py`
- `outputs/generated/text/candidate_plan.02.py`
- `outputs/generated/text/candidate_plan.03.py`
- 回写图谱（知识）：`outputs/kg/text_kg_after_run.json`

模式 with_kg（图谱来源 sources+after_run）；候选 3 个；修复 0 轮；历史失败经验命中 否；检索证据 5 项已注入 Planner 与 Coder prompt。
