"""Embedding similarity + NLI contradiction + trained severity classifier."""
import os
import numpy as np
import joblib
from functools import lru_cache
from sentence_transformers import SentenceTransformer, CrossEncoder

EMBEDDER_NAME = os.getenv("EMBEDDER_MODEL", "all-MiniLM-L6-v2")
NLI_MODEL_NAME = os.getenv("NLI_MODEL", "cross-encoder/nli-distilroberta-base")
CLASSIFIER_PATH = "models/severity_classifier.joblib"
SEVERITY_LABELS = {0: "STABLE", 1: "LOW_DRIFT", 2: "MEDIUM_DRIFT", 3: "CONFLICT"}

@lru_cache(maxsize=1)
def get_embedder():
    return SentenceTransformer(EMBEDDER_NAME)

@lru_cache(maxsize=1)
def get_nli_model():
    return CrossEncoder(NLI_MODEL_NAME)

@lru_cache(maxsize=1)
def get_severity_classifier():
    return joblib.load(CLASSIFIER_PATH)

def _feature_vector(embedder, req_a, req_b):
    a = embedder.encode([req_a])[0]
    b = embedder.encode([req_b])[0]
    cos_sim = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
    feats = np.concatenate([a, b, np.abs(a - b), [cos_sim]]).reshape(1, -1)
    return feats, cos_sim

def analyze_pair(req_a: str, req_b: str) -> dict:
    embedder = get_embedder()
    nli = get_nli_model()
    clf = get_severity_classifier()
    feats, cos_sim = _feature_vector(embedder, req_a, req_b)
    nli_scores = nli.predict([(req_a, req_b)])[0]
    nli_label = ["contradiction", "entailment", "neutral"][int(np.argmax(nli_scores))]
    severity_idx = int(clf.predict(feats)[0])
    severity_label = SEVERITY_LABELS[severity_idx]
    flagged_disagreement = (nli_label == "contradiction" and severity_label == "STABLE")
    return {
        "req_original": req_a, "req_updated": req_b,
        "cosine_similarity": round(cos_sim, 4), "nli_label": nli_label,
        "nli_scores": {"contradiction": round(float(nli_scores[0]), 4),
                       "entailment": round(float(nli_scores[1]), 4),
                       "neutral": round(float(nli_scores[2]), 4)},
        "severity": severity_label, "model_disagreement_flag": flagged_disagreement,
    }