from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline

TEXT_COLUMN = "text"

def build_pipeline(config):
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 1), min_df=2,
            max_features=50000, sublinear_tf=True)),
        ("model", ComplementNB(alpha=0.5)),
    ])
