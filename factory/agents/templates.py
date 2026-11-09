"""算法模板插件：按 ``model_family`` 注册可渲染的代码模板。

与 ``factory/validation/metrics`` 采用同一模式（装饰器 + 注册表 + 可列举），
让「插件式接入算法模板或评估指标」两件事用一致的方式表达；渲染用标准库
``str.format``，不引入模板引擎。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

TemplateFn = Callable[[list[str], dict[str, Any]], str]
_REGISTRY: dict[str, TemplateFn] = {}


def register(model_family: str) -> Callable[[TemplateFn], TemplateFn]:
    """注册一个算法模板；重复注册会覆盖并记日志。"""
    def decorator(function: TemplateFn) -> TemplateFn:
        if model_family in _REGISTRY:
            logger.warning("算法模板被覆盖：%s", model_family)
        _REGISTRY[model_family] = function
        return function
    return decorator


def render(model_family: str, columns: list[str], hyperparams: dict[str, Any],
           task_type: str = "") -> str:
    """按模型族渲染源码。

    先按 ``<task_type>.<model_family>`` 查找任务专属模板（如文本分类的
    TF-IDF 管线），再退回通用表格模板；两者都没有时回退
    ``logistic_regression`` 并记 warning，绝不静默产出不匹配的代码。
    """
    keys = [f"{task_type}.{model_family}", model_family] if task_type else [model_family]
    for key in keys:
        function = _REGISTRY.get(key)
        if function is not None:
            return function(columns, hyperparams)
    logger.warning("未注册算法模板 %s，回退 logistic_regression", model_family)
    return _REGISTRY["logistic_regression"](columns, hyperparams)


def list_templates() -> list[str]:
    """返回已注册模板名，供报告说明插件式接入能力。"""
    return sorted(_REGISTRY)


LOGISTIC_REGRESSION_TEMPLATE = '''\
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = {columns}

def build_pipeline(config):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(C={c_value}, max_iter={max_iter}, random_state=42)),
    ])
'''


@register("logistic_regression")
def _logistic_regression(columns: list[str], hyperparams: dict[str, Any]) -> str:
    return LOGISTIC_REGRESSION_TEMPLATE.format(
        columns=json.dumps(columns, ensure_ascii=False),
        c_value=hyperparams.get("C", 1.0),
        max_iter=hyperparams.get("max_iter", 1000),
    )


GRADIENT_BOOSTING_TEMPLATE = '''\
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

FEATURE_COLUMNS = {columns}

def build_pipeline(config):
    return Pipeline([
        ("model", HistGradientBoostingClassifier(
            max_iter={max_iter}, learning_rate={learning_rate}, random_state=42)),
    ])
'''


@register("hist_gradient_boosting")
def _hist_gradient_boosting(columns: list[str], hyperparams: dict[str, Any]) -> str:
    return GRADIENT_BOOSTING_TEMPLATE.format(
        columns=json.dumps(columns, ensure_ascii=False),
        max_iter=hyperparams.get("max_iter", 200),
        learning_rate=hyperparams.get("learning_rate", 0.1),
    )


RANDOM_FOREST_TEMPLATE = '''\
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

FEATURE_COLUMNS = {columns}

def build_pipeline(config):
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestClassifier(
            n_estimators={n_estimators}, max_depth={max_depth},
            random_state=42, n_jobs=1)),
    ])
'''


@register("random_forest")
def _random_forest(columns: list[str], hyperparams: dict[str, Any]) -> str:
    return RANDOM_FOREST_TEMPLATE.format(
        columns=json.dumps(columns, ensure_ascii=False),
        n_estimators=hyperparams.get("n_estimators", 200),
        max_depth=hyperparams.get("max_depth", 8),
    )


TEXT_LOGISTIC_TEMPLATE = '''\
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

TEXT_COLUMN = {text_column}

def build_pipeline(config):
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, {ngram_max}), min_df={min_df},
            max_features={max_features}, sublinear_tf=True)),
        ("model", LogisticRegression(C={c_value}, max_iter=1000, random_state=42,
                                     class_weight="balanced")),
    ])
'''


@register("text_classification.logistic_regression")
def _text_logistic(columns: list[str], hyperparams: dict[str, Any]) -> str:
    return TEXT_LOGISTIC_TEMPLATE.format(
        text_column=json.dumps(hyperparams.get("text_column", "text")),
        ngram_max=hyperparams.get("ngram_max", 2),
        min_df=hyperparams.get("min_df", 2),
        max_features=hyperparams.get("max_features", 50000),
        c_value=hyperparams.get("C", 1.0),
    )


TEXT_SVM_TEMPLATE = '''\
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

TEXT_COLUMN = {text_column}

def build_pipeline(config):
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, {ngram_max}), min_df={min_df},
            max_features={max_features}, sublinear_tf=True)),
        ("model", LinearSVC(C={c_value}, max_iter=5000, random_state=42,
                            class_weight="balanced")),
    ])
'''


@register("text_classification.linear_svc")
def _text_svm(columns: list[str], hyperparams: dict[str, Any]) -> str:
    return TEXT_SVM_TEMPLATE.format(
        text_column=json.dumps(hyperparams.get("text_column", "text")),
        ngram_max=hyperparams.get("ngram_max", 1),
        min_df=hyperparams.get("min_df", 2),
        max_features=hyperparams.get("max_features", 50000),
        c_value=hyperparams.get("C", 1.0),
    )


TEXT_NB_TEMPLATE = '''\
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline

TEXT_COLUMN = {text_column}

def build_pipeline(config):
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, {ngram_max}), min_df={min_df},
            max_features={max_features}, sublinear_tf=True)),
        ("model", ComplementNB(alpha={alpha})),
    ])
'''


@register("text_classification.complement_nb")
def _text_nb(columns: list[str], hyperparams: dict[str, Any]) -> str:
    return TEXT_NB_TEMPLATE.format(
        text_column=json.dumps(hyperparams.get("text_column", "text")),
        ngram_max=hyperparams.get("ngram_max", 1),
        min_df=hyperparams.get("min_df", 2),
        max_features=hyperparams.get("max_features", 50000),
        alpha=hyperparams.get("alpha", 1.0),
    )


__all__ = [
    "GRADIENT_BOOSTING_TEMPLATE",
    "LOGISTIC_REGRESSION_TEMPLATE",
    "RANDOM_FOREST_TEMPLATE",
    "TEXT_LOGISTIC_TEMPLATE",
    "TEXT_NB_TEMPLATE",
    "TEXT_SVM_TEMPLATE",
    "list_templates",
    "register",
    "render",
]
