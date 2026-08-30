"""
Main FastAPI application. Order of concerns on every request:
1. Rate limiting (slowapi) — before anything else runs
2. Security headers middleware
3. Auth (JWT cookie) on protected routes
4. Pydantic validation (schemas.py) on the request body
5. Business logic

Chatbot engine is pluggable via CHATBOT_ENGINE env var:
  CHATBOT_ENGINE=rule_based (default) -> app/chatbot.py, zero external dependency
  CHATBOT_ENGINE=llm                  -> app/llm_chatbot.py, local Ollama, auto-falls
                                          back to rule_based if Ollama is unavailable
"""
import json
import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from sqlalchemy.orm import Session

from app.database import init_db, get_db, User, Audit
from app.schemas import UserRegister, UserLogin, RequirementPair, ChatQuery
from app.security import (
    limiter, hash_password, verify_password, create_access_token,
    get_current_user_email, add_security_headers,
)
from app.document_processor import validate_and_extract
from app.drift_detector import analyze_pair

CHATBOT_ENGINE = os.getenv("CHATBOT_ENGINE", "rule_based")  # "rule_based" | "ollama" | "huggingface"
if CHATBOT_ENGINE == "ollama":
    from app.llm_chatbot import answer as chatbot_answer
else:
    from app.chatbot import answer as chatbot_answer

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"

app = FastAPI(title="Requirement Drift & Consistency Auditor")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.middleware("http")(add_security_headers)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,   # never "*" once cookies/auth are involved
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    # Deliberately minimal — no version/stack info leaked to unauthenticated callers
    return {"status": "ok"}


# ---------- AUTH ----------

@app.post("/auth/register")
@limiter.limit("5/minute")  # bot/brute-force guard on account creation
def register(request: Request, payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        # Same generic error whether email exists or not, to avoid user enumeration
        raise HTTPException(status_code=400, detail="Registration failed. Try a different email.")
    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    return {"message": "Registered successfully."}


@app.post("/auth/login")
@limiter.limit("10/minute")  # brute-force guard
def login(request: Request, payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        # Generic message — never reveal whether it was the email or password that was wrong
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = create_access_token(subject=user.email)
    response.set_cookie(
        key="access_token", value=token,
        httponly=True, secure=COOKIE_SECURE, samesite="strict", max_age=1800,
    )
    return {"message": "Logged in."}


@app.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out."}


# ---------- CORE FEATURE (protected) ----------

@app.post("/analyze")
@limiter.limit("20/minute")  # protects the expensive NLP path from abuse
def analyze(
    request: Request,
    payload: RequirementPair,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    result = analyze_pair(payload.req_original, payload.req_updated)

    user = db.query(User).filter(User.email == user_email).first()
    audit = Audit(
        owner_id=user.id,
        filename_original="inline_text",
        filename_updated="inline_text",
        result_json=json.dumps([result]),
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    result["audit_id"] = audit.id
    return result


@app.post("/upload-analyze")
@limiter.limit("10/minute")  # tighter limit — file parsing is the costliest path
async def upload_analyze(
    request: Request,
    original_file: UploadFile = File(...),
    updated_file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    original_bytes = await original_file.read()
    updated_bytes = await updated_file.read()

    try:
        original_text = validate_and_extract(original_bytes, original_file.filename)
        updated_text = validate_and_extract(updated_bytes, updated_file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result = analyze_pair(original_text, updated_text)

    user = db.query(User).filter(User.email == user_email).first()
    audit = Audit(
        owner_id=user.id,
        filename_original=original_file.filename,
        filename_updated=updated_file.filename,
        result_json=json.dumps([result]),
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    result["audit_id"] = audit.id
    return result


@app.get("/audits/{audit_id}")
def get_audit(
    audit_id: int,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    user = db.query(User).filter(User.email == user_email).first()
    audit = db.query(Audit).filter(Audit.id == audit_id, Audit.owner_id == user.id).first()
    # Ownership check above is the IDOR guard — without "owner_id == user.id",
    # any logged-in user could fetch ANY audit_id by guessing integers.
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found.")
    return {"id": audit.id, "results": json.loads(audit.result_json)}


@app.post("/chat")
@limiter.limit("30/minute")
def chat(
    request: Request,
    payload: ChatQuery,
    db: Session = Depends(get_db),
    user_email: str = Depends(get_current_user_email),
):
    user = db.query(User).filter(User.email == user_email).first()
    audit = db.query(Audit).filter(Audit.id == payload.audit_id, Audit.owner_id == user.id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found.")
    results = json.loads(audit.result_json)
    return chatbot_answer(payload.question, results)
