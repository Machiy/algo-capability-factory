# 项目说明 · AlgoCap Factory

基于 AI Agent 的算法能力工厂原型，主场景为信用卡客户下月违约预测，目标是跑通
「能力抽取 → 能力复刻 → 能力验证 → 能力沉淀」闭环。对应 LLM Agent 笔试题目。

## 常用命令

- `python scripts/download_data.py`：下载并校验数据集（仅用标准库；已有缓存时加 `--offline`）
- `python scripts/download_data.py --verify`：只校验现有 CSV，不联网
- `python -m unittest discover -s tests -v`：数据契约测试，无需安装第三方依赖
- `python -m factory --version`：包入口自检
- `pip install -r requirements.txt`：安装 P1 起所需依赖

## 架构约定

- 采用扁平包布局 `factory/`，不要改回 `src/factory/`（README 的运行命令依赖此结构）
- 所有模块只通过 `factory/contracts/` 中的契约数据类交互，契约先行
- LLM 经 `BaseLLM` 抽象接入，`MockLLM` 为默认路径，保证断网可复现
- 验证逻辑与场景解耦：换任务只改 `configs/verify_*.yaml`，不改核心代码
- 预处理必须置于 `sklearn.Pipeline` 内且仅在训练集 fit；标签是「下月违约」，禁止随机划分

## 数据与合规

- 数据集：UCI Default of Credit Card Clients（CC BY 4.0）/ OpenML d/43435（CC0 Public Domain）
- 敏感字段 `SEX`、`AGE`、`EDUCATION`、`MARRIAGE` 不入模，仅用于公平性审计
- `ID` 禁止作为特征
- 已知数据陷阱 T1–T4 见 `assets/docs/data_dictionary.md`，不要按列名直觉推断

## 仓库约定

- `PLAN.md`、`assets/data/raw/`、`_archive/` 为本地内容，不纳入版本控制
- 不要把 token、`.env` 或任何凭据写入仓库文件或 remote URL
- 提交信息使用 Conventional Commits，每个实现阶段一个独立提交
