# 验证报告 · baseline-p2

> 范围：验证框架自检 / baseline（非最终验收）。最终验收数值在 P5 实测后由生成算法的验证报告替换。

- 方案：baseline_logreg
- 任务类型：tabular_binary_classification
- 通过状态：**FAIL**
- 错误签名：OSError: [WinError 10106] 无法加载或初始化请求的服务提供程序。

## 1. 接口规范


- syntax：PASS

- build_pipeline_signature：PASS

- import_whitelist：PASS

- forbidden_calls：PASS

- forbidden_features：PASS

- source_hash_recorded：PASS


## 2. 功能正确性


- smoke_passed：FAIL

- no_exception：FAIL

- deterministic：PASS


## 3. 指标表现

| 指标 | 实测值 | 方向 | 门槛 | 插件 | 判定 |
|---|---|---|---|---|---|

| auc | 0.7206 | maximize | 0.78 | sklearn_metrics | FAIL |

| ks | 0.3928 | maximize | 0.35 | credit_metrics | PASS |

| pr_auc | 0.5055 | maximize | 0.5 | sklearn_metrics | PASS |

| f1 | 0.3468 | maximize | 0.45 | sklearn_metrics | FAIL |

| cost_weighted_loss | 0.8027 | minimize | — | credit_metrics | PASS |

| psi | 0.0205 | minimize | 0.25 | credit_metrics | PASS |

| grouped_auc_gap | 0.0586 | minimize | 0.1 | fairness_metrics | PASS |


## 4. 运行稳定性


- duration_seconds：2.469

- peak_memory_mb：4.08

- memory_limit_applied：True

- timed_out：False

- memory_exceeded：False

- repeat_variance：None


## 5. 说明

smoke_passed; no_exception; auc; f1