// AlgoCap Factory 知识图谱导出（Cypher，Neo4j 5.x）
// 节点 108 个 / 边 343 条
// 用法：cat <this-file>.cypher | cypher-shell -u neo4j -p <password>

CREATE CONSTRAINT capability_node_id IF NOT EXISTS FOR (n:Capability) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT operator_node_id IF NOT EXISTS FOR (n:Operator) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT algorithm_node_id IF NOT EXISTS FOR (n:Algorithm) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT metric_node_id IF NOT EXISTS FOR (n:Metric) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT dataset_node_id IF NOT EXISTS FOR (n:Dataset) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT environment_node_id IF NOT EXISTS FOR (n:Environment) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT validationrun_node_id IF NOT EXISTS FOR (n:ValidationRun) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT failurecase_node_id IF NOT EXISTS FOR (n:FailureCase) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT lesson_node_id IF NOT EXISTS FOR (n:Lesson) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT evidence_node_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.node_id IS UNIQUE;

MERGE (n:Evidence {node_id: 'evidence.data_dictionary'})
SET n.name = '证据源：assets/docs/data_dictionary.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "业务文档", "file_sha256": "6848ec5aaa8675f09d0eca3d68dfb9ce3b14588abe1a450502f5e7a1c3101274", "path": "assets/docs/data_dictionary.md"}';
MERGE (n:Dataset {node_id: 'dataset.data_dictionary'})
SET n.name = 'synthetic_demand', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fields": {"名称": "UCI Default of Credit Card Clients", "标签": "`default.payment.next.month`，1 = 违约，0 = 正常", "样本量": "30,000 行 × 25 列（23 特征 + 1 标签 + 1 标识）", "正例": "6,636（22.12%，下月违约）", "观测期": "2005 年 4 月 – 2005 年 9 月", "负例": "23,364（77.88%）"}, "forbidden_features": ["demand"], "sensitive_features": [], "split_policy": "temporal_holdout", "target": "demand"}';
MERGE (n:Capability {node_id: 'cap.data_dictionary.T1'})
SET n.name = '[T1] 最近一期列名是 PAY_0，不存在 PAY_1', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"处理建议": 16.0, "实测证据": 26.0, "编号": 1.0, "问题": 1.0}, "section": "3. 已知数据问题（登记为 T1–T4）", "source_id": "T1", "处理建议": "建立显式列名映射，禁止按 `PAY_1`…`PAY_6` 硬编码", "实测证据": "列名清单中仅有 `PAY_0`、`PAY_2`…`PAY_6`", "编号": "T1", "问题": "最近一期列名是 `PAY_0`，**不存在 `PAY_1`**"}';
MERGE (n:Capability {node_id: 'cap.data_dictionary.T2'})
SET n.name = '[T2] 存在未文档化类别', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"处理建议": 56.0, "实测证据": 1.234560563450123e+18, "编号": 2.0}, "section": "3. 已知数据问题（登记为 T1–T4）", "source_id": "T2", "处理建议": "0/5/6 归入「其他」；编码前必须做取值校验", "实测证据": "`EDUCATION` 实测取值 `[0,1,2,3,4,5,6]`，其中 0/5/6 共 **345** 条；`MARRIAGE` 实测 `[0,1,2,3]`，0 共 **54** 条", "编号": "T2", "问题": "存在未文档化类别"}';
MERGE (n:Capability {node_id: 'cap.data_dictionary.T2b'})
SET n.name = '[T2b] 还款状态含未文档化值', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 2.0}, "section": "3. 已知数据问题（登记为 T1–T4）", "source_id": "T2b", "处理建议": "保留为独立类别，不做简单裁剪", "实测证据": "`PAY_0` 实测范围 `[-2, 8]`，字典未说明 -2 含义", "编号": "T2b", "问题": "还款状态含未文档化值"}';
MERGE (n:Capability {node_id: 'cap.data_dictionary.T3'})
SET n.name = '[T3] 账单金额为负', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"实测证据": 3932.0, "编号": 3.0}, "section": "3. 已知数据问题（登记为 T1–T4）", "source_id": "T3", "处理建议": "视为退款/多付，保留符号，不做绝对值化", "实测证据": "`BILL_AMT*` 负值记录共 **3,932** 条", "编号": "T3", "问题": "账单金额为负"}';
MERGE (n:Capability {node_id: 'cap.data_dictionary.T3b'})
SET n.name = '[T3b] 期次错位', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"实测证据": 19819.0, "编号": 3.0}, "section": "3. 已知数据问题（登记为 T1–T4）", "source_id": "T3b", "处理建议": "构造比值类特征时须显式对齐期次", "实测证据": "`PAY_AMT1` 是 9 月实付、对应 8 月账单，与 `BILL_AMT1`（9 月账单）不同期", "编号": "T3b", "问题": "期次错位"}';
MERGE (n:Capability {node_id: 'cap.data_dictionary.T4'})
SET n.name = '[T4] 标签为「下月」违约', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 4.0}, "section": "3. 已知数据问题（登记为 T1–T4）", "source_id": "T4", "处理建议": "必须时间外划分，随机划分会引入未来信息", "实测证据": "目标列定义", "编号": "T4", "问题": "标签为「下月」违约"}';
MERGE (n:Evidence {node_id: 'evidence.engineering_lessons'})
SET n.name = '证据源：assets/docs/engineering_lessons.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "工程教训", "file_sha256": "53dda1833ae55b0db5fbf9e6338976ef89feb21142a2fe4a861b8a4fca584ed9", "path": "assets/docs/engineering_lessons.md"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE1'})
SET n.name = '[LE1] 内存看门狗永不触发，占用早已超过 2GB 仍判定通过', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "改为 `psutil.Process.children(recursive=True)` 对整棵进程树求和，超限即终止子进程", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "资源基准与四层验证共用同一套内存口径，并构造超限用例验证看门狗真的会触发", "record_kind": "knowledge", "root_cause": "Windows 虚拟环境里的 `python.exe` 是重定向器，读父进程 RSS 只有约 4MB，按单进程计量完全失真", "run_ids": [], "scope": "runtime", "scope_label": "运行环境", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE1", "symptom": "内存看门狗永不触发，占用早已超过 2GB 仍判定通过"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE2'})
SET n.name = '[LE2] 本地跑通的 CLI 断言在 CI 上随机失败', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "子进程设 `NO_COLOR=1`、`TERM=dumb`，断言前统一剥离 ANSI", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "所有 CLI 断言走同一个输出归一化函数，不各写一份", "record_kind": "knowledge", "root_cause": "Typer 检测到终端后自动着色，输出里混入 ANSI 转义序列，按纯文本匹配必然失配", "run_ids": [], "scope": "platform", "scope_label": "平台", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE2", "symptom": "本地跑通的 CLI 断言在 CI 上随机失败"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE3'})
SET n.name = '[LE3] 证据 SHA-256 在 Windows 上校验失败，Linux 正常', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "`read_sources` 读入后归一化换行再计算哈希", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "哈希只对归一化后的文本计算，测试重算时复用同一入口", "record_kind": "knowledge", "root_cause": "Git 检出的换行是 CRLF，与原文 LF 不同，同一内容算出不同哈希", "run_ids": [], "scope": "platform", "scope_label": "平台", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE3", "symptom": "证据 SHA-256 在 Windows 上校验失败，Linux 正常"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE4'})
SET n.name = '[LE4] 报告写着四层验证，实际只有两层在生效：确定性恒为 True，test 段从未被读取', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "沙箱支持 `repeat>=2` 的同进程二次 fit 与 `segment=\\"test\\"`；工作流在候选比较结束后消费一次 test", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "每个检查项都必须配一个「不通过」的构造用例，否则不许写进报告", "record_kind": "knowledge", "root_cause": "检查项只存在于报告字段里，没有代码真正读取对应输入", "run_ids": [], "scope": "validation", "scope_label": "验证", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE4", "symptom": "报告写着四层验证，实际只有两层在生效：确定性恒为 True，test 段从未被读取"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE5'})
SET n.name = '[LE5] 边很多，但追问「这两点为什么相连」答不出来', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "改为名称或属性文本命中才连边，宁可边少", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "每条边都要能回答「凭什么连」，答不出就删", "record_kind": "knowledge", "root_cause": "连边按 `index % len(metrics)` 轮转，与内容无关，属于凑数量", "run_ids": [], "scope": "knowledge", "scope_label": "图谱", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE5", "symptom": "边很多，但追问「这两点为什么相连」答不出来"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE6'})
SET n.name = '[LE6] 修复退化成反复重试，同一错误连修三轮仍失败', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "建立「签名 → 策略」表，只改必要片段，最多 3 轮", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "每轮修复必须记录签名与策略，重复签名立即停止该路线", "record_kind": "knowledge", "root_cause": "没有先分类错误签名，直接整段重新生成代码", "run_ids": [], "scope": "workflow", "scope_label": "编排", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE6", "symptom": "修复退化成反复重试，同一错误连修三轮仍失败"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE7'})
SET n.name = '[LE7] 传入 `../../x` 的请求能把产物写到仓库外', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "接口层做字符集 pattern 校验并拒绝 `..`，工作流侧再兜底一次", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "任何用户输入进入路径前先校验字符集与相对路径，双层校验", "record_kind": "knowledge", "root_cause": "把用户输入原样拼进文件名，只做了字符串拼接", "run_ids": [], "scope": "platform", "scope_label": "平台", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE7", "symptom": "传入 `../../x` 的请求能把产物写到仓库外"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE8'})
SET n.name = '[LE8] 报告里把离线回放说成实时调用，评审无法区分', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "把来源写进 `RunTrace.interpreter_source`，报告逐条标注", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "任何「实测」结论必须能追溯来源，回放内容单独标注", "record_kind": "knowledge", "root_cause": "响应来源没有落到产物里，只在日志里出现", "run_ids": [], "scope": "llm", "scope_label": "LLM", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE8", "symptom": "报告里把离线回放说成实时调用，评审无法区分"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE9'})
SET n.name = '[LE9] Coder 明明调用了 LLM，产物却全是模板代码', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "先过 AST 白名单与契约检查，通过即采用；失败回退模板并写 `code_sources`", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "回退路径必须写进 trace，不能静默回退", "record_kind": "knowledge", "root_cause": "LLM 返回的代码没过静态检查就被丢弃，且丢弃原因没有留痕", "run_ids": [], "scope": "llm", "scope_label": "LLM", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE9", "symptom": "Coder 明明调用了 LLM，产物却全是模板代码"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE10'})
SET n.name = '[LE10] 同一候选两次 fit 的指标不同，报告却声称确定性通过', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "显式固定 `random_state`，并在子进程内二次 fit 比较输出", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "确定性必须实测（最大绝对差），不能靠声明", "record_kind": "knowledge", "root_cause": "随机种子未固定，或同一进程重复 fit 带来状态污染", "run_ids": [], "scope": "runtime", "scope_label": "运行环境", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE10", "symptom": "同一候选两次 fit 的指标不同，报告却声称确定性通过"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE11'})
SET n.name = '[LE11] 图谱做得很全，但生成代码看不出受过它影响', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "统一走 `RetrievalResult.as_prompt_context()`，Planner 与 Coder 强制使用", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "注入内容要写进 trace 留证，报告可回放", "record_kind": "knowledge", "root_cause": "渲染与注入是两套逻辑，检索结果只用于展示", "run_ids": [], "scope": "knowledge", "scope_label": "检索", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE11", "symptom": "图谱做得很全，但生成代码看不出受过它影响"}';
MERGE (n:Lesson {node_id: 'lesson.engineering_lessons.LE12'})
SET n.name = '[LE12] 换一个任务类型就要改核心验证器，改动风险高', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"action": "指标与门槛下沉到 `verify_*.yaml`，新增任务只加配置与插件", "applies_to": "跨场景通用", "confidence": 0.9, "occurrences": 1, "prevention": "新增任务类型时不许改核心模块，只允许新增配置与注册插件", "record_kind": "knowledge", "root_cause": "任务假设（指标、划分、数据列）写死在代码里，而非配置里", "run_ids": [], "scope": "workflow", "scope_label": "编排", "section": "教训速查", "signatures": [], "source": "seeded", "source_id": "LE12", "symptom": "换一个任务类型就要改核心验证器，改动风险高"}';
MERGE (n:Evidence {node_id: 'evidence.experiment_log'})
SET n.name = '证据源：assets/docs/experiment_log.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "实验记录", "file_sha256": "9891c32bbc8405638188bc0eb96712557592c18973eca1ef49abe2ba103e29db", "path": "assets/docs/experiment_log.md"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-01'})
SET n.name = '[EXP-01] Dummy（分层随机）', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.221, "编号": -1.0, "耗时(s)": 0.1, "采样/阈值": 0.5, "验证集 AUC": 0.5, "验证集 KS": 0.0}, "section": "记录汇总", "source_id": "EXP-01", "成本加权损失": "0.221", "模型": "Dummy（分层随机）", "结论": "基线", "编号": "EXP-01", "耗时(s)": "0.1", "采样/阈值": "0.5", "预处理": "无", "验证集 AUC": "0.500", "验证集 KS": "0.000"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-02'})
SET n.name = '[EXP-02] LogisticRegression', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.183, "编号": -2.0, "耗时(s)": 0.8, "采样/阈值": 0.5, "验证集 AUC": 0.741, "验证集 KS": 0.318}, "section": "记录汇总", "source_id": "EXP-02", "成本加权损失": "0.183", "模型": "LogisticRegression", "结论": "基线，未达 KS 门槛", "编号": "EXP-02", "耗时(s)": "0.8", "采样/阈值": "无 / 0.5", "预处理": "标准化", "验证集 AUC": "0.741", "验证集 KS": "0.318"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-03'})
SET n.name = '[EXP-03] LogisticRegression', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.171, "编号": -3.0, "耗时(s)": 2.4, "采样/阈值": 0.5, "验证集 AUC": 0.772, "验证集 KS": 0.361}, "section": "记录汇总", "source_id": "EXP-03", "成本加权损失": "0.171", "模型": "LogisticRegression", "结论": "可解释性好，KS 达标", "编号": "EXP-03", "耗时(s)": "2.4", "采样/阈值": "无 / 0.5", "预处理": "WOE 分箱", "验证集 AUC": "0.772", "验证集 KS": "0.361"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-04'})
SET n.name = '[EXP-04] LogisticRegression', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.152, "编号": -4.0, "耗时(s)": 2.6, "验证集 AUC": 0.775, "验证集 KS": 0.368}, "section": "记录汇总", "source_id": "EXP-04", "成本加权损失": "0.152", "模型": "LogisticRegression", "结论": "成本损失最低", "编号": "EXP-04", "耗时(s)": "2.6", "采样/阈值": "class_weight / 成本最优阈值", "预处理": "WOE 分箱", "验证集 AUC": "0.775", "验证集 KS": "0.368"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-05'})
SET n.name = '[EXP-05] RandomForest(200)', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.168, "模型": 200.0, "结论": -4.0, "编号": -5.0, "耗时(s)": 6.1, "采样/阈值": 0.5, "验证集 AUC": 0.779, "验证集 KS": 0.372}, "section": "记录汇总", "source_id": "EXP-05", "成本加权损失": "0.168", "模型": "RandomForest(200)", "结论": "AUC 略高但成本损失不如 EXP-04", "编号": "EXP-05", "耗时(s)": "6.1", "采样/阈值": "class_weight / 0.5", "预处理": "类别编码", "验证集 AUC": "0.779", "验证集 KS": "0.372"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-06'})
SET n.name = '[EXP-06] HistGB(max_iter=200)', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.165, "模型": 200.0, "编号": -6.0, "耗时(s)": 4.3, "采样/阈值": 0.5, "验证集 AUC": 0.783, "验证集 KS": 0.381}, "section": "记录汇总", "source_id": "EXP-06", "成本加权损失": "0.165", "模型": "HistGB(max_iter=200)", "结论": "AUC/KS 最高", "编号": "EXP-06", "耗时(s)": "4.3", "采样/阈值": "无 / 0.5", "预处理": "类别编码", "验证集 AUC": "0.783", "验证集 KS": "0.381"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-07'})
SET n.name = '[EXP-07] HistGB + SMOTE', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.176, "编号": -7.0, "耗时(s)": 7.9, "采样/阈值": 0.5, "验证集 AUC": 0.77, "验证集 KS": 0.355}, "section": "记录汇总", "source_id": "EXP-07", "成本加权损失": "0.176", "模型": "HistGB + SMOTE", "结论": "过采样未带来收益，且耗时上升", "编号": "EXP-07", "耗时(s)": "7.9", "采样/阈值": "SMOTE / 0.5", "预处理": "类别编码", "验证集 AUC": "0.770", "验证集 KS": "0.355"}';
MERGE (n:ValidationRun {node_id: 'run.experiment_log.EXP-08'})
SET n.name = '[EXP-08] HistGB(全量随机划分)', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"成本加权损失": 0.071, "编号": -8.0, "耗时(s)": 4.5, "采样/阈值": 0.5, "验证集 AUC": 0.912, "验证集 KS": 0.702}, "section": "记录汇总", "source_id": "EXP-08", "成本加权损失": "0.071", "模型": "HistGB(全量随机划分)", "结论": "**判定无效**：随机划分引入未来信息，指标虚高，已作废", "编号": "EXP-08", "耗时(s)": "4.5", "采样/阈值": "无 / 0.5", "预处理": "类别编码", "验证集 AUC": "0.912", "验证集 KS": "0.702"}';
MERGE (n:Capability {node_id: 'cap.experiment_log.K1'})
SET n.name = '[K1] WOE 分箱对逻辑回归的 KS 提升明显（0.318 → 0.361）', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 1.0}, "section": "可复用经验", "source_id": "K1", "来源": "EXP-02 / EXP-03", "经验": "WOE 分箱对逻辑回归的 KS 提升明显（0.318 → 0.361）", "编号": "K1"}';
MERGE (n:Capability {node_id: 'cap.experiment_log.K2'})
SET n.name = '[K2] 按成本比调阈值比换模型更能降低业务损失', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"来源": -4.0, "编号": 2.0}, "section": "可复用经验", "source_id": "K2", "来源": "EXP-04", "经验": "按成本比调阈值比换模型更能降低业务损失", "编号": "K2"}';
MERGE (n:Capability {node_id: 'cap.experiment_log.K3'})
SET n.name = '[K3] HistGB 在 AUC/KS 上最优，但可解释性弱于评分卡', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"来源": -6.0, "编号": 3.0}, "section": "可复用经验", "source_id": "K3", "来源": "EXP-06", "经验": "HistGB 在 AUC/KS 上最优，但可解释性弱于评分卡", "编号": "K3"}';
MERGE (n:Capability {node_id: 'cap.experiment_log.K4'})
SET n.name = '[K4] SMOTE 在本数据集无收益，优先 class_weight', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"来源": -7.0, "编号": 4.0}, "section": "可复用经验", "source_id": "K4", "来源": "EXP-07", "经验": "SMOTE 在本数据集无收益，优先 `class_weight`", "编号": "K4"}';
MERGE (n:Capability {node_id: 'cap.experiment_log.K5'})
SET n.name = '[K5] 随机划分会造成严重虚高，必须时间外划分', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"来源": -8.0, "编号": 5.0}, "section": "可复用经验", "source_id": "K5", "来源": "EXP-08（作废记录）", "经验": "随机划分会造成严重虚高，必须时间外划分", "编号": "K5"}';
MERGE (n:Capability {node_id: 'cap.experiment_log.K6'})
SET n.name = '[K6] 训练耗时均低于 8s，满足 60s 时限；Beam Search 可行', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"经验": 860.0, "编号": 6.0}, "section": "可复用经验", "source_id": "K6", "来源": "全部", "经验": "训练耗时均低于 8s，满足 60s 时限；Beam Search 可行", "编号": "K6"}';
MERGE (n:Evidence {node_id: 'evidence.expert_rules'})
SET n.name = '证据源：assets/docs/expert_rules.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "专家经验", "file_sha256": "a937357a6a5598c3df7787d9807bd44c06b45a83dca27791fdb75cce2dc8a1e4", "path": "assets/docs/expert_rules.md"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E1'})
SET n.name = '[E1] EDUCATION 的 0/5/6、MARRIAGE 的 0 统一归入「其他」', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"经验": 560.0, "编号": 1.0}, "section": "1. 预处理经验", "source_id": "E1", "原因": "数据字典未定义，直接 One-Hot 会引入稀疏噪声或触发未知类别报错", "经验": "`EDUCATION` 的 0/5/6、`MARRIAGE` 的 0 统一归入「其他」", "编号": "E1"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E2'})
SET n.name = '[E2] PAY_* 的 -2 保留为独立类别，不裁剪为 0', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"经验": -20.0, "编号": 2.0}, "section": "1. 预处理经验", "source_id": "E2", "原因": "-2 表示无消费记录，与按时还款（-1）语义不同", "经验": "`PAY_*` 的 -2 保留为独立类别，不裁剪为 0", "编号": "E2"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E3'})
SET n.name = '[E3] BILL_AMT* 负值保留符号', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 3.0}, "section": "1. 预处理经验", "source_id": "E3", "原因": "负值代表退款/多付，取绝对值会丢失信息", "经验": "`BILL_AMT*` 负值保留符号", "编号": "E3"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E4'})
SET n.name = '[E4] 所有预处理器置于 sklearn.Pipeline 内并仅在训练集 fit', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 4.0}, "section": "1. 预处理经验", "source_id": "E4", "原因": "防止均值/编码统计量泄漏到验证集", "经验": "所有预处理器置于 `sklearn.Pipeline` 内并仅在训练集 fit", "编号": "E4"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E5'})
SET n.name = '[E5] 连续逾期月数是最强单一信号', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"派生方式": 260.0, "编号": 5.0}, "section": "2. 特征工程经验", "source_id": "E5", "派生方式": "统计 `PAY_0`、`PAY_2`…`PAY_6` 中 > 0 的期数", "经验": "连续逾期月数是最强单一信号", "编号": "E5"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E6'})
SET n.name = '[E6] 最大逾期等级', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"派生方式": 26.0, "编号": 6.0}, "section": "2. 特征工程经验", "source_id": "E6", "派生方式": "`max(PAY_0, PAY_2, …, PAY_6)`", "经验": "最大逾期等级", "编号": "E6"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E7'})
SET n.name = '[E7] 还款率需按期次对齐', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"派生方式": 219800.0, "编号": 7.0}, "section": "2. 特征工程经验", "source_id": "E7", "派生方式": "`PAY_AMT2 / BILL_AMT1`（9 月实付针对 8 月账单），分母为 0 时置 0", "经验": "还款率需按期次对齐", "编号": "E7"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E8'})
SET n.name = '[E8] 账单趋势', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 8.0}, "section": "2. 特征工程经验", "source_id": "E8", "派生方式": "`BILL_AMT1 - BILL_AMT6`、`BILL_AMT*` 均值与标准差", "经验": "账单趋势", "编号": "E8"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E9'})
SET n.name = '[E9] 额度使用率', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"派生方式": 100.0, "编号": 9.0}, "section": "2. 特征工程经验", "source_id": "E9", "派生方式": "`BILL_AMT1 / LIMIT_BAL`，`LIMIT_BAL = 0` 时置 0", "经验": "额度使用率", "编号": "E9"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E10'})
SET n.name = '[E10] 对 LIMIT_BAL、AGE、BILL_AMT1 做监督分箱（5–10 箱），计算 WOE 与 IV，IV < 0.02 的变量剔除', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"经验": 15100.02, "编号": 10.0}, "section": "3. WOE 分箱与评分卡", "source_id": "E10", "经验": "对 `LIMIT_BAL`、`AGE`、`BILL_AMT1` 做监督分箱（5–10 箱），计算 WOE 与 IV，IV < 0.02 的变量剔除", "编号": "E10"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E11'})
SET n.name = '[E11] WOE 变换后接逻辑回归，可输出标准评分卡分数，可解释性优于树模型，适合作为 baseline 候选', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 11.0}, "section": "3. WOE 分箱与评分卡", "source_id": "E11", "经验": "WOE 变换后接逻辑回归，可输出标准评分卡分数，可解释性优于树模型，适合作为 baseline 候选", "编号": "E11"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E12'})
SET n.name = '[E12] 分箱边界必须在训练集内学习，验证/测试集只做 apply', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 12.0}, "section": "3. WOE 分箱与评分卡", "source_id": "E12", "经验": "分箱边界必须在训练集内学习，验证/测试集只做 apply", "编号": "E12"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E13'})
SET n.name = '[E13] 逻辑回归 + WOE', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 13.0}, "section": "4. 模型选择经验", "source_id": "E13", "经验": "逻辑回归 + WOE", "编号": "E13", "适用条件": "需要可解释、需输出评分卡、样本量小"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E14'})
SET n.name = '[E14] 随机森林', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 14.0}, "section": "4. 模型选择经验", "source_id": "E14", "经验": "随机森林", "编号": "E14", "适用条件": "存在非线性交互，允许黑箱，需 `class_weight=\'balanced\'`"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E15'})
SET n.name = '[E15] HistGradientBoosting', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 15.0, "适用条件": 60.0}, "section": "4. 模型选择经验", "source_id": "E15", "经验": "HistGradientBoosting", "编号": "E15", "适用条件": "追求 AUC/KS 上限，注意限制 `max_iter` 以满足 60s 时限"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E16'})
SET n.name = '[E16] SMOTE', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 16.0}, "section": "4. 模型选择经验", "source_id": "E16", "经验": "SMOTE", "编号": "E16", "适用条件": "仅对训练集过采样，绝不能对全量数据采样；与 `class_weight` 二选一"}';
MERGE (n:Capability {node_id: 'cap.expert_rules.E17'})
SET n.name = '[E17] 阈值', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 17.0}, "section": "4. 模型选择经验", "source_id": "E17", "经验": "阈值", "编号": "E17", "适用条件": "按 5:1 成本比在验证集网格搜索，不在测试集调阈值"}';
MERGE (n:Operator {node_id: 'op.pipeline.01'})
SET n.name = '列名映射', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fit_on_train_only": true, "order": 1, "source_section": "依赖与顺序约束"}';
MERGE (n:Operator {node_id: 'op.pipeline.02'})
SET n.name = '类别清洗', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fit_on_train_only": true, "order": 2, "source_section": "依赖与顺序约束"}';
MERGE (n:Operator {node_id: 'op.pipeline.03'})
SET n.name = '特征派生', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fit_on_train_only": true, "order": 3, "source_section": "依赖与顺序约束"}';
MERGE (n:Operator {node_id: 'op.pipeline.04'})
SET n.name = 'WOE/编码', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fit_on_train_only": true, "order": 4, "source_section": "依赖与顺序约束"}';
MERGE (n:Operator {node_id: 'op.pipeline.05'})
SET n.name = '采样', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fit_on_train_only": true, "order": 5, "source_section": "依赖与顺序约束"}';
MERGE (n:Operator {node_id: 'op.pipeline.06'})
SET n.name = '模型', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fit_on_train_only": true, "order": 6, "source_section": "依赖与顺序约束"}';
MERGE (n:Operator {node_id: 'op.pipeline.07'})
SET n.name = '阈值', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"fit_on_train_only": true, "order": 7, "source_section": "依赖与顺序约束"}';
MERGE (n:Evidence {node_id: 'evidence.failure_review'})
SET n.name = '证据源：assets/docs/failure_review.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "失败复盘", "file_sha256": "e212416e3615bb62fac36346385b914f27c945deda4c1c536fd644db1981c857", "path": "assets/docs/failure_review.md"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.FR-01'})
SET n.name = '[FR-01] 列名假设错误', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"error_signature": "KeyError", "修复策略": "按 `Dataset` 节点的列名映射表替换为 `PAY_0`、`PAY_2`…`PAY_6`；禁止按序号硬编码列名", "可复用经验": "使用数据字典校验列名，而非按业务直觉推断", "根因": "工程师按 `PAY_1`…`PAY_6` 的直觉命名编写代码，实际数据集最近一期列名为 `PAY_0`，不存在 `PAY_1`", "现象": "`KeyError: \'PAY_1\'`", "错误签名": "`KeyError: PAY_1`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.FR-02'})
SET n.name = '[FR-02] 未文档化类别导致编码失败', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"error_signature": "SchemaError", "修复策略": "0/5/6 归入「其他」类别；`PAY_* = -2` 保留为独立类别；编码前做取值域校验", "可复用经验": "类别型特征的合法取值必须以数据实测为准，不能只信文档", "根因": "`EDUCATION` 实测含 0/5/6（345 条），`MARRIAGE` 含 0（54 条），均不在数据字典枚举内", "现象": "OneHotEncoder 报未知类别 / schema 校验失败", "错误签名": "`SchemaError`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.FR-03'})
SET n.name = '[FR-03] 数据泄漏导致指标虚高', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"error_signature": "LeakageDetected", "修复策略": "改时间外划分；强制 `sklearn.Pipeline` 且所有预处理器仅 on train fit；按 `PRECEDES` 约束检查期次", "可复用经验": "指标显著高于历史记录时，优先怀疑泄漏而非庆祝提升", "根因": "① 使用随机划分而非时间外划分；② 在全量数据上 fit 标准化/编码器；③ 使用了与目标同期的付款信息", "现象": "验证 AUC 0.912，显著高于历史 0.78 量级；上线后效果骤降", "错误签名": "`LeakageDetected` / `MetricSuspiciouslyHigh`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.FR-04'})
SET n.name = '[FR-04] 阈值选择错误', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"error_signature": "CostLossAboveBaseline", "修复策略": "在验证集上按成本加权损失网格搜索最优阈值，测试集不参与调阈", "可复用经验": "分类阈值是业务决策，不是超参数默认值", "根因": "沿用 0.5 默认阈值，忽略 5:1 的漏报/误报成本比", "现象": "AUC 达标但业务损失偏高", "错误签名": "`CostLossAboveBaseline`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.FR-05'})
SET n.name = '[FR-05] 采样时机错误', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"error_signature": "LeakageDetected", "修复策略": "采样仅在训练集内、且在 Pipeline 内执行", "可复用经验": "任何改变样本分布的操作都必须在划分之后", "根因": "对全量数据先做 SMOTE 再划分，合成样本跨训练/验证集", "现象": "验证指标虚高且不可复现", "错误签名": "`LeakageDetected`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.r01'})
SET n.name = '[r01] 列名映射', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "错误签名 → 修复策略速查", "source_id": "r01", "定向修复": "列名映射", "签名": "`KeyError: PAY_1`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.r02'})
SET n.name = '[r02] 类别归一化 + 取值域校验', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "错误签名 → 修复策略速查", "source_id": "r02", "定向修复": "类别归一化 + 取值域校验", "签名": "`SchemaError`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.r03'})
SET n.name = '[r03] 时间外划分 + Pipeline 约束', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "错误签名 → 修复策略速查", "source_id": "r03", "定向修复": "时间外划分 + Pipeline 约束", "签名": "`LeakageDetected`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.r04'})
SET n.name = '[r04] 检索历史高分方案，切换模型族/采样/阈值', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "错误签名 → 修复策略速查", "source_id": "r04", "定向修复": "检索历史高分方案，切换模型族/采样/阈值", "签名": "`MetricBelowThreshold`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.r05'})
SET n.name = '[r05] 降采样或换轻量模型', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "错误签名 → 修复策略速查", "source_id": "r05", "定向修复": "降采样或换轻量模型", "签名": "`Timeout`"}';
MERGE (n:FailureCase {node_id: 'fail.failure_review.r06'})
SET n.name = '[r06] 注入 random_state', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "错误签名 → 修复策略速查", "source_id": "r06", "定向修复": "注入 `random_state`", "签名": "`Nondeterminism`"}';
MERGE (n:Evidence {node_id: 'evidence.risk_policy'})
SET n.name = '证据源：assets/docs/risk_policy.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "风控策略", "file_sha256": "65132022264e88c7552c8d681aa03b3c5d55eefee9fd18d38037b207f549c1fd", "path": "assets/docs/risk_policy.md"}';
MERGE (n:Capability {node_id: 'cap.risk_policy.C1'})
SET n.name = '[C1] 客群范围', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 1.0, "说明": 6.0}, "section": "2. 适用条件（约束）", "source_id": "C1", "约束": "客群范围", "编号": "C1", "说明": "仅适用于持有 ≥6 期账单历史的存量客户；新客无 `PAY_*` / `BILL_AMT*` 序列，不在适用范围内"}';
MERGE (n:Capability {node_id: 'cap.risk_policy.C2'})
SET n.name = '[C2] 额度区间', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 2.0}, "section": "2. 适用条件（约束）", "source_id": "C2", "约束": "额度区间", "编号": "C2", "说明": "`LIMIT_BAL` 在本样本覆盖区间内；超出区间需人工复核"}';
MERGE (n:Capability {node_id: 'cap.risk_policy.C3'})
SET n.name = '[C3] 时间范围', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 3.0}, "section": "2. 适用条件（约束）", "source_id": "C3", "约束": "时间范围", "编号": "C3", "说明": "训练样本观测期为 2005-04 至 2005-09；上线前须做 PSI 群体稳定性检查，PSI > 0.25 触发重训"}';
MERGE (n:Capability {node_id: 'cap.risk_policy.C4'})
SET n.name = '[C4] 划分方式', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 4.0}, "section": "2. 适用条件（约束）", "source_id": "C4", "约束": "划分方式", "编号": "C4", "说明": "必须时间外划分，禁止随机打乱；所有预处理在训练集内 fit"}';
MERGE (n:Capability {node_id: 'cap.risk_policy.C5'})
SET n.name = '[C5] 敏感字段', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 5.0}, "section": "2. 适用条件（约束）", "source_id": "C5", "约束": "敏感字段", "编号": "C5", "说明": "`SEX` / `AGE` / `EDUCATION` / `MARRIAGE` 不得进入模型特征，仅用于分组公平性审计"}';
MERGE (n:Capability {node_id: 'cap.risk_policy.C6'})
SET n.name = '[C6] 标识字段', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 6.0}, "section": "2. 适用条件（约束）", "source_id": "C6", "约束": "标识字段", "编号": "C6", "说明": "`ID` 不得作为特征"}';
MERGE (n:Capability {node_id: 'cap.risk_policy.C7'})
SET n.name = '[C7] 可复现', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 7.0, "说明": 42602.0}, "section": "2. 适用条件（约束）", "source_id": "C7", "约束": "可复现", "编号": "C7", "说明": "固定随机种子 42，单次运行 60 秒内、内存 2GB 以内"}';
MERGE (n:Metric {node_id: 'metric.risk_policy.r01'})
SET n.name = '[r01] 越大越好', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"门槛": 0.78}, "section": "4. 验收门槛（目标值，非实测结果）", "source_id": "r01", "指标": "AUC", "方向": "越大越好", "门槛": "≥ 0.78"}';
MERGE (n:Metric {node_id: 'metric.risk_policy.r02'})
SET n.name = '[r02] 越大越好', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"门槛": 0.35}, "section": "4. 验收门槛（目标值，非实测结果）", "source_id": "r02", "指标": "KS", "方向": "越大越好", "门槛": "≥ 0.35"}';
MERGE (n:Metric {node_id: 'metric.risk_policy.r03'})
SET n.name = '[r03] 越大越好', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"门槛": 0.5}, "section": "4. 验收门槛（目标值，非实测结果）", "source_id": "r03", "指标": "PR-AUC", "方向": "越大越好", "门槛": "≥ 0.50"}';
MERGE (n:Metric {node_id: 'metric.risk_policy.r04'})
SET n.name = '[r04] 越小越好', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"门槛": 0.1}, "section": "4. 验收门槛（目标值，非实测结果）", "source_id": "r04", "指标": "分组 AUC 差异", "方向": "越小越好", "门槛": "≤ 0.10"}';
MERGE (n:Evidence {node_id: 'evidence.test_report'})
SET n.name = '证据源：assets/docs/test_report.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "测试报告", "file_sha256": "b52820419a10325ef552814bc32ff798524186bfaf4f214bd9da7774ca99df90", "path": "assets/docs/test_report.md"}';
MERGE (n:Metric {node_id: 'metric.test_report.r01'})
SET n.name = '[r01] build_pipeline() 签名', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r01", "判定方法": "AST 解析函数签名", "层": "接口规范", "检查项": "`build_pipeline()` 签名"}';
MERGE (n:Metric {node_id: 'metric.test_report.r02'})
SET n.name = '[r02] 输出列 pd / label / score 及 dtype', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r02", "判定方法": "契约比对", "层": "接口规范", "检查项": "输出列 `pd` / `label` / `score` 及 dtype"}';
MERGE (n:Metric {node_id: 'metric.test_report.r03'})
SET n.name = '[r03] pd ∈ [0,1]', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"检查项": 1.0}, "section": "1. 四层验证检查项", "source_id": "r03", "判定方法": "逐行断言", "层": "接口规范", "检查项": "`pd` ∈ [0,1]"}';
MERGE (n:Metric {node_id: 'metric.test_report.r04'})
SET n.name = '[r04] 禁 ID 入模、禁读标签路径', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r04", "判定方法": "AST 名称检查", "层": "接口规范", "检查项": "禁 `ID` 入模、禁读标签路径"}';
MERGE (n:Metric {node_id: 'metric.test_report.r05'})
SET n.name = '[r05] import 白名单', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r05", "判定方法": "AST 检查，禁止 os.system / subprocess / socket", "层": "接口规范", "检查项": "import 白名单"}';
MERGE (n:Metric {node_id: 'metric.test_report.r06'})
SET n.name = '[r06] 小样本 smoke、无 NaN', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r06", "判定方法": "沙箱执行", "层": "功能正确性", "检查项": "小样本 smoke、无 NaN"}';
MERGE (n:Metric {node_id: 'metric.test_report.r07'})
SET n.name = '[r07] fit/predict 幂等、固定种子两次输出一致', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r07", "判定方法": "重复运行比对", "层": "功能正确性", "检查项": "fit/predict 幂等、固定种子两次输出一致"}';
MERGE (n:Metric {node_id: 'metric.test_report.r08'})
SET n.name = '[r08] 单类别、全缺失列边界输入', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r08", "判定方法": "合成边界样本", "层": "功能正确性", "检查项": "单类别、全缺失列边界输入"}';
MERGE (n:Metric {node_id: 'metric.test_report.r09'})
SET n.name = '[r09] AUC / KS / PR-AUC / F1 / 成本损失 / PSI / 分组 AUC 差异', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"检查项": -1.0}, "section": "1. 四层验证检查项", "source_id": "r09", "判定方法": "时间外划分 + baseline 对照", "层": "指标表现", "检查项": "AUC / KS / PR-AUC / F1 / 成本损失 / PSI / 分组 AUC 差异"}';
MERGE (n:Metric {node_id: 'metric.test_report.r10'})
SET n.name = '[r10] test 集仅终评一次', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r10", "判定方法": "运行日志审计", "层": "指标表现", "检查项": "test 集仅终评一次"}';
MERGE (n:Metric {node_id: 'metric.test_report.r11'})
SET n.name = '[r11] 单次 ≤ 60s、内存 ≤ 2GB', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"检查项": 602.0}, "section": "1. 四层验证检查项", "source_id": "r11", "判定方法": "子进程资源限制", "层": "运行稳定性", "检查项": "单次 ≤ 60s、内存 ≤ 2GB"}';
MERGE (n:Metric {node_id: 'metric.test_report.r12'})
SET n.name = '[r12] 重复运行方差、依赖版本校验', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"section": "1. 四层验证检查项", "source_id": "r12", "判定方法": "多次运行比对", "层": "运行稳定性", "检查项": "重复运行方差、依赖版本校验"}';
MERGE (n:ValidationRun {node_id: 'run.test_report.RUN-legacy-01'})
SET n.name = '[RUN-legacy-01] 历史评分卡脚本', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"修复轮次": 3.0}, "section": "3. 历史样例结论（构造数据）", "source_id": "RUN-legacy-01", "修复轮次": "3", "四层结论": "接口 FAIL、功能 FAIL、指标 FAIL、稳定性 PASS", "方案": "历史评分卡脚本", "最终状态": "通过（修复后）", "运行": "RUN-legacy-01"}';
MERGE (n:ValidationRun {node_id: 'run.test_report.RUN-legacy-02'})
SET n.name = '[RUN-legacy-02] WOE + LR', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"修复轮次": 0.0}, "section": "3. 历史样例结论（构造数据）", "source_id": "RUN-legacy-02", "修复轮次": "0", "四层结论": "四层 PASS", "方案": "WOE + LR", "最终状态": "通过", "运行": "RUN-legacy-02"}';
MERGE (n:ValidationRun {node_id: 'run.test_report.RUN-legacy-03'})
SET n.name = '[RUN-legacy-03] HistGB + SMOTE', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"修复轮次": 2.0}, "section": "3. 历史样例结论（构造数据）", "source_id": "RUN-legacy-03", "修复轮次": "2", "四层结论": "接口 PASS、功能 PASS、指标 FAIL、稳定性 FAIL", "方案": "HistGB + SMOTE", "最终状态": "通过", "运行": "RUN-legacy-03"}';
MERGE (n:Evidence {node_id: 'evidence.legacy_default_model'})
SET n.name = '证据源：assets/legacy/legacy_default_model.py', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "历史代码", "file_sha256": "de226005c94a6953799ed790c083fcd6d2b1e58662680b7d11e2404187d6c287", "path": "assets/legacy/legacy_default_model.py"}';
MERGE (n:Algorithm {node_id: 'algo.legacy_default_model.load_raw'})
SET n.name = 'load_raw', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"args": ["path"], "docstring": "读取原始客户账单数据。", "lineno": 26}';
MERGE (n:Algorithm {node_id: 'algo.legacy_default_model.build_features'})
SET n.name = 'build_features', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"args": ["df"], "docstring": "构造历史评分卡特征。\\n\\n缺陷 2：未剔除 ID 标识列。\\n缺陷 3：未处理 EDUCATION / MARRIAGE 的未文档化类别。", "lineno": 31}';
MERGE (n:Algorithm {node_id: 'algo.legacy_default_model.train_default_model'})
SET n.name = 'train_default_model', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"args": ["df"], "docstring": "训练历史逻辑回归评分卡，返回结果字典。\\n\\n缺陷 4：在全量数据上 fit 标准化器，统计量泄漏到验证集。\\n缺陷 5：使用随机划分，对「下月违约」标签引入未来信息。\\n缺陷 6：以 accuracy 作为验收指标，正例仅 22.12% 时结论失真。", "lineno": 42}';
MERGE (n:Algorithm {node_id: 'algo.legacy_default_model.score_to_rating'})
SET n.name = 'score_to_rating', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"args": ["probability"], "docstring": "把违约概率映射为内部评级（历史规则）。", "lineno": 61}';
MERGE (n:FailureCase {node_id: 'fail.legacy_default_model.defect022'})
SET n.name = '[缺陷22] 数据集中最近一期的列名是 PAY_0，并不存在 PAY_1', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"description": "数据集中最近一期的列名是 PAY_0，并不存在 PAY_1", "error_signature": null, "lineno": 22}';
MERGE (n:Environment {node_id: 'env.legacy_default_model'})
SET n.name = '历史代码依赖环境', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"lib_deps": ["__future__", "pandas", "sklearn.linear_model", "sklearn.metrics", "sklearn.model_selection", "sklearn.preprocessing"], "python_version": "3.11+"}';

MATCH (a {node_id: 'dataset.data_dictionary'}), (b {node_id: 'evidence.data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'evidence.data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'evidence.data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2b'}), (b {node_id: 'evidence.data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3'}), (b {node_id: 'evidence.data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3b'}), (b {node_id: 'evidence.data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T4'}), (b {node_id: 'evidence.data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE1'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE2'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE3'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE4'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE5'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE6'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE7'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE8'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE9'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE10'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE11'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'lesson.engineering_lessons.LE12'}), (b {node_id: 'evidence.engineering_lessons'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-01'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-02'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-03'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-04'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-05'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-06'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-07'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-08'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K4'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K5'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K6'}), (b {node_id: 'evidence.experiment_log'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E1'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E2'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E3'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E5'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E6'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E7'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E8'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E9'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E12'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.01'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.02'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.01'}), (b {node_id: 'op.pipeline.02'})
MERGE (a)-[:PRECEDES]->(b);
MATCH (a {node_id: 'op.pipeline.03'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.02'}), (b {node_id: 'op.pipeline.03'})
MERGE (a)-[:PRECEDES]->(b);
MATCH (a {node_id: 'op.pipeline.04'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.03'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:PRECEDES]->(b);
MATCH (a {node_id: 'op.pipeline.05'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.04'}), (b {node_id: 'op.pipeline.05'})
MERGE (a)-[:PRECEDES]->(b);
MATCH (a {node_id: 'op.pipeline.06'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.05'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:PRECEDES]->(b);
MATCH (a {node_id: 'op.pipeline.07'}), (b {node_id: 'evidence.expert_rules'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'op.pipeline.06'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:PRECEDES]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-01'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-02'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-03'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-04'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-05'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.r01'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.r02'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.r03'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.r04'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.r05'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.r06'}), (b {node_id: 'evidence.failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C1'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C2'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C3'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C4'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C5'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C6'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C7'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.risk_policy.r01'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.risk_policy.r02'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.risk_policy.r03'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.risk_policy.r04'}), (b {node_id: 'evidence.risk_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r01'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r02'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r03'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r04'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r05'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r06'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r07'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r08'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r09'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r10'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r11'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.test_report.r12'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.test_report.RUN-legacy-01'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.test_report.RUN-legacy-02'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'run.test_report.RUN-legacy-03'}), (b {node_id: 'evidence.test_report'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'algo.legacy_default_model.load_raw'}), (b {node_id: 'evidence.legacy_default_model'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'algo.legacy_default_model.build_features'}), (b {node_id: 'evidence.legacy_default_model'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'algo.legacy_default_model.train_default_model'}), (b {node_id: 'evidence.legacy_default_model'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'algo.legacy_default_model.score_to_rating'}), (b {node_id: 'evidence.legacy_default_model'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.legacy_default_model.defect022'}), (b {node_id: 'evidence.legacy_default_model'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'env.legacy_default_model'}), (b {node_id: 'evidence.legacy_default_model'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'op.pipeline.01'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'metric.risk_policy.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'metric.test_report.r09'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'metric.risk_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'metric.risk_policy.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'metric.test_report.r09'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'metric.test_report.r07'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E12'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'metric.risk_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'metric.risk_policy.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'metric.test_report.r09'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'op.pipeline.05'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C1'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.risk_policy.C2'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.risk_policy.C3'}), (b {node_id: 'metric.test_report.r09'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C3'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.risk_policy.C4'}), (b {node_id: 'metric.test_report.r07'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C4'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.risk_policy.C5'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C5'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.risk_policy.C6'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.risk_policy.C7'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'cap.data_dictionary.T2'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'cap.expert_rules.E4'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'cap.expert_rules.E4'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'cap.experiment_log.K3'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'cap.expert_rules.E10'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'cap.expert_rules.E11'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'cap.expert_rules.E12'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'cap.expert_rules.E13'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'cap.expert_rules.E15'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'cap.expert_rules.E11'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'cap.expert_rules.E13'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'cap.expert_rules.E14'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'cap.expert_rules.E15'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'cap.expert_rules.E16'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'cap.expert_rules.E17'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'cap.risk_policy.C5'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'cap.expert_rules.E15'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'cap.risk_policy.C4'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'cap.expert_rules.E11'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'cap.expert_rules.E12'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'cap.expert_rules.E13'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'cap.expert_rules.E12'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'cap.expert_rules.E13'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'cap.expert_rules.E14'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'cap.expert_rules.E15'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'cap.expert_rules.E16'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'cap.expert_rules.E17'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'cap.risk_policy.C5'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E12'}), (b {node_id: 'cap.expert_rules.E13'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'cap.expert_rules.E14'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'cap.expert_rules.E15'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'cap.expert_rules.E16'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'cap.expert_rules.E17'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'cap.risk_policy.C5'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'cap.expert_rules.E15'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'cap.expert_rules.E16'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'cap.expert_rules.E17'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'cap.risk_policy.C5'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'cap.expert_rules.E16'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'cap.expert_rules.E17'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'cap.risk_policy.C5'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'cap.expert_rules.E17'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'cap.risk_policy.C5'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'cap.risk_policy.C5'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'fail.failure_review.r01'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:FIXED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.r04'}), (b {node_id: 'cap.experiment_log.K2'})
MERGE (a)-[:FIXED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'metric.risk_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'metric.risk_policy.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'op.pipeline.02'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2b'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2b'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2b'}), (b {node_id: 'metric.risk_policy.r03'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2b'}), (b {node_id: 'op.pipeline.03'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3'}), (b {node_id: 'metric.risk_policy.r04'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3b'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3b'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3b'}), (b {node_id: 'metric.test_report.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3b'}), (b {node_id: 'op.pipeline.05'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T4'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T4'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T4'}), (b {node_id: 'metric.test_report.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T4'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'metric.test_report.r03'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K1'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'metric.test_report.r04'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K2'}), (b {node_id: 'op.pipeline.01'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'metric.test_report.r05'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K3'}), (b {node_id: 'op.pipeline.02'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K4'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K4'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.experiment_log.K4'}), (b {node_id: 'metric.test_report.r06'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K4'}), (b {node_id: 'op.pipeline.03'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K5'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K5'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.experiment_log.K5'}), (b {node_id: 'metric.test_report.r07'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K5'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.experiment_log.K6'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.experiment_log.K6'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.experiment_log.K6'}), (b {node_id: 'metric.test_report.r08'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.experiment_log.K6'}), (b {node_id: 'op.pipeline.05'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E1'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E1'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E1'}), (b {node_id: 'metric.test_report.r09'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E1'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E2'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E2'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E2'}), (b {node_id: 'metric.test_report.r10'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E2'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E3'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E3'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E3'}), (b {node_id: 'metric.test_report.r11'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E3'}), (b {node_id: 'op.pipeline.01'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'metric.test_report.r12'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E4'}), (b {node_id: 'op.pipeline.02'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E5'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E5'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E5'}), (b {node_id: 'metric.risk_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E5'}), (b {node_id: 'op.pipeline.03'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E6'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E6'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E6'}), (b {node_id: 'metric.risk_policy.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E6'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E7'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E7'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E7'}), (b {node_id: 'metric.risk_policy.r03'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E7'}), (b {node_id: 'op.pipeline.05'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E8'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E8'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E8'}), (b {node_id: 'metric.risk_policy.r04'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E8'}), (b {node_id: 'op.pipeline.06'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E9'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E9'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E9'}), (b {node_id: 'metric.test_report.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E9'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'metric.test_report.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E10'}), (b {node_id: 'op.pipeline.01'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'metric.test_report.r03'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E11'}), (b {node_id: 'op.pipeline.02'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E12'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E12'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E12'}), (b {node_id: 'metric.test_report.r04'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E12'}), (b {node_id: 'op.pipeline.03'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E13'}), (b {node_id: 'metric.test_report.r05'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'metric.test_report.r06'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E14'}), (b {node_id: 'op.pipeline.05'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E15'}), (b {node_id: 'metric.test_report.r07'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'metric.test_report.r08'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E16'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'metric.test_report.r09'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.expert_rules.E17'}), (b {node_id: 'op.pipeline.01'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C1'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.risk_policy.C1'}), (b {node_id: 'metric.test_report.r10'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C1'}), (b {node_id: 'op.pipeline.02'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C2'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.risk_policy.C2'}), (b {node_id: 'metric.test_report.r11'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C2'}), (b {node_id: 'op.pipeline.03'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C3'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.risk_policy.C3'}), (b {node_id: 'metric.test_report.r12'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C3'}), (b {node_id: 'op.pipeline.04'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C4'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.risk_policy.C4'}), (b {node_id: 'metric.risk_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C4'}), (b {node_id: 'op.pipeline.05'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C5'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.risk_policy.C5'}), (b {node_id: 'metric.risk_policy.r02'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C6'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.risk_policy.C6'}), (b {node_id: 'metric.risk_policy.r03'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C6'}), (b {node_id: 'op.pipeline.07'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.risk_policy.C7'}), (b {node_id: 'env.legacy_default_model'})
MERGE (a)-[:DEPENDS_ON]->(b);
MATCH (a {node_id: 'cap.risk_policy.C7'}), (b {node_id: 'metric.risk_policy.r04'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.risk_policy.C7'}), (b {node_id: 'op.pipeline.01'})
MERGE (a)-[:USES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'dataset.data_dictionary'})
MERGE (a)-[:REQUIRES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'op.pipeline.01'})
MERGE (a)-[:REQUIRES]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:DERIVED_FROM]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2b'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:DERIVED_FROM]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T3'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:DERIVED_FROM]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2'}), (b {node_id: 'cap.data_dictionary.T2b'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T2b'}), (b {node_id: 'cap.data_dictionary.T3'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'cap.data_dictionary.T3b'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'run.experiment_log.EXP-01'})
MERGE (a)-[:HAS_RUN]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-01'}), (b {node_id: 'fail.failure_review.FR-01'})
MERGE (a)-[:RESULTED_IN]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'run.experiment_log.EXP-02'})
MERGE (a)-[:HAS_RUN]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-02'}), (b {node_id: 'fail.failure_review.FR-01'})
MERGE (a)-[:RESULTED_IN]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'run.experiment_log.EXP-03'})
MERGE (a)-[:HAS_RUN]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-03'}), (b {node_id: 'fail.failure_review.FR-01'})
MERGE (a)-[:RESULTED_IN]->(b);
MATCH (a {node_id: 'cap.data_dictionary.T1'}), (b {node_id: 'run.experiment_log.EXP-04'})
MERGE (a)-[:HAS_RUN]->(b);
MATCH (a {node_id: 'run.experiment_log.EXP-04'}), (b {node_id: 'fail.failure_review.FR-01'})
MERGE (a)-[:RESULTED_IN]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-01'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:FIXED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-02'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:FIXED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-03'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:FIXED_BY]->(b);
MATCH (a {node_id: 'fail.failure_review.FR-04'}), (b {node_id: 'cap.data_dictionary.T1'})
MERGE (a)-[:FIXED_BY]->(b);
