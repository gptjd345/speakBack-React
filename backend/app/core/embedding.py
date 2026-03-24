import os
import hashlib
import json
from openai import OpenAI
from app.core.redis import redis_client

EMBED_CACHE_TTL = 60 * 60 * 24 * 7  # 7일

def get_embedding(text: str) -> list[float]:
    """
    텍스트를 OpenAI text-embedding-3-small로 벡터화.
    동일 텍스트는 Redis 캐시 반환.
    """
    cache_key = f"embed:{hashlib.md5(text.encode()).hexdigest()}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    vector = response.data[0].embedding
    redis_client.set(cache_key, json.dumps(vector), ex=EMBED_CACHE_TTL)
    return vector


def build_pattern_text(
    improvements: list,
    transcript_mismatches: list,
    score: float,
) -> str:
    """패턴 벡터화에 쓸 텍스트 생성."""
    parts = []
    if improvements:
        parts.append(f"weak content words: {', '.join(improvements)}")
    if transcript_mismatches:
        parts.append(f"pronunciation mismatches: {', '.join(transcript_mismatches)}")
    parts.append(f"score: {int(score) if score else 0}")
    return ". ".join(parts)


def extract_transcript_mismatches(target_text: str, user_transcript: str) -> list[str]:
    """
    target_text와 user_transcript를 단어 단위로 비교해서
    Whisper가 다르게 전사한 단어 추출.
    """
    if not target_text or not user_transcript:
        return []

    target_words = target_text.lower().split()
    transcript_words = user_transcript.lower().split()

    mismatches = []
    for i, t_word in enumerate(target_words):
        # 구두점 제거
        t_clean = t_word.strip(".,!?;:'\"")
        if i < len(transcript_words):
            u_clean = transcript_words[i].strip(".,!?;:'\"")
            if t_clean != u_clean and t_clean:
                mismatches.append(f"{t_clean}->{u_clean}")
        else:
            mismatches.append(f"{t_clean}->missing")
    return mismatches
