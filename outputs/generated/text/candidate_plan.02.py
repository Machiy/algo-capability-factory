from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

TEXT_COLUMN = "text"

def build_pipeline(config):
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 1), min_df=2,
            max_features=50000, sublinear_tf=True)),
        ("model", LinearSVC(C=1.0, max_iter=5000, random_state=42,
                            class_weight="balanced")),
    ])
