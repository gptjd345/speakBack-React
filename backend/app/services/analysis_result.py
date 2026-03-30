from app.db.database import SessionLocal
from app.db.models import SessionHistory, SessionPattern
from app.core.embedding import get_embedding, build_pattern_text, extract_transcript_mismatches
from datetime import datetime


def save_analysis_result(
    *,
    user_id: int,
    target_text: str,
    user_name: str,
    user_transcript: str | None,
    score,
    strengths: list,
    improvements: list,
    rhythm_feedback: str | None,
):
    """분석 결과를 session_history + session_patterns 테이블에 저장"""
    db = SessionLocal()
    try:
        record = SessionHistory(
            user_id=user_id,
            target_text=target_text or "",
            user_transcript=user_transcript,
            score=score,
            strengths=strengths or [],
            improvements=improvements or [],
            rhythm_feedback=rhythm_feedback,
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        mismatches = extract_transcript_mismatches(target_text or "", user_transcript or "")
        pattern_text = build_pattern_text(improvements or [], mismatches, score or 0)
        embedding = get_embedding(pattern_text)

        pattern = SessionPattern(
            session_id=record.id,
            user_id=user_id,
            pattern_text=pattern_text,
            weak_words=improvements or [],
            transcript_mismatches=mismatches,
            score=score or 0,
            embedding=embedding,
            created_at=datetime.utcnow(),
        )
        db.add(pattern)
        db.commit()
        print(f"=== [save_analysis_result] 저장 완료 id={record.id} ===")

    except Exception as e:
        db.rollback()
        print(f"=== [save_analysis_result] 저장 실패: {e} ===")
    finally:
        db.close()
