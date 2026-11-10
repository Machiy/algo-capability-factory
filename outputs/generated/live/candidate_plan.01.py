from typing import Any, Dict, Optional

import pandas as pd

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


FEATURE_COLUMNS = [
    "LIMIT_BAL",
    "PAY_0",
    "PAY_2",
    "PAY_3",
    "PAY_4",
    "PAY_5",
    "PAY_6",
    "BILL_AMT1",
    "BILL_AMT2",
    "BILL_AMT3",
    "BILL_AMT4",
    "BILL_AMT5",
    "BILL_AMT6",
    "PAY_AMT1",
    "PAY_AMT2",
    "PAY_AMT3",
    "PAY_AMT4",
    "PAY_AMT5",
    "PAY_AMT6",
]

CATEGORICAL_COLUMNS = []

SENSITIVE_OR_ID_COLUMNS = [
    "ID",
    "SEX",
    "AGE",
    "EDUCATION",
    "MARRIAGE",
    "default.payment.next.month",
    "default",
    "target",
    "label",
    "y",
]


class CategoryMapper(BaseEstimator, TransformerMixin):
    def __init__(self, mappings=None):
        self.mappings = mappings

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        if not isinstance(X, pd.DataFrame):
            return X
        mappings = self.mappings or {}
        X = X.copy()
        for col, values in mappings.items():
            if col in X.columns:
                X[col] = X[col].where(~X[col].isin(values), "other")
        return X


class ColumnDropper(BaseEstimator, TransformerMixin):
    def __init__(self, columns_to_drop=None):
        self.columns_to_drop = columns_to_drop

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        if not isinstance(X, pd.DataFrame):
            return X
        cols = self.columns_to_drop or []
        cols = [c for c in cols if c in X.columns]
        if not cols:
            return X
        return X.drop(columns=cols)


def _get_param(config, name, default):
    if isinstance(config, dict):
        if name in config:
            return config[name]
        hyperparams = config.get("hyperparams", {})
        if isinstance(hyperparams, dict) and name in hyperparams:
            return hyperparams[name]
    return default


def build_pipeline(config):
    C = float(_get_param(config, "C", 0.5))
    max_iter = int(_get_param(config, "max_iter", 1000))

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    transformers = [("num", numeric_pipeline, FEATURE_COLUMNS)]
    if CATEGORICAL_COLUMNS:
        transformers.append(("cat", categorical_pipeline, CATEGORICAL_COLUMNS))

    preprocessor = ColumnTransformer(
        transformers=transformers,
        remainder="drop",
    )

    model = LogisticRegression(
        C=C,
        max_iter=max_iter,
        solver="lbfgs",
    )

    pipeline = Pipeline(
        steps=[
            (
                "category_map",
                CategoryMapper(
                    mappings={
                        "EDUCATION": [0, 5, 6],
                        "MARRIAGE": [0],
                    }
                ),
            ),
            ("column_drop", ColumnDropper(columns_to_drop=SENSITIVE_OR_ID_COLUMNS)),
            ("preprocess", preprocessor),
            ("classifier", model),
        ]
    )

    return pipeline