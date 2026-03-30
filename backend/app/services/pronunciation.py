import hashlib
import base64
import threading

from concurrent.futures import ThreadPoolExecutor
import time

import wave, json, os

from pydub import AudioSegment, silence
import io
import subprocess
import numpy as np

from openai import OpenAI
from app.core.redis import redis_client

# ----------------------------------------------------
# librosa / numba JIT 워밍업
# numba는 첫 호출 시 JIT 컴파일로 5-15초 소요.
# /prepare 엔드포인트에서 백그라운드로 미리 실행해두면
# 실제 분석 시점엔 컴파일이 완료되어 즉시 실행됨.
# ----------------------------------------------------
_librosa_warmup_done  = threading.Event()
_librosa_warmup_lock  = threading.Lock()
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
            _librosa_warmup_done.set()

    threading.Thread(target=_run, daemon=True).start()

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
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word"],  # 단어별 타임스탬프 활성화
            prompt=(
                "Transcribe exactly as spoken. "
                "Do not correct mispronunciations, grammar, or word choices. "
                "Include fillers like 'uh', 'um', 'gonna', 'wanna' as heard."
            )
        )

    text = result.text.strip()

    words = getattr(result, "words", []) or []
    conf_dict = {w.word: getattr(w, "probability", 1.0) for w in words}

    # 단어별 타임스탬프 추출
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

# ----------------------------------------------------
# Acoustic Feature Extraction (librosa + Whisper timestamp)
# numba JIT는 warmup_librosa()로 /prepare 시점에 미리 완료됨
# ----------------------------------------------------
def analyze_acoustic_features(audio_path: str, word_timestamps: list) -> list:
    """
    단어별 음향 특징 추출.
    word_timestamps: stt_whisper()가 반환한 [{word, start, end}, ...]

    Returns:
        list of dict: [{
            word, start, end,
            rms_energy,      # 에너지 크기
            mean_pitch,      # 평균 피치(Hz), 무성음=0
            duration,        # 발화 길이(초)
            linking_next,    # 다음 단어와 연음 여부 (gap < 50ms)
            energy_rank,     # 문장 내 에너지 순위 (1 = 가장 강함)
            energy_rank_pct, # 상위 몇 %
        }, ...]
    """
    import librosa
    import numpy as np

    if not word_timestamps:
        return []

    # warmup 완료 대기 (최대 30초 — 이미 완료됐으면 즉시 통과)
    warmed = _librosa_warmup_done.wait(timeout=30)
    if not warmed:
        print("[analyze_acoustic_features] librosa warmup 타임아웃 — 그냥 진행")

    y, sr = librosa.load(audio_path, sr=16000)

    raw_features = []
    for i, w in enumerate(word_timestamps):
        start_s = max(0.0, w["start"])
        end_s   = min(len(y) / sr, w["end"])

        if end_s <= start_s:
            continue

        seg = y[int(start_s * sr): int(end_s * sr)]
        duration = end_s - start_s

        # RMS 에너지
        rms = float(np.sqrt(np.mean(seg ** 2))) if len(seg) > 0 else 0.0

        # 피치 (F0) — warmup 덕분에 JIT 컴파일 완료 상태
        mean_pitch = 0.0
        if duration >= 0.05:
            try:
                f0, voiced, _ = librosa.pyin(
                    seg,
                    fmin=librosa.note_to_hz("C2"),
                    fmax=librosa.note_to_hz("C7"),
                    sr=sr,
                )
                voiced_f0 = f0[voiced] if voiced is not None else np.array([])
                if len(voiced_f0) > 0:
                    mean_pitch = float(np.nanmean(voiced_f0))
            except Exception:
                pass

        # 연음: 다음 단어와의 gap
        if i < len(word_timestamps) - 1:
            gap = word_timestamps[i + 1]["start"] - w["end"]
            linking_next = gap < 0.05
        else:
            linking_next = False

        raw_features.append({
            "word": w["word"],
            "start": start_s,
            "end": end_s,
            "duration": round(duration, 3),
            "rms_energy": rms,
            "mean_pitch": round(mean_pitch, 1),
            "linking_next": linking_next,
            "energy_rank": 0,
            "energy_rank_pct": 0.0,
        })

    # 강세: 절대값 대신 문장 내 에너지 순위로 판정
    if raw_features:
        total = len(raw_features)
        sorted_indices = sorted(
            range(total),
            key=lambda i: raw_features[i]["rms_energy"],
            reverse=True,  # 높은 에너지 = 낮은 순위 번호
        )
        rank_map = {idx: rank + 1 for rank, idx in enumerate(sorted_indices)}
        for i, f in enumerate(raw_features):
            rank = rank_map[i]
            f["energy_rank"]     = rank
            f["energy_rank_pct"] = round(rank / total * 100, 1)  # 상위 X%

    return raw_features


def _format_acoustic_for_prompt(acoustic_features: list) -> str:
    """GPT 프롬프트에 넣을 음향 분석 요약 문자열 생성."""
    total = len(acoustic_features)
    if total == 0:
        return ""

    lines = []
    for f in acoustic_features:
        rank_str    = f"rank {f['energy_rank']}/{total} (top {f['energy_rank_pct']}%)"
        linking_tag = " [LINKED->next]" if f["linking_next"] else ""
        lines.append(
            f"  '{f['word']}': energy={f['rms_energy']:.4f} ({rank_str}), "
            f"dur={f['duration']}s{linking_tag}"
        )
    return "\n".join(lines)


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

TEXT_ANALYSIS_CACHE_TTL = 60 * 60 * 24  # 24시간 (문장 분석은 변하지 않음)

def analyze_communicative_weight(target_text: str) -> dict:
    """
    target_text의 단어별 communicative weight 사전 분석.
    오디오 없이 텍스트만으로 실행 가능.
    동일 문장은 Redis 캐시 반환.
    """
    cache_key = f"text_analysis:{hashlib.md5(target_text.strip().lower().encode()).hexdigest()}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    system_prompt = """You are an English linguistics expert specializing in conversational speech.

Analyze the given sentence for a non-native speaker learning to communicate naturally with native speakers.

For each word, determine:
- communicative_weight: "high" | "medium" | "low"
    high   = core meaning — if unclear, native listener may not understand
    medium = supporting meaning — slight confusion if unclear
    low    = structural/grammatical — reduction or omission sounds natural
- stress_expected: true if a native speaker would naturally stress this word
- reduction_acceptable: true if weakening this word is natural in casual speech
- omission_acceptable: true if omitting this word is natural in casual speech

Also identify:
compound_nouns: list of compound nouns in the sentence.
   Compound nouns always stress the FIRST element (e.g., "SHOW dog", "HIGH school").
   The second element gets lighter stress — do NOT penalize this lighter stress.

RULES:
- Judge from CONVERSATIONAL context, not formal/written context
- Personal pronouns like "I" at the start of a personal statement are often low weight
- Function words (articles, prepositions, auxiliaries) are almost always low weight

Return JSON only."""

    user_prompt = f"""Analyze this sentence for conversational English:
"{target_text}"

Return this exact format:
{{
  "words": [
    {{
      "word": "word",
      "communicative_weight": "high|medium|low",
      "stress_expected": true,
      "reduction_acceptable": false,
      "omission_acceptable": false,
      "note": "one-line reason"
    }}
  ],
  "key_focus_words": ["word1", "word2"],
  "natural_weak_words": ["word1", "word2"],
  "compound_nouns": [
    {{
      "compound": "full compound noun phrase",
      "primary_stress_on": "the first element that takes primary stress",
      "secondary_stress_words": ["other words in the compound with lighter stress"]
    }}
  ]
}}"""

    t = time.time()
    raw = call_ai(system_prompt, user_prompt)
    print(f"[communicative weight 분석] {time.time()-t:.2f}s")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"words": [], "key_focus_words": [], "natural_weak_words": []}

    redis_client.set(cache_key, json.dumps(result), ex=TEXT_ANALYSIS_CACHE_TTL)
    return result


def evaluate_pronunciation(target_text: str, user_audio_path: str, tutor_type: str = "us", on_progress=None):
    """
    전체 흐름: 사용자 오디오 → STT + TTS 병렬 처리 → 발음 평가 → 결과 반환
    on_progress(step, total, status): 진행 상황 콜백 (SSE용)
    """
    def _notify(step, total, status):
        if on_progress:
            on_progress(step, total, status)

    # 1) 텍스트 사전 분석 + TTS + STT 병렬 처리
    _notify(1, 3, "음성 인식 중...")
    t0 = time.time()
    with ThreadPoolExecutor() as executor:
        text_analysis_future = executor.submit(analyze_communicative_weight, target_text)
        tts_future = executor.submit(tts_generate_us, target_text)
        stt_future = executor.submit(stt_whisper, user_audio_path)

        text_analysis = text_analysis_future.result()
        ref_audio, ref_duration = tts_future.result()
        user_transcript, conf_dict, word_timestamps = stt_future.result()
    print(f"[text_analysis+TTS+STT 병렬] {time.time()-t0:.2f}s")

    # 2) 사용자 발화 시간 + 음향 분석
    _notify(2, 3, "음향 분석 중...")
    t1 = time.time()
    user_seg = AudioSegment.from_file(user_audio_path)
    user_duration = len(user_seg) / 1000.0

    acoustic_features = analyze_acoustic_features(user_audio_path, word_timestamps)
    print(f"[발화시간+음향분석] {time.time()-t1:.2f}s")

    # 3) GPT 평가용 데이터 구성
    key_focus         = text_analysis.get("key_focus_words", [])
    natural_weak      = text_analysis.get("natural_weak_words", [])
    word_details      = text_analysis.get("words", [])
    compound_nouns    = text_analysis.get("compound_nouns", [])

    # Monotone 감지: 전체 단어 에너지의 변동계수(CV = std/mean)
    # CV가 낮을수록 에너지가 평탄 → 강세 없는 발화
    energies = [f["rms_energy"] for f in acoustic_features if f["rms_energy"] > 0]
    if len(energies) >= 2:
        energy_mean = float(np.mean(energies))
        energy_cv   = float(np.std(energies) / energy_mean) if energy_mean > 0 else 0.0
        is_monotone = energy_cv < 0.15
    else:
        energy_cv   = 0.0
        is_monotone = False

    # communicative weight 요약 (Step 1 결과)
    weight_parts = []
    for w in word_details:
        word_str   = w.get("word", "")
        weight_str = w.get("communicative_weight", "")
        stress_str = w.get("stress_expected", False)
        red_str    = w.get("reduction_acceptable", False)
        omit_str   = w.get("omission_acceptable", False)
        note_str   = w.get("note", "")
        note_sfx   = f" -> {note_str}" if note_str else ""
        weight_parts.append(
            f"  '{word_str}': weight={weight_str}, stress_expected={stress_str}, "
            f"reduction_ok={red_str}, omission_ok={omit_str}{note_sfx}"
        )
    weight_lines = "\n".join(weight_parts)

    # 복합명사 강세 규칙 요약
    compound_parts = []
    for cn in compound_nouns:
        compound_str  = cn.get("compound", "")
        primary_str   = cn.get("primary_stress_on", "")
        secondary_str = cn.get("secondary_stress_words", [])
        compound_parts.append(
            f"  '{compound_str}': primary stress on '{primary_str}', "
            f"lighter stress (do NOT penalize) on {secondary_str}"
        )
    compound_lines = "\n".join(compound_parts) if compound_parts else "  (none)"

    # 기능어 평균 에너지 계산 → 내용어 강세 위반 사전 계산
    word_weight_map = {
        w.get("word", "").lower().strip(".,!?'"): w.get("communicative_weight", "low")
        for w in word_details
    }

    function_word_energies = [
        f["rms_energy"]
        for f in acoustic_features
        if word_weight_map.get(f["word"].lower().strip(".,!?'"), "low") == "low"
        and f["rms_energy"] > 0
    ]
    func_mean_energy = float(np.mean(function_word_energies)) if function_word_energies else 0.0

    stress_violation_parts = []
    for f in acoustic_features:
        w_key = f["word"].lower().strip(".,!?'")
        weight = word_weight_map.get(w_key, "low")
        if weight in ("high", "medium") and func_mean_energy > 0:
            if f["rms_energy"] < func_mean_energy:
                stress_violation_parts.append(
                    f"  STRESS WEAK: '{f['word']}' (weight={weight}) "
                    f"energy={f['rms_energy']:.4f} < func_mean={func_mean_energy:.4f}"
                )
    stress_violation_lines = (
        "\n".join(stress_violation_parts)
        if stress_violation_parts
        else "  (none — all content words are above function word mean)"
    )

    # 음향 분석 요약 (Step 2 결과)
    acoustic_lines = _format_acoustic_for_prompt(acoustic_features)

    monotone_line = (
        f"  Energy variation (CV): {energy_cv:.2f} — "
        + ("WARNING: delivery is flat/monotone. No word stands out clearly." if is_monotone
           else "OK: energy contrast is present.")
    )

    system_prompt = """You are an encouraging English pronunciation coach.
The learner's goal is NOT to sound like a native speaker - it is to communicate clearly enough that native speakers understand them without effort.
Your job is to help them build confidence while improving, not to nitpick perfection.

You are given three types of data:
1. Communicative weight per word - how important each word is for communication.
2. Stress rules - compound noun stress patterns.
3. Acoustic features - energy RANK per word (rank 1 = highest energy in sentence) and energy variation.

CORE EVALUATION QUESTION:
"Would a native speaker understand this without effort?"
-> YES, clearly    : 90-100
-> YES, mostly     : 85-90
-> SOMEWHAT        : 70-85
-> NO              : 50-70

STRESS IS NOT BINARY. Do not expect dramatic, exaggerated stress.
Evaluate by relative rank among neighboring words, not absolute energy.

STRESS EVALUATION RULES:
1. Content word vs function word:
   - Pre-computed stress violations are provided under [4] below.
   - Any HIGH or MEDIUM weight content word whose energy is below the function word mean energy is flagged as STRESS WEAK.
   - Penalize each flagged word — these are real stress errors, not minor variation.
   - Content words NOT flagged are fine even if some are weaker than adjacent function words (natural in word clusters).
   - Never evaluate function words in isolation.

2. Monotone delivery:
   - If energy variation (CV) is below 0.15, the delivery is flat — no word stands out.
   - Flat delivery makes it harder for native speakers to parse the sentence, even if all words are correct.
   - Penalize monotone delivery and suggest adding contrast between content and function words.

3. Compound nouns:
   - The primary_stress_on word should rank higher than secondary words within the compound.

FEEDBACK TONE:
- Frame improvements as "would sound even more natural if..." not "this was wrong".
- Always find something positive to say first.
- Keep improvements to 1-2 points maximum. Do not overwhelm.

Return JSON only."""

    user_prompt = (
        "Target phrase: {target_text}\n"
        "Learner transcript: {user_transcript}\n"
        "Learner duration: {user_duration}s / Reference duration: {ref_duration}s\n\n"
        "[1] Communicative weight:\n{weight_lines}\n\n"
        "Key words that MUST be clear: {key_focus}\n"
        "Words where reduction/omission is NATURAL: {natural_weak}\n\n"
        "[2] Stress rules:\n"
        "  Compound noun stress patterns:\n{compound_lines}\n\n"
        "[3] Acoustic features (measured from audio):\n"
        "{monotone_line}\n"
        "{acoustic_lines}\n\n"
        "[4] Pre-computed stress violations (content word energy < function word mean={func_mean_energy:.4f}):\n"
        "{stress_violation_lines}\n\n"
        "Evaluate and return:\n"
        "{{\n"
        '  "score": 0-100,\n'
        '  "strengths": ["specific observations referencing actual words"],\n'
        '  "improvements": ["specific actionable feedback referencing actual words"],\n'
        '  "rhythm_feedback": "one sentence on stress pattern and linking quality",\n'
        '  "feedback": []\n'
        "}}"
    ).format(
        target_text=target_text,
        user_transcript=user_transcript,
        user_duration=f"{user_duration:.2f}",
        ref_duration=f"{ref_duration:.2f}",
        weight_lines=weight_lines,
        key_focus=key_focus,
        natural_weak=natural_weak,
        compound_lines=compound_lines,
        monotone_line=monotone_line,
        acoustic_lines=acoustic_lines if acoustic_lines else "  (no timestamp data available)",
        func_mean_energy=func_mean_energy,
        stress_violation_lines=stress_violation_lines,
    )

    # AI 호출
    _notify(3, 3, "AI 평가 중...")
    t2 = time.time()
    ai_response = call_ai(system_prompt, user_prompt)
    print(f"[GPT 평가 호출] {time.time()-t2:.2f}s")

    try:
        result = json.loads(ai_response)
    except json.JSONDecodeError:
        result = {
            "score": 0,
            "feedback": ["AI 응답 파싱 실패"],
            "user_transcript": user_transcript,
            "target_text": target_text
        }

    return {
        "score": result.get("score", 0),
        "feedback": result.get("feedback", []),
        "strengths": result.get("strengths", []),
        "improvements": result.get("improvements", []),
        "rhythm_feedback": result.get("rhythm_feedback", ""),
        "reference_tts": ref_audio,
        "user_transcript": user_transcript,
        "user_duration": user_duration,
        "ref_duration": ref_duration,
    }
