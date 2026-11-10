import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler, FunctionTransformer
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier

FEATURE_COLUMNS = [
    "LIMIT_BAL",
    "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6",
    "BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6",
    "PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6",
]

PAY_COLUMNS = ["PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6"]
NUMERIC_COLUMNS = [
    "LIMIT_BAL",
    "BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6",
    "PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6",
]

_VALID_PAY_VALUES = {-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9}


def _category_mapper(values):
    arr = np.asarray(values)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    out = np.empty(arr.shape, dtype=object)
    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            v = arr[i, j]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                out[i, j] = np.nan
                continue
            try:
                iv = int(float(v))
            except (TypeError, ValueError):
                out[i, j] = "MISSING"
                continue
            if iv in _VALID_PAY_VALUES:
                out[i, j] = str(iv)
            else:
                out[i, j] = "OTHER"
    return out


def build_pipeline(config):
    config = config or {}
    random_state = int(config.get("random_state", 42))

    def make_pay_transformer():
        return Pipeline(steps=[
            ("category_mapper", FunctionTransformer(_category_mapper, validate=False)),
            ("imputer", SimpleImputer(strategy="constant", fill_value="MISSING")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False, categories="auto")),
        ])

    numeric_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, NUMERIC_COLUMNS),
            ("pay", make_pay_transformer(), PAY_COLUMNS),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )

    classifier = RandomForestClassifier(
        n_estimators=int(config.get("n_estimators", 300)),
        max_depth=int(config.get("max_depth", 10)) if config.get("max_depth", 10) is not None else None,
        random_state=random_state,
        n_jobs=-1,
    )

    return Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", classifier),
    ])