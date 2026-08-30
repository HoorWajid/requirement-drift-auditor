"""
Deterministic, template-based assistant over structured audit results.
No external LLM call — zero prompt-injection surface, zero external
dependency/cost, fully offline-capable. This is the DEFAULT engine,
chosen deliberately for security — see app/llm_chatbot.py for the
optional local-LLM alternative and CHATBOT_ENGINE in app/main.py for
how the two are switched.

If a question doesn't match a known intent, the bot says so explicitly and
offers the escalation path (email / contact) instead of guessing.
"""
import re

SUPPORT_EMAIL = "hoorwajid3@gmail.com"  # replace with a real contact for the demo

INTENTS = [
    (re.compile(r"\bhow many.*(requirement|change|drift)", re.I), "count_changed"),
    (re.compile(r"\b(conflict|contradict)", re.I), "list_conflicts"),
    (re.compile(r"\bwhy.*(drift|flag|conflict)", re.I), "explain_severity"),
    (re.compile(r"\b(missing|no test|coverage)", re.I), "coverage_gap"),
]


def answer(question: str, audit_results: list) -> dict:
    """
    audit_results: list of dicts shaped like drift_detector.analyze_pair()'s
    output, plus optional 'req_id' and 'has_test_case' keys set by the caller.
    """
    matched_intent = None
    for pattern, intent in INTENTS:
        if pattern.search(question):
            matched_intent = intent
            break

    if matched_intent == "count_changed":
        changed = [r for r in audit_results if r["severity"] != "STABLE"]
        return _ok(f"{len(changed)} of {len(audit_results)} requirement pairs show drift.")

    if matched_intent == "list_conflicts":
        conflicts = [r for r in audit_results if r["severity"] == "CONFLICT"]
        if not conflicts:
            return _ok("No CONFLICT-level items were detected in this audit.")
        lines = [f"- {r.get('req_id', '?')}: \"{r['req_original'][:60]}...\"" for r in conflicts[:10]]
        return _ok("Conflicting requirements:\n" + "\n".join(lines))

    if matched_intent == "explain_severity":
        return _ok(
            "Severity is computed from semantic similarity between the original and "
            "updated requirement text, cross-checked against a contradiction-detection "
            "model. Higher divergence and detected contradiction both raise severity."
        )

    if matched_intent == "coverage_gap":
        gaps = [r for r in audit_results if r["severity"] != "STABLE" and not r.get("has_test_case", True)]
        if not gaps:
            return _ok("No coverage gaps found among drifted requirements.")
        return _ok(f"{len(gaps)} drifted requirements have no matching test case.")

    # Unmatched intent — be honest, don't hallucinate an answer, offer escalation
    return _fallback()


def _ok(message: str) -> dict:
    return {"answered": True, "message": message, "engine": "rule_based"}


def _fallback() -> dict:
    return {
        "answered": False,
        "engine": "rule_based",
        "message": (
            "I can only answer questions about counts, conflicts, severity reasoning, "
            "and test coverage gaps right now. For anything else, please "
            f"contact {SUPPORT_EMAIL} or use the feedback button below."
        ),
    }
