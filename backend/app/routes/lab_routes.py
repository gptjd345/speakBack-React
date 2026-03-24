from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.dependencies import get_current_user
from app.core.embedding import get_embedding, build_pattern_text, extract_transcript_mismatches
from app.db.database import SessionLocal
from app.db.models import SessionPattern
from sqlalchemy import text
from openai import OpenAI
import json
import os

router = APIRouter()


class LabFeedbackRequest(BaseModel):
    current_session_id: int  # 가장 최근 coach 세션 ID


@router.post("/feedback")
def get_lab_feedback(
    body: LabFeedbackRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    RAG 기반 개인화 피드백.
    현재 세션 패턴으로 과거 유사 패턴 검색 → GPT로 개인화 피드백 생성.
    """
    db = SessionLocal()
    try:
        from app.db.models import SessionHistory

        # 현재 세션 조회
        current_session = db.query(SessionHistory).filter(
            SessionHistory.id == body.current_session_id,
            SessionHistory.user_id == current_user["id"],
        ).first()

        if not current_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 현재 세션 패턴 텍스트 생성 & 임베딩
        mismatches = extract_transcript_mismatches(
            current_session.target_text or "",
            current_session.user_transcript or "",
        )
        pattern_text = build_pattern_text(
            current_session.improvements or [],
            mismatches,
            current_session.score or 0,
        )
        query_vector = get_embedding(pattern_text)

        # pgvector 유사도 검색 (현재 세션 제외, 상위 5개)
        similar_patterns = db.execute(
            text("""
            SELECT sp.pattern_text, sp.weak_words, sp.transcript_mismatches,
                   sp.score, sh.target_text, sh.created_at,
                   sp.embedding <=> :query_vec AS distance
            FROM session_patterns sp
            JOIN session_history sh ON sp.session_id = sh.id
            WHERE sp.user_id = :user_id
              AND sp.session_id != :current_id
            ORDER BY sp.embedding <=> :query_vec
            LIMIT 5
            """),
            {
                "query_vec": str(query_vector),
                "user_id": current_user["id"],
                "current_id": body.current_session_id,
            },
        ).fetchall()

        if not similar_patterns:
            return {
                "feedback": "Not enough history yet. Keep practicing and you'll see personalized patterns here!",
                "retrieved_count": 0,
            }

        # RAG context 구성
        context_parts = []
        for i, row in enumerate(similar_patterns, 1):
            context_parts.append(
                f"Session {i} (score: {row.score:.0f}, target: '{row.target_text}'):\n"
                f"  - Weak words: {row.weak_words}\n"
                f"  - Mismatches: {row.transcript_mismatches}"
            )
        rag_context = "\n\n".join(context_parts)

        # GPT 개인화 피드백 생성
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an encouraging English pronunciation coach analyzing a learner's personal history.\n"
                        "Based on retrieved past sessions, identify RECURRING patterns — "
                        "words or types of words that the learner consistently struggles with.\n"
                        "Give specific, actionable advice that addresses the root cause, not just symptoms.\n"
                        "Be encouraging. Keep response concise (3-5 sentences)."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Current session:\n{pattern_text}\n\n"
                        f"Similar past sessions:\n{rag_context}\n\n"
                        "What recurring patterns do you see, and what should this learner focus on?"
                    ),
                },
            ],
        )

        feedback = response.choices[0].message.content

        return {
            "feedback": feedback,
            "retrieved_count": len(similar_patterns),
            "pattern_text": pattern_text,
        }

    finally:
        db.close()


# ─── /sentences: 취약 패턴 기반 연습 문장 3개 생성 ──────────────────
class SentencesRequest(BaseModel):
    feedback: str  # /feedback 에서 받은 RAG 피드백 텍스트


@router.post("/sentences")
def get_practice_sentences(
    body: SentencesRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    사용자의 session_patterns에서 반복 취약 패턴(weak_words, mismatches) 상위 3개 추출.
    RAG 피드백 + 패턴 데이터를 context로 GPT가 연습 문장 3개 생성.
    informal / neutral / formal 각 1개씩.
    """
    db = SessionLocal()
    try:
        # 최근 20개 세션 패턴에서 취약 단어 빈도 집계
        patterns = (
            db.query(SessionPattern)
            .filter(SessionPattern.user_id == current_user["id"])
            .order_by(SessionPattern.created_at.desc())
            .limit(20)
            .all()
        )

        word_count = {}
        mismatch_count = {}
        for p in patterns:
            for w in (p.weak_words or []):
                word_count[w] = word_count.get(w, 0) + 1
            for m in (p.transcript_mismatches or []):
                mismatch_count[m] = mismatch_count.get(m, 0) + 1

        top_weak = sorted(word_count.items(), key=lambda x: -x[1])[:3]
        top_mismatches = sorted(mismatch_count.items(), key=lambda x: -x[1])[:3]

        weak_summary = (
            ", ".join([f"'{w}' ({c}x)" for w, c in top_weak])
            if top_weak else "none recorded yet"
        )
        mismatch_summary = (
            ", ".join([f"'{m}' ({c}x)" for m, c in top_mismatches])
            if top_mismatches else "none recorded yet"
        )

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.7,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an English pronunciation coach creating targeted practice sentences.\n"
                        "Generate exactly 3 sentences following these rules:\n"
                        "1. Each sentence naturally includes the learner's weak words or similar stress/rhythm patterns.\n"
                        "2. Sentence 1: casual/informal (everyday conversation)\n"
                        "   Sentence 2: neutral (general use)\n"
                        "   Sentence 3: formal/professional\n"
                        "3. Each sentence is 8-15 words, natural-sounding English.\n"
                        "4. Respond with ONLY a valid JSON array of 3 strings. No explanation, no markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Pattern analysis feedback:\n{body.feedback}\n\n"
                        f"Top recurring weak content words: {weak_summary}\n"
                        f"Top recurring Whisper mismatches: {mismatch_summary}\n\n"
                        "Generate 3 practice sentences that target these specific patterns."
                    ),
                },
            ],
        )

        content = response.choices[0].message.content.strip()
        sentences = json.loads(content)
        if not isinstance(sentences, list):
            sentences = []

        return {"sentences": sentences[:3]}

    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse generated sentences.")
    finally:
        db.close()
