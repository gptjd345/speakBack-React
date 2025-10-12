from .store import global_store
import re
from typing import Optional, Dict

from vosk import Model, KaldiRecognizer
import wave, json, os

from pydub import AudioSegment, silence
import io
import subprocess

from openai import OpenAI

def get_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ----------------------------------------------------
# Call AI 
# ----------------------------------------------------
def call_ai(system_prompt: str, user_prompt: str) -> str:
    """
    GPT 기반 평가 호출
    """
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

# ----------------------------------------------------
# Audio data preprocessing (BytesIO → 16kHz mono wav)
# ----------------------------------------------------
def prepare_audio_for_vosk(org_file_path) -> io.BytesIO:
    """
    Streamlit BytesIO / UploadedFile → Vosk에서 쓸 수 있는 16kHz mono wav로 변환
    """
    process = subprocess.run(
        [
            "ffmpeg",
            "-i", org_file_path,
            "-ar", "16000",    # 16kHz
            "-ac", "1",        # mono
            "-f", "wav",
            "pipe:1"
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True
    )
    return io.BytesIO(process.stdout)

# -----------------------------
# Vosk 모델 로드
# -----------------------------
VOSK_MODEL_PATH = "vosk-model-small-en-us-0.15"  # 모델 다운로드 후 경로
if not os.path.exists(VOSK_MODEL_PATH):
    raise FileNotFoundError("Vosk 모델을 먼저 다운로드하세요!")
vosk_model = Model(VOSK_MODEL_PATH)

def stt_vosk(user_audio_path: str) :
    """사용자 음성파일을 Vosk STT로 변환"""
    audio_stream = prepare_audio_for_vosk(user_audio_path)

    # Vosk recognizer 초기화
    model = Model(VOSK_MODEL_PATH)
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(True)

    # wav header skip 필요 → wave 모듈 사용 X, raw bytes 그대로 처리
    while True:
        data = audio_stream.read(4000)
        if len(data) == 0:
            break
        rec.AcceptWaveform(data)

    result = json.loads(rec.FinalResult())
    text = result.get("text", "").strip()
    words = result.get("result", [])  # 단어별 confidence

    conf_dict = {w["word"]: w.get("conf", 0) for w in words}
    return text, conf_dict

# Try import Coqui TTS (optional)
try:
    from TTS.api import TTS
    # 앱 시작 시 한 번만 로드
    # 모델 선택: (사용 가능한 모델 이름은 환경에 따라 바꿔야 함)
    # 예: LJSpeech → 미국 여성 화자 데이터셋 기반
    # 발음은 전형적인 American English
    tts_us_model = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", 
                    progress_bar=False, gpu=False)
    TTS_AVAILABLE = True
except Exception:
    TTS_AVAILABLE = False
#tts_uk_model = TTS(model_name="tts_models/en/vctk/vits", progress_bar=False, gpu=False)

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

# -----------------------------
# TTS 생성 (길이 포함)
# -----------------------------
def tts_generate_us(text: str) -> tuple[bytes, float]:
    """US tutor TTS → wav 바이트 리턴"""
    wav_path = "reference_us.wav"
    tts_us_model.tts_to_file(text=text, file_path=wav_path)
    with open(wav_path, "rb") as f:
        wav_bytes = f.read()

    # trimming 적용
    trimmed_bytes = trim_audio(wav_bytes)

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
    전체 흐름: 사용자 오디오 → STT → 발음 평가 → 결과 반환
    """
    # 1) 튜터 참조 음성, 튜터 음성시간
    ref_audio,ref_duration = tts_generate_us(target_text) if tutor_type == "us" else None

    # 2) 사용자 음성 → STT
    user_transcript, conf_dict = stt_vosk(user_audio_path)
    user_seg = AudioSegment.from_file(user_audio_path)
    # 사용자발화시간
    user_duration = len(user_seg) / 1000.0

    # 3) Invoke AI Prompt
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

    example response:
    {
      "score": 87.5,
      "feedback": [
        "Content word 'goal' was clear 👍",
        "Function word 'to' was slightly weak but acceptable.",
        "Used contraction 'I'm' naturally 👌"
      ],
      "user_transcript": "...",
      "target_text": "..."
    }
 

    """

    user_prompt = f"""
    Target phrase: "{target_text}"
    Learner transcript: "{user_transcript}"
    Learner duration: {user_duration:.2f} seconds
    Reference duration: {ref_duration:.2f} seconds
    """

    # pseudo code: AI 호출
    ai_response = call_ai(system_prompt, user_prompt)

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
        # "target_chunks": target_chunks,
        "reference_tts": ref_audio,   # US tutor 음성 (wav 바이트)
        "user_transcript": user_transcript,
        "user_duration": user_duration,
        "ref_duration": ref_duration
    }
    return total_result

