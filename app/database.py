"""DATABASE_URL controls backend: sqlite locally, postgresql in prod — no code change needed."""
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    audits = relationship("Audit", back_populates="owner")

class Audit(Base):
    __tablename__ = "audits"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename_original = Column(String(255))
    filename_updated = Column(String(255))
    result_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    owner = relationship("User", back_populates="audits")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()