// AlgoCap Factory 知识图谱导出（Cypher，Neo4j 5.x）
// 节点 30 个 / 边 45 条
// 用法：cat <this-file>.cypher | cypher-shell -u neo4j -p <password>

CREATE CONSTRAINT capability_node_id IF NOT EXISTS FOR (n:Capability) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT metric_node_id IF NOT EXISTS FOR (n:Metric) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT failurecase_node_id IF NOT EXISTS FOR (n:FailureCase) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT lesson_node_id IF NOT EXISTS FOR (n:Lesson) REQUIRE n.node_id IS UNIQUE;
CREATE CONSTRAINT evidence_node_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.node_id IS UNIQUE;

MERGE (n:Evidence {node_id: 'evidence.sms_data_dictionary'})
SET n.name = '证据源：assets/docs/text/sms_data_dictionary.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "业务文档", "file_sha256": "c33f877a47ef29b52673b949a556d32e81ade82759a24cacc4fb930632451176", "path": "assets/docs/text/sms_data_dictionary.md"}';
MERGE (n:Capability {node_id: 'cap.sms_data_dictionary.ST1'})
SET n.name = '[ST1] 大小写与标点不统一', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 1.0}, "section": "2. 已知数据问题", "source_id": "ST1", "处理方式": "统一小写后再做 TF-IDF，数字保留", "编号": "ST1", "问题": "大小写与标点不统一"}';
MERGE (n:Capability {node_id: 'cap.sms_data_dictionary.ST2'})
SET n.name = '[ST2] 正文含电话号码与短链接', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 2.0}, "section": "2. 已知数据问题", "source_id": "ST2", "处理方式": "替换为 `phone` / `url` 占位符，避免记忆具体号码", "编号": "ST2", "问题": "正文含电话号码与短链接"}';
MERGE (n:Capability {node_id: 'cap.sms_data_dictionary.ST3'})
SET n.name = '[ST3] 极短文本与重复文本', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"处理方式": 3.0, "编号": 3.0}, "section": "2. 已知数据问题", "source_id": "ST3", "处理方式": "长度 < 3 的样本剔除；重复文本只在训练集保留一份", "编号": "ST3", "问题": "极短文本与重复文本"}';
MERGE (n:Capability {node_id: 'cap.sms_data_dictionary.ST4'})
SET n.name = '[ST4] 标签分布偏斜', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 4.0}, "section": "2. 已知数据问题", "source_id": "ST4", "处理方式": "spam 13.4%，评估用 macro-F1，必要时在 Pipeline 内做类别权重", "编号": "ST4", "问题": "标签分布偏斜"}';
MERGE (n:Evidence {node_id: 'evidence.sms_failure_review'})
SET n.name = '证据源：assets/docs/text/sms_failure_review.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "失败复盘", "file_sha256": "248b9ca40f057691a43ba0cfbb7f3880cb7426259c6046ab9018a9f53cfc062b", "path": "assets/docs/text/sms_failure_review.md"}';
MERGE (n:FailureCase {node_id: 'fail.sms_failure_review.FR-01'})
SET n.name = '[FR-01] 向量器在测试集上 fit 导致指标虚高', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"error_signature": "LeakageDetected", "修复策略": "向量器放进 `sklearn.Pipeline`，只在训练集 fit；划分前不触碰测试集", "可复用经验": "文本任务的泄漏比表格更隐蔽，必须由 Pipeline 结构保证，而不是靠人工纪律", "根因": "划分前对全量文本 `TfidfVectorizer.fit`，测试集词表与 IDF 泄漏进训练", "现象": "accuracy 0.997、macro-F1 0.985，上线后掉到 0.94", "错误签名": "`LeakageDetected`"}';
MERGE (n:FailureCase {node_id: 'fail.sms_failure_review.FR-02'})
SET n.name = '[FR-02] 只看 accuracy 掩盖少数类误杀', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"error_signature": "MetricBelowThreshold", "修复策略": "主指标改为 macro-F1 与 spam 召回，配合 `class_weight=\\"balanced\\"`", "可复用经验": "类别不平衡场景禁止用 accuracy 单独验收", "根因": "正例仅 13.4%，全判 ham 也能拿到 0.866 的 accuracy", "现象": "accuracy 0.98 看似达标，但 spam 召回只有 0.71，大量垃圾短信漏过", "错误签名": "`MetricBelowThreshold`"}';
MERGE (n:Evidence {node_id: 'evidence.sms_policy'})
SET n.name = '证据源：assets/docs/text/sms_policy.md', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"doc_type": "风控策略", "file_sha256": "45cb52fd9dc68b75110e3eb1f504716afeb2a87099db02585d25aefb529b7506", "path": "assets/docs/text/sms_policy.md"}';
MERGE (n:Capability {node_id: 'cap.sms_policy.S1'})
SET n.name = '[S1] 文本长度', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 1.0, "说明": 3.0}, "section": "2. 适用条件（约束）", "source_id": "S1", "约束": "文本长度", "编号": "S1", "说明": "少于 3 个字符的样本不参与训练，避免噪声主导词表"}';
MERGE (n:Capability {node_id: 'cap.sms_policy.S2'})
SET n.name = '[S2] 语言范围', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 2.0}, "section": "2. 适用条件（约束）", "source_id": "S2", "约束": "语言范围", "编号": "S2", "说明": "当前仅覆盖英文短信；中文短信需要另行分词，不能直接复用本词表"}';
MERGE (n:Capability {node_id: 'cap.sms_policy.S3'})
SET n.name = '[S3] 类别严重不平衡', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 3.0}, "section": "2. 适用条件（约束）", "source_id": "S3", "约束": "类别严重不平衡", "编号": "S3", "说明": "spam 约 13.4%，评估必须同时看 macro-F1，禁止只看 accuracy"}';
MERGE (n:Capability {node_id: 'cap.sms_policy.S4'})
SET n.name = '[S4] 词表边界', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 4.0}, "section": "2. 适用条件（约束）", "source_id": "S4", "约束": "词表边界", "编号": "S4", "说明": "向量器只能在训练集 fit，禁止在验证集 / 测试集上统计词表"}';
MERGE (n:Capability {node_id: 'cap.sms_policy.S5'})
SET n.name = '[S5] 号码与链接', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 5.0}, "section": "2. 适用条件（约束）", "source_id": "S5", "约束": "号码与链接", "编号": "S5", "说明": "电话、URL 用占位符替换，禁止让模型记住具体号码"}';
MERGE (n:Capability {node_id: 'cap.sms_policy.S6'})
SET n.name = '[S6] 判定阈值', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"编号": 6.0, "说明": 0.5}, "section": "2. 适用条件（约束）", "source_id": "S6", "约束": "判定阈值", "编号": "S6", "说明": "默认 0.5；业务可通过调阈值控制误杀率，调阈只在验证集做"}';
MERGE (n:Metric {node_id: 'metric.sms_policy.r01'})
SET n.name = '[r01] 0.95', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"门槛": 0.95}, "section": "3. 验收门槛", "source_id": "r01", "口径": "验证集，固定种子随机切分", "指标": "accuracy", "门槛": "0.95"}';
MERGE (n:Metric {node_id: 'metric.sms_policy.macro_f1'})
SET n.name = '[macro_f1] 0.90', n.version = 'v1', n.task_type = 'tabular_binary_classification', n.status = 'active', n.attributes_json = '{"metrics": {"指标": 1.0, "门槛": 0.9}, "section": "3. 验收门槛", "source_id": "macro_f1", "口径": "验证集，兼顾 spam 少数类", "指标": "macro_f1", "门槛": "0.90"}';
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

MATCH (a {node_id: 'cap.sms_data_dictionary.ST1'}), (b {node_id: 'evidence.sms_data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST2'}), (b {node_id: 'evidence.sms_data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST3'}), (b {node_id: 'evidence.sms_data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST4'}), (b {node_id: 'evidence.sms_data_dictionary'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.sms_failure_review.FR-01'}), (b {node_id: 'evidence.sms_failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'fail.sms_failure_review.FR-02'}), (b {node_id: 'evidence.sms_failure_review'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S1'}), (b {node_id: 'evidence.sms_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S2'}), (b {node_id: 'evidence.sms_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S3'}), (b {node_id: 'evidence.sms_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S4'}), (b {node_id: 'evidence.sms_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S5'}), (b {node_id: 'evidence.sms_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S6'}), (b {node_id: 'evidence.sms_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.sms_policy.r01'}), (b {node_id: 'evidence.sms_policy'})
MERGE (a)-[:EVIDENCED_BY]->(b);
MATCH (a {node_id: 'metric.sms_policy.macro_f1'}), (b {node_id: 'evidence.sms_policy'})
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
MATCH (a {node_id: 'cap.sms_policy.S3'}), (b {node_id: 'metric.sms_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST1'}), (b {node_id: 'metric.sms_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST2'}), (b {node_id: 'metric.sms_policy.macro_f1'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST3'}), (b {node_id: 'metric.sms_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST4'}), (b {node_id: 'metric.sms_policy.macro_f1'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S1'}), (b {node_id: 'metric.sms_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S2'}), (b {node_id: 'metric.sms_policy.macro_f1'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S4'}), (b {node_id: 'metric.sms_policy.macro_f1'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S5'}), (b {node_id: 'metric.sms_policy.r01'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_policy.S6'}), (b {node_id: 'metric.sms_policy.macro_f1'})
MERGE (a)-[:EVALUATED_BY]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST2'}), (b {node_id: 'cap.sms_data_dictionary.ST1'})
MERGE (a)-[:DERIVED_FROM]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST3'}), (b {node_id: 'cap.sms_data_dictionary.ST1'})
MERGE (a)-[:DERIVED_FROM]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST4'}), (b {node_id: 'cap.sms_data_dictionary.ST1'})
MERGE (a)-[:DERIVED_FROM]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST1'}), (b {node_id: 'cap.sms_data_dictionary.ST2'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST2'}), (b {node_id: 'cap.sms_data_dictionary.ST3'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST3'}), (b {node_id: 'cap.sms_data_dictionary.ST4'})
MERGE (a)-[:SIMILAR_TO]->(b);
MATCH (a {node_id: 'cap.sms_data_dictionary.ST1'}), (b {node_id: 'cap.sms_policy.S1'})
MERGE (a)-[:TRANSFERABLE_TO]->(b);
MATCH (a {node_id: 'fail.sms_failure_review.FR-01'}), (b {node_id: 'cap.sms_data_dictionary.ST1'})
MERGE (a)-[:FIXED_BY]->(b);
MATCH (a {node_id: 'fail.sms_failure_review.FR-02'}), (b {node_id: 'cap.sms_data_dictionary.ST1'})
MERGE (a)-[:FIXED_BY]->(b);
