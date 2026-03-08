# app/routers/history.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.db.database import get_db
from app.db.models import SessionHistory
from app.core.dependencies import get_current_user  # 기존 JWT 인증 의존성

router = APIRouter()

# ─── Response 스키마 ──────────────────────────────────────────────
class SessionHistoryItem(BaseModel):
    id: int
    target_text: str
    score: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionHistoryDetail(BaseModel):
    id: int
    target_text: str
    user_transcript: str | None
    score: float | None
    strengths: list | None
    improvements: list | None
    rhythm_feedback: str | None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── 목록 조회 (사이드 히스토리 패널용) ──────────────────────────
@router.get("/", response_model=List[SessionHistoryItem])
def get_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    records = (
        db.query(SessionHistory)
        .filter(SessionHistory.user_id == current_user["id"])
        .order_by(desc(SessionHistory.created_at))
        .limit(limit)
        .all()
    )
    return records


# ─── 단건 상세 조회 (히스토리 클릭 시 피드백 전체 표시) ──────────
@router.get("/{session_id}", response_model=SessionHistoryDetail)
def get_history_detail(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    record = (
        db.query(SessionHistory)
        .filter(
            SessionHistory.id == session_id,
            SessionHistory.user_id == current_user["id"],  # 본인 것만 조회
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    return record