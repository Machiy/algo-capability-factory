---
description: 算法能力工厂的架构与验证约束
alwaysApply: true
enabled: true
---

# 架构与验证约束

- 六层结构：contracts / knowledge / agents / runtime / validation / 接入层；模块间只通过契约数据类交互。
- 知识图谱的检索结果必须进入 Planner 与 Coder 的 prompt，不能只做静态展示。
- 生成代码必须在子进程沙箱中执行：超时 60s、内存上限、AST import 白名单。
- 四层验证缺一不可：接口规范、功能正确性、指标表现、运行稳定性。
- 修复必须先分类错误签名再定向处理，最多 3 轮；每轮结果回写知识图谱。
- 测试集仅在终评使用一次；指标门槛以 `configs/verify_*.yaml` 为准，不硬编码。
- 新任务类型通过新增 `verify_*.yaml` 与指标插件接入，不修改核心验证器。
