from .store import global_store

import hashlib
import base64

from concurrent.futures import ThreadPoolExecutor
import time

import wave, json, os

from pydub import AudioSegment, silence
import io
import subprocess

from openai import OpenAI
from app.core.redis import redis_client

def get_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ----------------------------------------------------
# Call AI (GPT 평가)
# ----------------------------------------------------
def call_ai(system_prompt: str, user_prompt: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",   # 빠른 피드백용
        # model="gpt-4o",      # 더 정밀하게 하고 싶을 때
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,  # 일관된 점수 유지
        response_format={"type": "json_object"}  # JSON 응답 강제
    )
    return response.choices[0].message.content

# -----------------------------
# Whisper STT (발음 그대로 반환 테스트용)
# Vosk 대비 1분 음성 기준 25초 → 3~5초
# 발음 교정 억제 프롬프트 적용 (gonna, wanna 등 그대로 반환)
# -----------------------------
def stt_whisper(user_audio_path: str):
    client = get_client()

    with open(user_audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1", # tts-1: 빠른 버전 / tts-1-hd: 고품질 버전 선택 가능
            file=audio_file,
            response_format="verbose_json",  # 단어별 confidence 포함
            prompt=(
                "Transcribe exactly as spoken. "
                "Do not correct mispronunciations, grammar, or word choices. "
                "Include fillers like 'uh', 'um', 'gonna', 'wanna' as heard."
            )
        )

    text = result.text.strip()

    # verbose_json이면 단어별 정보 포함
    words = getattr(result, "words", []) or []
    conf_dict = {w.word: getattr(w, "probability", 1.0) for w in words}

    return text, conf_dict

# -----------------------------
# Audio trimming helper
# -----------------------------
def trim_audio(audio_bytes: bytes, silence_thresh=-40, min_silence_len=200) -> bytes:
    """
    오디오 끝부분의 불필요한 무음/이상음을 제거
    - silence_thresh: 무음으로 인식할 dB 기준 (-40~ -50 추천)
    - min_silence_len: 제거할 최소 무음 길이(ms)
    """
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
    
    silences = silence.detect_silence(
        audio,
        silence_thresh=silence_thresh,
        min_silence_len=min_silence_len
    )

    # 끝부분 무음 제거
    if silences:
        last_silence = silences[-1]
        if last_silence[1] >= len(audio) - 100:  # 끝에 무음이 있는 경우
            audio = audio[:last_silence[0]]

    buf = io.BytesIO()
    audio.export(buf, format="wav")
    buf.seek(0)
    return buf.getvalue()

# ----------------------------------------------------
# OpenAI TTS
# Coqui TTS 대비 12초 → 1~2초
# 동일 문장은 Redis 캐시 반환 (TTS 생성 스킵)
# 캐시 키 생성 전 텍스트 정규화 (\xa0, \r\n 등 제거)
# ----------------------------------------------------
TTS_CACHE_TTL = 60 * 60 * 6  # 6시간

def tts_generate_us(text: str) -> tuple[bytes, float]:
    # 정규화: \xa0, \r\n 등 특수문자 제거 → 캐시 히트율 향상
    normalized = text.strip().replace("\xa0", " ").replace("\r\n", " ").replace("\n", " ")
    cache_key = f"tts:{hashlib.md5(text.encode()).hexdigest()}"

    # 캐시 확인
    cached = redis_client.get(cache_key)
    if cached:
        audio_bytes = base64.b64decode(cached)
        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        return audio_bytes, len(seg) / 1000.0

    # OpenAI TTS 생성
    client = get_client()
    response = client.audio.speech.create(
        model="tts-1",    # tts-1-hd: 고품질, tts-1: 빠른 버전
        voice="alloy",    # 미국 영어 발음
        input=normalized,
        response_format="wav"
    )
    audio_bytes = response.content

    # trimming 적용
    trimmed_bytes = trim_audio(audio_bytes)

    # Redis 캐싱
    redis_client.set(cache_key, base64.b64encode(trimmed_bytes), ex=TTS_CACHE_TTL)

    seg = AudioSegment.from_file(io.BytesIO(trimmed_bytes), format="wav")
    duration_sec = len(seg) / 1000.0

    return trimmed_bytes, duration_sec
    
# -----------------------------
# Audio duration helper
# -----------------------------
def get_audio_duration(file_path: str) -> float:
    """wav 파일 길이(초)"""
    with wave.open(file_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)   

def evaluate_pronunciation(target_text: str, user_audio_path: str, tutor_type: str = "us"):
    """
    전체 흐름: 사용자 오디오 → STT + TTS 병렬 처리 → 발음 평가 → 결과 반환
    """
    # 1) TTS + STT 병렬 처리 (서로 의존성 없음)
    t0 = time.time()
    with ThreadPoolExecutor() as executor:
        tts_future = executor.submit(tts_generate_us, target_text)
        stt_future = executor.submit(stt_whisper, user_audio_path) # whisper api로 테스트

        ref_audio, ref_duration = tts_future.result()
        user_transcript, conf_dict = stt_future.result()
    print(f"[TTS+STT 병렬] {time.time()-t0:.2f}s")

    # 2) 사용자발화시간
    t1 = time.time()
    user_seg = AudioSegment.from_file(user_audio_path)
    user_duration = len(user_seg) / 1000.0
    print(f"[발화시간 계산] {time.time()-t1:.2f}s")

    # 3) GPT 평가
    system_prompt ="""You are an English pronunciation tutor. 
    Your job is to evaluate how well a learner pronounced a target phrase.

    Criteria:
    1. Content words (nouns, verbs, adjectives, adverbs) are most important. 
       - Strong weight if clear and confident.
       - Medium if slightly weak but understandable.
       - Low if unclear or missing.
    2. Function words (articles, prepositions, auxiliaries) are less important. 
       - If the learner used natural contractions (I'm, gonna, don't), give extra credit.
       - If omitted but sentence is still natural, small penalty only.
    3. Speed & rhythm: If user’s speech duration is close to native reference duration, give a bonus.
    4. Give short, encouraging feedback for each important word.
    5. Return a total score as a percentage (0-100).
    
    IMPORTANT: Return your final result in JSON format only.
    IMPORTANT SCORING RULES:
        - Always return a score between 50 and 100.
        - If the learner’s speech is generally understandable, the minimum score should be 70.
        - Only if the speech is completely unintelligible, give below 50.

IMPORTANT: Return your final result in JSON format only.
                
example response:
{
  "score": 87.5,
  "strengths": [
    "Content word 'goal' was clear",
    "Used contraction 'I'm' naturally"
  ],
  "improvements": [
    "Content word 'because' was unclear",
    "Speed was significantly slower than native reference"
  ],
  "rhythm_feedback": "Your speech was slightly slower than the native reference.",
  "feedback": []
}
 

    """

    user_prompt = f"""
    Target phrase: "{target_text}"
    Learner transcript: "{user_transcript}"
    Learner duration: {user_duration:.2f} seconds
    Reference duration: {ref_duration:.2f} seconds
    """

    # AI 호출
    t2 = time.time()
    ai_response = call_ai(system_prompt, user_prompt)
    print(f"[GPT 호출] {time.time()-t2:.2f}s")

    try :
        result = json.loads(ai_response)
    except json.JSONDecodeError:
        result = {
                "score": 0, 
                "feedback": ["AI 응답 파싱 실패"], 
                "user_transcript": user_transcript, 
                "target_text": target_text
            }


    # 최종 결과
    total_result = {
        "score": result.get("score", 0),
        "feedback": result.get("feedback", []),
        "strengths": result.get("strengths", []),
        "improvements": result.get("improvements", []),
        "rhythm_feedback": result.get("rhythm_feedback", ""),
        # "target_chunks": target_chunks,
        "reference_tts": ref_audio,   # US tutor 음성 (wav 바이트)
        "user_transcript": user_transcript,
        "user_duration": user_duration,
        "ref_duration": ref_duration
    }
    return total_result

