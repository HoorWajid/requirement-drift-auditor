"""Pydantic request/response schemas — the input-validation boundary."""
import re
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict

PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,128}$")

class UserRegister(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v: str) -> str:
        if not PASSWORD_RE.match(v):
            raise ValueError("Password must be 8-128 chars with upper, lower, and a digit.")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class RequirementPair(BaseModel):
    model_config = ConfigDict(str_max_length=5000)
    req_original: str
    req_updated: str

    @field_validator("req_original", "req_updated")
    @classmethod
    def no_empty_or_control_chars(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Requirement text cannot be empty.")
        if len(v) > 5000:
            raise ValueError("Requirement text too long (max 5000 chars).")
        return "".join(ch for ch in v if ch.isprintable() or ch.isspace())

class ChatQuery(BaseModel):
    audit_id: int
    question: str

    @field_validator("question")
    @classmethod
    def clean_question(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 500:
            raise ValueError("Question must be 1-500 characters.")
        return v