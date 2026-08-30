"""
Tests the Ollama chatbot engine's fallback behavior. Does NOT require Ollama
to actually be running or a model to be pulled — that's the point: this
locks in the fallback-to-rule_based contract deterministically, using a
monkeypatched URL that's guaranteed to fail, rather than depending on the
real local Ollama service being up (which would make CI flaky and would
make this test's pass/fail depend on machine state, not code correctness).
"""
import pytest
import app.llm_chatbot as llm_chatbot


@pytest.mark.unit
def test_falls_back_to_rule_based_when_ollama_unreachable(monkeypatch):
    # Point at a port nothing is listening on -> guaranteed connection failure,
    # every time, on every machine, regardless of whether Ollama is installed.
    monkeypatch.setattr(llm_chatbot, "OLLAMA_URL", "http://localhost:1/api/generate")

    result = llm_chatbot.answer(
        "How many requirements changed?",
        [{"severity": "CONFLICT", "nli_label": "contradiction", "cosine_similarity": 0.4}],
    )

    assert result["engine"] == "rule_based_fallback"
    assert result["answered"] is True
    # The fallback must produce the SAME correct answer the rule-based
    # engine would give directly — not a generic error message.
    assert "1 of 1" in result["message"]


@pytest.mark.unit
def test_fallback_never_raises_on_malformed_ollama_response(monkeypatch):
    """
    Simulates Ollama responding successfully (HTTP 200) but with an empty or
    malformed body — a different failure mode than being unreachable. The
    fallback must trigger here too, not just on network errors.
    """
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {}  # missing "response" key entirely

    def fake_post(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setattr(llm_chatbot.requests, "post", fake_post)

    result = llm_chatbot.answer("How many requirements changed?", [])

    assert result["engine"] == "rule_based_fallback"
    assert result["answered"] is True
    assert "0 of 0" in result["message"]