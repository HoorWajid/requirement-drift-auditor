"""
Baseline: Logistic Regression on frozen MiniLM embeddings.
Iteration: MLP head with class-weighting.
EMBEDDER_MODEL env var can override with a local folder path if
huggingface.co is rate-limited (see README troubleshooting section).
"""
import os
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib, json, time

EMBEDDER_NAME = os.getenv("EMBEDDER_MODEL", "all-MiniLM-L6-v2")

def embed_pairs(embedder, df):
    a = embedder.encode(df["req_original"].tolist(), show_progress_bar=False)
    b = embedder.encode(df["req_updated"].tolist(), show_progress_bar=False)
    cos_sim = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-8)
    return np.concatenate([a, b, np.abs(a - b), cos_sim.reshape(-1, 1)], axis=1)

def main():
    train = pd.read_csv("data/train.csv")
    val = pd.read_csv("data/val.csv")
    test = pd.read_csv("data/test.csv")
    embedder = SentenceTransformer(EMBEDDER_NAME)

    Xtr, ytr = embed_pairs(embedder, train), train["label"].values
    Xval, yval = embed_pairs(embedder, val), val["label"].values
    Xtest, ytest = embed_pairs(embedder, test), test["label"].values

    results = {}

    t0 = time.time()
    baseline = LogisticRegression(max_iter=2000, class_weight="balanced")
    baseline.fit(Xtr, ytr)
    baseline_report = classification_report(yval, baseline.predict(Xval), output_dict=True)
    results["baseline_logreg"] = {
        "val_macro_f1": baseline_report["macro avg"]["f1-score"],
        "train_time_sec": round(time.time() - t0, 2),
        "hyperparams": {"max_iter": 2000, "class_weight": "balanced"}
    }

    t0 = time.time()
    mlp = MLPClassifier(hidden_layer_sizes=(128, 32), activation="relu", alpha=1e-4,
                         learning_rate_init=1e-3, max_iter=300, early_stopping=True,
                         n_iter_no_change=15, random_state=42)
    mlp.fit(Xtr, ytr)
    mlp_report = classification_report(yval, mlp.predict(Xval), output_dict=True)
    results["iteration_mlp"] = {
        "val_macro_f1": mlp_report["macro avg"]["f1-score"],
        "train_time_sec": round(time.time() - t0, 2),
        "n_iter_actual": mlp.n_iter_,
        "hyperparams": {"hidden_layer_sizes": [128, 32], "alpha": 1e-4, "learning_rate_init": 1e-3}
    }

    best_name = max(results, key=lambda k: results[k]["val_macro_f1"])
    best_model = baseline if best_name == "baseline_logreg" else mlp
    test_pred = best_model.predict(Xtest)
    results["selected_model"] = best_name
    results["test_report"] = classification_report(ytest, test_pred, output_dict=True)
    results["test_confusion_matrix"] = confusion_matrix(ytest, test_pred).tolist()

    joblib.dump(best_model, "models/severity_classifier.joblib")
    with open("models/training_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
    print(f"\nSelected model: {best_name} — saved to models/severity_classifier.joblib")

if __name__ == "__main__":
    main()