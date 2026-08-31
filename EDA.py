"""
EDA for the Drift Severity Classifier dataset (+ model comparison, if
models/training_results.json already exists from train_model.py).

Run after generate_dataset.py, optionally after train_model.py too.
All figures are saved to results/ (created if missing). Console output
is a short, to-the-point insight summary — not a data dump.

Each insight uses a different chart type on purpose (no chart type
repeated), matched to what it's best suited to show:
  - donut chart    -> label distribution (part-of-whole)
  - grouped bar     -> split balance (compare categories across groups)
  - violin plot     -> jaccard similarity by label (full distribution shape)
  - KDE density     -> length-delta distribution by label (overlaid curves)
  - scatter plot    -> jaccard vs. length-delta relationship
  - lollipop chart  -> model comparison (few categories, exact values matter)
  - radar chart     -> per-class test F1 (multi-axis profile of one model)
"""
import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr, gaussian_kde

RESULTS_DIR = "results"
LABEL_NAMES = {0: "STABLE", 1: "LOW_DRIFT", 2: "MEDIUM_DRIFT", 3: "CONFLICT"}
LABEL_COLORS = {0: "#16A34A", 1: "#2563EB", 2: "#C2760C", 3: "#DC2647"}


def load_data():
    train = pd.read_csv("data/train.csv")
    val = pd.read_csv("data/val.csv")
    test = pd.read_csv("data/test.csv")
    for name, df in [("train", train), ("val", val), ("test", test)]:
        df["split"] = name
    return pd.concat([train, val, test], ignore_index=True)


def add_text_features(df):
    df = df.copy()
    df["label_name"] = df["label"].map(LABEL_NAMES)
    df["orig_word_count"] = df["req_original"].str.split().str.len()
    df["upd_word_count"] = df["req_updated"].str.split().str.len()
    df["word_count_delta"] = (df["upd_word_count"] - df["orig_word_count"]).abs()
    df["char_len_delta"] = (df["req_updated"].str.len() - df["req_original"].str.len()).abs()

    def jaccard(a, b):
        wa, wb = set(a.lower().split()), set(b.lower().split())
        if not wa and not wb:
            return 1.0
        return len(wa & wb) / len(wa | wb)

    df["jaccard_sim"] = df.apply(lambda r: jaccard(r["req_original"], r["req_updated"]), axis=1)
    df["is_exact_duplicate_pair"] = df["req_original"].str.strip() == df["req_updated"].str.strip()
    return df


# ---------- 1. Donut chart: label distribution ----------
def plot_label_distribution(df):
    counts = df["label_name"].value_counts().reindex(LABEL_NAMES.values())
    colors = [LABEL_COLORS[k] for k in sorted(LABEL_NAMES)]

    fig, ax = plt.subplots(figsize=(6, 6))
    wedges, _, autotexts = ax.pie(
        counts.values, colors=colors, autopct="%1.1f%%", pctdistance=0.8,
        startangle=90, wedgeprops=dict(width=0.4, edgecolor="white")
    )
    ax.legend(wedges, counts.index, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)
    ax.set_title("Label distribution (train+val+test)")
    ax.text(0, 0, f"n={counts.sum()}", ha="center", va="center", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"{RESULTS_DIR}/label_distribution_donut.png", dpi=150)
    plt.close(fig)
    return counts


# ---------- 2. Grouped bar chart: label balance across splits ----------
def plot_split_balance(df):
    ct = pd.crosstab(df["split"], df["label_name"], normalize="index")[list(LABEL_NAMES.values())]
    splits = ct.index.tolist()
    labels = ct.columns.tolist()
    x = np.arange(len(splits))
    width = 0.2

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, lab in enumerate(labels):
        key = [k for k, v in LABEL_NAMES.items() if v == lab][0]
        ax.bar(x + (i - 1.5) * width, ct[lab].values, width, label=lab, color=LABEL_COLORS[key])
    ax.set_xticks(x)
    ax.set_xticklabels(splits)
    ax.set_ylabel("Proportion")
    ax.set_title("Label proportion by split (checks stratified split held)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{RESULTS_DIR}/split_label_balance_grouped_bar.png", dpi=150)
    plt.close(fig)
    return ct


# ---------- 3. Violin plot: jaccard similarity by label ----------
def plot_jaccard_by_label(df):
    order = sorted(LABEL_NAMES)
    data = [df.loc[df["label"] == k, "jaccard_sim"].values for k in order]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    parts = ax.violinplot(data, showmedians=True, showextrema=True)
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor(LABEL_COLORS[order[i]])
        body.set_alpha(0.6)
    ax.set_xticks(range(1, len(order) + 1))
    ax.set_xticklabels([LABEL_NAMES[k] for k in order])
    ax.set_title("Word-overlap (Jaccard) similarity by severity label")
    ax.set_ylabel("Jaccard similarity")
    fig.tight_layout()
    fig.savefig(f"{RESULTS_DIR}/jaccard_by_label_violin.png", dpi=150)
    plt.close(fig)


# ---------- 4. KDE density plot: length-delta distribution by label ----------
def plot_length_delta_density(df):
    order = sorted(LABEL_NAMES)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    x_max = df["char_len_delta"].quantile(0.98)
    xs = np.linspace(0, max(x_max, 1), 200)
    for k in order:
        vals = df.loc[df["label"] == k, "char_len_delta"].values
        if len(vals) < 2 or np.std(vals) == 0:
            continue
        kde = gaussian_kde(vals)
        ax.plot(xs, kde(xs), color=LABEL_COLORS[k], label=LABEL_NAMES[k], linewidth=2)
        ax.fill_between(xs, kde(xs), color=LABEL_COLORS[k], alpha=0.12)
    ax.set_title("Character-length delta density by severity label")
    ax.set_xlabel("|len(updated) - len(original)|")
    ax.set_ylabel("Density")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{RESULTS_DIR}/length_delta_density.png", dpi=150)
    plt.close(fig)


# ---------- 5. Scatter plot: jaccard vs. length-delta relationship ----------
def plot_jaccard_vs_length_scatter(df):
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for k in sorted(LABEL_NAMES):
        sub = df[df["label"] == k]
        ax.scatter(sub["jaccard_sim"], sub["char_len_delta"],
                   color=LABEL_COLORS[k], label=LABEL_NAMES[k], alpha=0.4, s=18)
    ax.set_xlabel("Jaccard similarity")
    ax.set_ylabel("|len(updated) - len(original)|")
    ax.set_title("Word-overlap vs. length change, by label")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(f"{RESULTS_DIR}/jaccard_vs_length_scatter.png", dpi=150)
    plt.close(fig)


# ---------- 6. Lollipop chart: model comparison (val macro-F1) ----------
def plot_model_comparison_lollipop(results):
    model_names = [k for k in results if k not in ("selected_model", "test_report", "test_confusion_matrix")]
    val_f1 = [results[m]["val_macro_f1"] for m in model_names]
    selected = results["selected_model"]
    colors = ["#4F46E5" if m == selected else "#9CA3AF" for m in model_names]
    y = np.arange(len(model_names))

    fig, ax = plt.subplots(figsize=(6.5, 3.5))
    ax.hlines(y=y, xmin=0, xmax=val_f1, color=colors, linewidth=2)
    ax.scatter(val_f1, y, color=colors, s=140, zorder=3)
    for yi, v in zip(y, val_f1):
        ax.text(v + 0.015, yi, f"{v:.3f}", va="center", fontsize=9)
    ax.set_yticks(y)
    ax.set_yticklabels(model_names)
    ax.set_xlim(0, 1)
    ax.set_xlabel("Validation Macro-F1")
    ax.set_title(f"Tuned model comparison — selected: {selected}")
    fig.tight_layout()
    fig.savefig(f"{RESULTS_DIR}/model_comparison_lollipop.png", dpi=150)
    plt.close(fig)


# ---------- 7. Radar chart: per-class test F1 for the selected model ----------
def plot_test_f1_radar(results):
    per_class = results["test_report"]
    class_labels = [k for k in per_class if k in [str(i) for i in LABEL_NAMES]]
    if not class_labels:
        return
    ordered = sorted(class_labels, key=int)
    names = [LABEL_NAMES[int(c)] for c in ordered]
    values = [per_class[c]["f1-score"] for c in ordered]

    angles = np.linspace(0, 2 * np.pi, len(names), endpoint=False).tolist()
    values_closed = values + values[:1]
    angles_closed = angles + angles[:1]

    fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw=dict(polar=True))
    ax.plot(angles_closed, values_closed, color="#4F46E5", linewidth=2)
    ax.fill(angles_closed, values_closed, color="#4F46E5", alpha=0.25)
    ax.set_xticks(angles)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_title(f"Test-set per-class F1 — {results['selected_model']} (evaluated once)", pad=20)
    fig.tight_layout()
    fig.savefig(f"{RESULTS_DIR}/test_per_class_f1_radar.png", dpi=150)
    plt.close(fig)


def run_model_comparison_plots():
    path = "models/training_results.json"
    if not os.path.exists(path):
        print("(models/training_results.json not found yet — skipping model comparison plots. "
              "Run train_model.py first to include them.)")
        return None
    with open(path) as f:
        results = json.load(f)
    plot_model_comparison_lollipop(results)
    plot_test_f1_radar(results)
    return results


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    df = add_text_features(load_data())
    n = len(df)

    counts = plot_label_distribution(df)
    plot_split_balance(df)
    plot_jaccard_by_label(df)
    plot_length_delta_density(df)
    plot_jaccard_vs_length_scatter(df)
    model_results = run_model_comparison_plots()

    # Quick, to-the-point numeric insights
    imbalance_ratio = counts.max() / counts.min()
    corr_jaccard, p_jaccard = spearmanr(df["jaccard_sim"], df["label"])
    corr_lendelta, p_lendelta = spearmanr(df["char_len_delta"], df["label"])
    dup_rate = df["is_exact_duplicate_pair"].mean()

    imbalance_note = ('class_weight="balanced" in training is justified'
                       if imbalance_ratio > 1.5 else 'fairly balanced')
    jaccard_note = ('strong inverse relationship, overlap drops as drift severity rises'
                     if corr_jaccard < -0.3 else 'weak relationship')

    print("=" * 60)
    print(f"EDA SUMMARY  (n={n} pairs across train/val/test)")
    print("=" * 60)
    print(f"- Label distribution: {counts.to_dict()}")
    print(f"  Imbalance ratio (largest/smallest class): {imbalance_ratio:.2f}x ({imbalance_note})")
    print(f"- Jaccard word-overlap vs. label: Spearman r={corr_jaccard:.3f} (p={p_jaccard:.1e}) — {jaccard_note}")
    print(f"- Char-length delta vs. label: Spearman r={corr_lendelta:.3f} (p={p_lendelta:.1e})")
    print(f"- Exact-duplicate original==updated pairs: {dup_rate:.1%} of dataset")
    if model_results:
        sel = model_results["selected_model"]
        print(f"- Selected model: {sel} "
              f"(val macro-F1={model_results[sel]['val_macro_f1']:.4f}, "
              f"hyperparams={model_results[sel]['hyperparams']})")
        print(f"- Test macro-F1 (evaluated once, after selection): "
              f"{model_results['test_report']['macro avg']['f1-score']:.4f}")
    print(f"\nFigures saved to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()