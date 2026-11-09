# 真实开源仓库来源说明

本目录固定了一份**真实开源仓库源码**，用于 `factory/knowledge/repo_extractor.py`
的 AST 抽取（题目加分项「支持从真实代码仓库中抽取函数、依赖和能力描述」）。

| 项 | 内容 |
|---|---|
| 仓库 | `scorecardpy`（信用评分卡工具库，与主场景同领域） |
| 版本 | `0.1.9.7` |
| 上游 | PyPI sdist：`scorecardpy-0.1.9.7.tar.gz` |
| 许可 | MIT（见 `scorecardpy/LICENSE`，Copyright (c) 2018 Shichen Xie） |
| 获取方式 | `pip download scorecardpy==0.1.9.7 --no-deps --no-binary :all:` |
| sdist SHA-256 | `a81c7e6f3bf5f10a87b61af73b25f1fc8bc5acbadf5d9e38c3addb02df128d03` |

## 保留了哪些文件

- `scorecardpy/*.py`：13 个模块源码，共 81 个函数（含嵌套函数）
- `LICENSE`、`README.md`、`NEWS.md`、`setup.py`：许可与依赖声明

**未保留**：`scorecardpy/data/germancredit.csv`（约 200KB 数据）、`egg-info/`、
打包配置中与抽取无关的部分。未保留项不影响函数 / 依赖 / 能力描述的抽取。

## 为什么入库而不是运行时克隆

评审环境需要「断网可复现」。若运行时 `git clone` 或联网下载，抽取流程
在无网络环境下直接失败，等于把加分项做成不可复现的演示。固定入库后，
`python scripts/extract_repo.py` 在离线环境中可重复产出同一份能力图谱。

## 安全边界

抽取器只做 `ast.parse` 文本分析，**不 import、不执行**被抽取仓库的任何代码，
因此不存在供应链执行风险。测试 `tests/test_repo_extractor.py` 同样只读文件。
