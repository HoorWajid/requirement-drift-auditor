"""
Baseline: Logistic Regression on frozen MiniLM embeddings.
Iteration: MLP head with class-weighting.
Both are now hyperparameter-tuned via GridSearchCV against the existing
train/val split (a PredefinedSplit — models are fit on train only and
scored on val only, so no k-fold mixing and no leakage into val).
The model type with the best *tuned* val macro-F1 is selected, and only
that model is evaluated on the test set, once.

EMBEDDER_MODEL env var can override with a local folder path if
huggingface.co is rate-limited (see README troubleshooting section).
"""
import os
import json
import time
import numpy as np
import pandas as pd
import joblib
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import GridSearchCV, PredefinedSplit
from sklearn.metrics import classification_report, confusion_matrix

EMBEDDER_NAME = os.getenv("EMBEDDER_MODEL", "all-MiniLM-L6-v2")


def embed_pairs(embedder, df):
    a = embedder.encode(df["req_original"].tolist(), show_progress_bar=False)
    b = embedder.encode(df["req_updated"].tolist(), show_progress_bar=False)
    cos_sim = np.sum(a * b, axis=1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-8)
    return np.concatenate([a, b, np.abs(a - b), cos_sim.reshape(-1, 1)], axis=1)


def predefined_train_val_split(n_train, n_val):
    """-1 = always train, 0 = the single validation fold GridSearchCV scores on."""
    test_fold = np.concatenate([np.full(n_train, -1), np.full(n_val, 0)])
    return PredefinedSplit(test_fold)


def tune(estimator, param_grid, Xtr, ytr, Xval, yval):
    """Grid-search hyperparameters using train-fit/val-score only (no k-fold),
    then refit the winning config on train alone so val stays held out for reporting."""
    X_combined = np.concatenate([Xtr, Xval])
    y_combined = np.concatenate([ytr, yval])
    ps = predefined_train_val_split(len(Xtr), len(Xval))

    t0 = time.time()
    search = GridSearchCV(
        estimator, param_grid, cv=ps, scoring="f1_macro", n_jobs=-1, refit=False
    )
    search.fit(X_combined, y_combined)
    tuning_time = round(time.time() - t0, 2)

    best_model = estimator.set_params(**search.best_params_)
    t0 = time.time()
    best_model.fit(Xtr, ytr)
    fit_time = round(time.time() - t0, 2)

    val_report = classification_report(yval, best_model.predict(Xval), output_dict=True)
    return {
        "model": best_model,
        "best_params": search.best_params_,
        "cv_best_val_f1": round(search.best_score_, 4),
        "val_macro_f1": val_report["macro avg"]["f1-score"],
        "tuning_time_sec": tuning_time,
        "train_time_sec": fit_time,
        "n_param_combos_tried": len(search.cv_results_["params"]),
    }


def main():
    train = pd.read_csv("data/train.csv")
    val = pd.read_csv("data/val.csv")
    test = pd.read_csv("data/test.csv")
    embedder = SentenceTransformer(EMBEDDER_NAME)

    Xtr, ytr = embed_pairs(embedder, train), train["label"].values
    Xval, yval = embed_pairs(embedder, val), val["label"].values
    Xtest, ytest = embed_pairs(embedder, test), test["label"].values

    results = {}

    # ---- Baseline: Logistic Regression, tuned over regularization strength ----
    logreg_grid = {
        "C": [0.01, 0.1, 1, 10, 30],
        "class_weight": ["balanced"],
        "max_iter": [2000],
    }
    logreg_result = tune(LogisticRegression(), logreg_grid, Xtr, ytr, Xval, yval)
    results["baseline_logreg"] = {
        "val_macro_f1": logreg_result["val_macro_f1"],
        "cv_best_val_f1": logreg_result["cv_best_val_f1"],
        "train_time_sec": logreg_result["train_time_sec"],
        "tuning_time_sec": logreg_result["tuning_time_sec"],
        "n_param_combos_tried": logreg_result["n_param_combos_tried"],
        "hyperparams": logreg_result["best_params"],
    }

    # ---- Iteration: MLP, tuned over capacity / regularization / learning rate ----
    mlp_grid = {
        "hidden_layer_sizes": [(64,), (128, 32), (128, 64, 32)],
        "alpha": [1e-5, 1e-4, 1e-3],
        "learning_rate_init": [1e-3, 5e-4],
        "activation": ["relu"],
        "max_iter": [300],
        "early_stopping": [True],
        "n_iter_no_change": [15],
        "random_state": [42],
    }
    mlp_result = tune(MLPClassifier(), mlp_grid, Xtr, ytr, Xval, yval)
    results["iteration_mlp"] = {
        "val_macro_f1": mlp_result["val_macro_f1"],
        "cv_best_val_f1": mlp_result["cv_best_val_f1"],
        "train_time_sec": mlp_result["train_time_sec"],
        "tuning_time_sec": mlp_result["tuning_time_sec"],
        "n_param_combos_tried": mlp_result["n_param_combos_tried"],
        "n_iter_actual": mlp_result["model"].n_iter_,
        "hyperparams": {k: v for k, v in mlp_result["best_params"].items()
                         if k not in ("max_iter", "early_stopping", "n_iter_no_change", "random_state")},
    }

    # ---- Select the model type with the best tuned val macro-F1 ----
    candidates = {"baseline_logreg": logreg_result["model"], "iteration_mlp": mlp_result["model"]}
    best_name = max(results, key=lambda k: results[k]["val_macro_f1"])
    best_model = candidates[best_name]

    # ---- Evaluate the selected model on test, once ----
    test_pred = best_model.predict(Xtest)
    results["selected_model"] = best_name
    results["test_report"] = classification_report(ytest, test_pred, output_dict=True)
    results["test_confusion_matrix"] = confusion_matrix(ytest, test_pred).tolist()

    os.makedirs("models", exist_ok=True)
    joblib.dump(best_model, "models/severity_classifier.joblib")
    with open("models/training_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))
    print(f"\nSelected model (best tuned val macro-F1): {best_name} "
          f"— saved to models/severity_classifier.joblib")


if __name__ == "__main__":
    main()