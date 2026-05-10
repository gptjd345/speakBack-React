import hashlib
import base64
import threading
import wave
import io
import os

from pydub import AudioSegment, silence
from openai import OpenAI
from app.core.redis import redis_client

# ─── librosa / numba JIT 워밍업 ─────────────────────────────────────────────
# numba는 첫 호출 시 JIT 컴파일로 5-15초 소요.
# /prepare 엔드포인트에서 백그라운드로 미리 실행해두면
# 실제 분석 시점엔 컴파일이 완료되어 즉시 실행됨.
# acoustic.py의 analyze_acoustic_features가 이 Event를 대기함.
librosa_warmup_done = threading.Event()
_librosa_warmup_lock = threading.Lock()
_librosa_warmup_started = False


def warmup_librosa():
    """백그라운드에서 librosa pyin 더미 호출 → numba JIT 컴파일 완료."""
    global _librosa_warmup_started
    with _librosa_warmup_lock:
        if _librosa_warmup_started:
            return
        _librosa_warmup_started = True

    def _run():
        try:
            import librosa
            import numpy as np
            dummy = np.zeros(3200, dtype=np.float32)  # 0.2s @ 16kHz
            librosa.pyin(
                dummy,
                fmin=librosa.note_to_hz("C2"),
                fmax=librosa.note_to_hz("C7"),
                sr=16000,
            )
            print("[librosa warmup] numba JIT 컴파일 완료")
        except Exception as e:
            print(f"[librosa warmup] 실패: {e}")
        finally:
            librosa_warmup_done.set()

    threading.Thread(target=_run, daemon=True).start()


def get_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ─── Whisper STT ─────────────────────────────────────────────────────────────
# Vosk 대비 1분 음성 기준 25초 → 3~5초
# 발음 교정 억제 프롬프트 적용 (gonna, wanna 등 그대로 반환)
def stt_whisper(user_audio_path: str):
    client = get_client()

    with open(user_audio_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word"],
            prompt=(
                "Transcribe exactly as spoken. "
                "Do not correct mispronunciations, grammar, or word choices. "
                "Include fillers like 'uh', 'um', 'gonna', 'wanna' as heard."
            ),
        )

    text = result.text.strip()
    words = getattr(result, "words", []) or []
    conf_dict = {w.word: getattr(w, "probability", 1.0) for w in words}
    word_timestamps = [
        {
            "word": w.word,
            "start": float(getattr(w, "start", 0.0)),
            "end": float(getattr(w, "end", 0.0)),
        }
        for w in words
        if getattr(w, "start", None) is not None
    ]

    return text, conf_dict, word_timestamps


# ─── Audio utilities ─────────────────────────────────────────────────────────

def trim_audio(audio_bytes: bytes, silence_thresh=-40, min_silence_len=200) -> bytes:
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
    silences = silence.detect_silence(
        audio, silence_thresh=silence_thresh, min_silence_len=min_silence_len
    )
    if silences:
        last_silence = silences[-1]
        if last_silence[1] >= len(audio) - 100:
            audio = audio[:last_silence[0]]
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    buf.seek(0)
    return buf.getvalue()


def get_audio_duration(file_path: str) -> float:
    with wave.open(file_path, "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


# ─── OpenAI TTS ──────────────────────────────────────────────────────────────
# Coqui TTS 대비 12초 → 1~2초
# 동일 문장은 Redis 캐시 반환, 캐시 키 생성 전 텍스트 정규화

TTS_CACHE_TTL = 60 * 60 * 6  # 6시간


def tts_generate_us(text: str) -> tuple[bytes, float]:
    normalized = text.strip().replace("\xa0", " ").replace("\r\n", " ").replace("\n", " ")
    cache_key = f"tts:{hashlib.md5(text.encode()).hexdigest()}"

    cached = redis_client.get(cache_key)
    if cached:
        audio_bytes = base64.b64decode(cached)
        seg = AudioSegment.from_file(io.BytesIO(audio_bytes), format="wav")
        return audio_bytes, len(seg) / 1000.0

    client = get_client()
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=normalized,
        response_format="wav",
    )
    audio_bytes = response.content
    trimmed_bytes = trim_audio(audio_bytes)

    redis_client.set(cache_key, base64.b64encode(trimmed_bytes), ex=TTS_CACHE_TTL)

    seg = AudioSegment.from_file(io.BytesIO(trimmed_bytes), format="wav")
    return trimmed_bytes, len(seg) / 1000.0
