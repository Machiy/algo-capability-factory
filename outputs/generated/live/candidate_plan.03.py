from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, FunctionTransformer
from sklearn.ensemble import HistGradientBoostingClassifier

FEATURE_COLUMNS = ["LIMIT_BAL", "PAY_0", "PAY_2", "PAY_3", "PAY_4", "PAY_5", "PAY_6", "BILL_AMT1", "BILL_AMT2", "BILL_AMT3", "BILL_AMT4", "BILL_AMT5", "BILL_AMT6", "PAY_AMT1", "PAY_AMT2", "PAY_AMT3", "PAY_AMT4", "PAY_AMT5", "PAY_AMT6"]

def build_pipeline(config):
    max_iter = config.get('max_iter', 200) if config else 200
    learning_rate = config.get('learning_rate', 0.1) if config else 0.1

    numeric_features = FEATURE_COLUMNS
    categorical_features = []  # sensitive fields excluded; no categorical features remain

    numeric_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    categorical_transformer = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('onehot', OneHotEncoder(handle_unknown='ignore'))
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', numeric_transformer, numeric_features),
            ('cat', categorical_transformer, categorical_features)
        ],
        remainder='drop'
    )

    category_mapper = FunctionTransformer(lambda X: X)

    pipeline = Pipeline(steps=[
        ('category_mapper', category_mapper),
        ('preprocessor', preprocessor),
        ('classifier', HistGradientBoostingClassifier(
            max_iter=max_iter,
            learning_rate=learning_rate,
            early_stopping=False,
            random_state=42
        ))
    ])

    return pipeline