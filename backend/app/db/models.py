from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float, JSON
from datetime import datetime
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    
    token_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    jti = Column(String(64), unique=True, index=True) # Refresh Token j
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SessionHistory(Base):
    __tablename__ = "session_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    target_text = Column(Text, nullable=False)           # 목표 문장
    user_transcript = Column(Text, nullable=True)        # STT 변환 결과
    score = Column(Float, nullable=True)                 # 점수 (0~100)
    strengths = Column(JSON, nullable=True)              # 잘한 부분 ["word1", ...]
    improvements = Column(JSON, nullable=True)           # 개선 필요 ["word1", ...]
    rhythm_feedback = Column(Text, nullable=True)        # 리듬 피드백
    created_at = Column(DateTime, default=datetime.utcnow)    