from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

TEXT_COLUMN = "text"

def build_pipeline(config):
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2), min_df=2,
            max_features=50000, sublinear_tf=True)),
        ("model", LogisticRegression(C=0.5, max_iter=1000, random_state=42,
                                     class_weight="balanced")),
    ])
