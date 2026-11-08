"""历史评分卡脚本（legacy，模拟的历史代码仓库资产）。

本文件**故意保留已知缺陷**，用于两个目的：
1. 供 RepoExtractor 演示「从真实/历史代码中抽取函数、依赖与能力描述」；
2. 作为验证器的反例，触发 KeyError / SchemaError / LeakageDetected 等错误签名，
   从而产生可复现的「失败 → 诊断 → 修复 → 沉淀」轨迹。

请勿在生产环境使用，也不要作为算法实现的参考。
"""

from __future__ import annotations

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

DATA_PATH = "assets/data/UCI_Credit_Card.csv"
TARGET = "default.payment.next.month"

# 缺陷 1：数据集中最近一期的列名是 PAY_0，并不存在 PAY_1
PAY_COLUMNS = ["PAY_1", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]


def load_raw(path: str = DATA_PATH) -> pd.DataFrame:
    """读取原始客户账单数据。"""
    return pd.read_csv(path)


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """构造历史评分卡特征。

    缺陷 2：未剔除 ID 标识列。
    缺陷 3：未处理 EDUCATION / MARRIAGE 的未文档化类别。
    """
    features = df.drop(columns=[TARGET]).copy()
    features["delay_count"] = (features[PAY_COLUMNS] > 0).sum(axis=1)
    return features, df[TARGET]


def train_default_model(df: pd.DataFrame) -> dict:
    """训练历史逻辑回归评分卡，返回结果字典。

    缺陷 4：在全量数据上 fit 标准化器，统计量泄漏到验证集。
    缺陷 5：使用随机划分，对「下月违约」标签引入未来信息。
    缺陷 6：以 accuracy 作为验收指标，正例仅 22.12% 时结论失真。
    """
    features, target = build_features(df)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    x_train, x_test, y_train, y_test = train_test_split(
        scaled, target, test_size=0.2, random_state=42
    )
    model = LogisticRegression(max_iter=1000)
    model.fit(x_train, y_train)
    prediction = model.predict(x_test)
    return {"accuracy": accuracy_score(y_test, prediction), "model": model}


def score_to_rating(probability: float) -> str:
    """把违约概率映射为内部评级（历史规则）。"""
    if probability < 0.1:
        return "A"
    if probability < 0.3:
        return "B"
    if probability < 0.5:
        return "C"
    return "D"
