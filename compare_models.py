"""Prints a clean baseline-vs-iteration comparison table — paste into your Part B report."""
import json
from tabulate import tabulate

with open("models/training_results.json") as f:
    results = json.load(f)

rows = []
for name in ["baseline_logreg", "iteration_mlp"]:
    r = results[name]
    rows.append([name, round(r["val_macro_f1"], 4), r["train_time_sec"]])

print(tabulate(rows, headers=["Model", "Validation Macro-F1", "Train Time (s)"], tablefmt="grid"))
print(f"\nSelected model (highest val F1): {results['selected_model']}")
print("\nFinal TEST-set performance (evaluated once, after selection):")
print(json.dumps(results["test_report"]["macro avg"], indent=2))