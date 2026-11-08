from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline

FEATURE_COLUMNS = ["LIMIT_BAL", "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6", "BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6", "PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6"]

def build_pipeline(config):
    return Pipeline([
        ("model", HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.1, random_state=42)),
    ])
