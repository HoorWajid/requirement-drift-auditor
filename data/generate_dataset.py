"""
Generates labeled requirement pairs for the Drift Severity Classifier.
Labels: 0=STABLE, 1=LOW_DRIFT, 2=MEDIUM_DRIFT, 3=CONFLICT
Synthetic, disclosed as such — no public requirement-drift corpus exists.
"""
import random
import pandas as pd
from sklearn.model_selection import train_test_split

random.seed(42)

TEMPLATES = [
    ("The system must respond within {a} seconds.",
     "The system must respond within {b} seconds.", "numeric"),
    ("Users must upload files up to {a} MB.",
     "Users can upload files up to {b} MB.", "numeric"),
    ("The application must support {a} concurrent users.",
     "The application must support {b} concurrent users.", "numeric"),
    ("The system must log all access attempts.",
     "The system must not log any access attempts.", "negation"),
    ("Passwords must be at least {a} characters.",
     "Passwords must be at least {b} characters.", "numeric"),
]

def label_numeric(a, b):
    diff_ratio = abs(a - b) / max(a, b)
    if diff_ratio < 0.05: return 0
    elif diff_ratio < 0.25: return 1
    elif diff_ratio < 0.6: return 2
    else: return 3

rows = []
for _ in range(4000):
    tpl_a, tpl_b, kind = random.choice(TEMPLATES)
    if kind == "numeric":
        base = random.randint(1, 100)
        delta_pct = random.choice([0.0, 0.05, 0.2, 0.5, 1.5])
        b_val = max(1, round(base * (1 + random.choice([-1, 1]) * delta_pct)))
        rows.append({"req_original": tpl_a.format(a=base), "req_updated": tpl_b.format(b=b_val),
                     "label": label_numeric(base, b_val)})
    else:
        rows.append({"req_original": tpl_a, "req_updated": tpl_b, "label": 3})

df = pd.DataFrame(rows).drop_duplicates()
train, temp = train_test_split(df, test_size=0.3, stratify=df["label"], random_state=42)
val, test = train_test_split(temp, test_size=0.5, stratify=temp["label"], random_state=42)

train.to_csv("data/train.csv", index=False)
val.to_csv("data/val.csv", index=False)
test.to_csv("data/test.csv", index=False)
print(f"train={len(train)} val={len(val)} test={len(test)}")
print(df["label"].value_counts())