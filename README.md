# Requirement Drift & Consistency Auditor

An AI-powered system that detects semantic drift, contradictions, and test-coverage
gaps between versions of software requirement documents, with a trained severity
classifier, a secured FastAPI backend, a Streamlit frontend, and a pluggable
chatbot (rule-based by default, optional local LLM via Ollama).

## Architecture

```
                        ┌────────────────────┐
                        │   Streamlit UI      │
                        │ login / upload /    │
                        │ dashboard / chat    │
                        └─────────┬───────────┘
                                  │ HTTPS + JWT cookie
                                  ▼
                        ┌────────────────────┐
                        │   FastAPI backend   │
                        │  - auth (JWT)       │
                        │  - rate limiting    │
                        │  - input validation │
                        │  - security headers │
                        └─────────┬───────────┘
                 ┌────────────────┼─────────────────┐
                 ▼                ▼                  ▼
        Document Processor   Embedding + NLI    Drift Severity
        (PyMuPDF/docx,       (MiniLM + distil-  Classifier
         size/type checks)    NLI, frozen)       (TRAINED, versioned)
                 │                │                  │
                 └────────────────┴──────────────────┘
                                  ▼
                          SQLite/Postgres
                     (users, requirements, audit results)
                                  │
                        ┌─────────┴─────────┐
                        ▼                   ▼
                 Rule-based chatbot   Optional: local LLM
                 (default, secure)    (Ollama, opt-in, auto-fallback)
```

## Folder structure

```
requirement-drift-auditor/
├── requirements.txt              # local dev deps (Windows: python-magic-bin)
├── requirements-docker.txt       # container deps (Linux: python-magic)
├── requirements-dev.txt          # test/lint/security tooling
├── pytest.ini
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── train_severity_classifier.py
├── compare_models.py
├── .github/workflows/ci-cd.yml
├── data/generate_dataset.py
├── models/                       # generated: severity_classifier.joblib, training_results.json
├── app/
│   ├── main.py                   # FastAPI app, endpoint wiring
│   ├── database.py                # SQLAlchemy models
│   ├── schemas.py                 # Pydantic input validation
│   ├── security.py                # JWT, hashing, rate limiting, headers
│   ├── document_processor.py      # upload validation
│   ├── drift_detector.py          # embeddings + NLI + trained classifier
│   ├── chatbot.py                 # rule-based engine (default)
│   └── llm_chatbot.py             # optional local-LLM engine (Ollama)
├── frontend/streamlit_app.py
└── tests/
    ├── unit/test_pipeline.py
    ├── security/test_security.py
    └── integration/test_api_integration.py
```

## 1. Setup (VS Code PowerShell terminal, Windows)

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
```
If PowerShell blocks activation: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`, then retry.

Copy `.env.example` to `.env` and set a real `JWT_SECRET_KEY`, then load env vars each session:
```powershell
$env:JWT_SECRET_KEY = "replace_with_a_long_random_value"
$env:DATABASE_URL = "sqlite:///./app.db"
$env:ALLOWED_ORIGINS = "http://localhost:8501"
$env:CHATBOT_ENGINE = "rule_based"
```

## 2. Train the model (produces the comparison your Part B report needs)

```powershell
python data\generate_dataset.py
python train_severity_classifier.py
python compare_models.py
```

## 3. Run the backend + frontend

```powershell
uvicorn app.main:app --reload
```
In a second terminal tab:
```powershell
streamlit run frontend\streamlit_app.py
```

## 4. Testing (standard organizational split — run security first)

```powershell
pytest -m security -v --cov=app --cov-report=term-missing
pytest -m unit -v
pytest -m integration -v
```

## 5. Security scans

```powershell
bandit -r app\ -f screen
pip-audit
ruff check app\ tests\
```

## 6. Optional: local LLM chatbot (Ollama)

```powershell
winget install Ollama.Ollama
ollama pull qwen3:1.7b
$env:CHATBOT_ENGINE = "llm"
```
Recommended for 8GB-RAM CPU-only machines: `qwen3:1.7b`. The engine automatically
falls back to the rule-based chatbot if Ollama is unavailable or times out — see
`app/llm_chatbot.py` for the fallback logic and prompt-injection mitigations.
Keep `CHATBOT_ENGINE=rule_based` for cloud deployment (smaller image, no extra
RAM/build-time cost); demo the LLM mode locally.

## 7. Docker

```powershell
docker build -t requirement-auditor:latest .
docker run --rm requirement-auditor:latest whoami   # expect: appuser (non-root check)
docker run --env-file .env -p 7860:7860 requirement-auditor:latest
```

## 8. Deployment

Backend → Hugging Face Space (Docker SDK, CPU basic — chosen for its larger free-tier
RAM versus the 512MB limit that caused OOM failures on a prior Render deployment):
```powershell
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/requirement-drift-auditor
git push space main
```

Frontend → Streamlit Community Cloud: connect the GitHub repo via its web UI,
main file `frontend/streamlit_app.py`, set `API_URL` secret to the HF Space URL.

## Security controls implemented

- Bcrypt password hashing, JWT in httpOnly + secure + samesite cookie (never localStorage)
- Rate limiting on auth and analysis endpoints (brute-force / bot defense)
- IDOR protection via ownership checks on all audit lookups
- File upload validation: size cap, real-content-type detection (not extension trust),
  path traversal sanitization, PDF/DOCX bomb guards
- Pydantic input validation with control-character stripping on all text fields
- Security response headers (CSP, HSTS, X-Frame-Options, nosniff)
- CORS restricted to a named origin, never `*`
- Non-root Docker user, multi-stage build, dependency and image vulnerability scanning in CI
- Rule-based chatbot by default (zero prompt-injection surface); optional LLM path
  is context-restricted, timeout-bounded, and auto-falls-back on failure
