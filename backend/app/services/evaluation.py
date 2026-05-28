import hashlib
import json
import time
import numpy as np

from concurrent.futures import ThreadPoolExecutor
from pydub import AudioSegment

from app.core.redis import redis_client
from app.services.audio import get_client, stt_whisper, tts_generate_us
from app.services.validation import is_english
from app.services.acoustic import (
    analyze_acoustic_features,
    compact_acoustic_features,
    compute_diff,
    format_acoustic_for_prompt,
)

TEXT_ANALYSIS_CACHE_TTL = 60 * 60 * 24  # 24시간


# ─── GPT wrapper ─────────────────────────────────────────────────────────────

def call_ai(system_prompt: str, user_prompt: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


# ─── Communicative weight analysis ───────────────────────────────────────────

def analyze_communicative_weight(target_text: str) -> dict:
    """
    target_text의 단어별 communicative weight 사전 분석.
    오디오 없이 텍스트만으로 실행 가능. 결과는 Redis 캐시.
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


# ─── Pronunciation evaluation ─────────────────────────────────────────────────

EVAL_SYSTEM_PROMPT = """You are an encouraging English pronunciation coach.
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

# LLM 프롬프트 품질을 높이기 위해 diff 정보를 구조화해서 전달
def _build_diff_section(diff: dict, compact_acoustic: dict) -> str:
    """
    이전 발화와 현재 발화를 비교하여
    LLM 프롬프트용 문자열을 생성한다.

    CV : Coefficient of Variation(변동계수)
    목소리가 원래 큰사람일 경우 평균에너지가 크기 때문에 분산도 커짐 -> 에너지값이 평균대비 얼마나 차이가 있나를 기준으로 판단. 
    CV= σ​/μ
    σ: 표준편차 (에너지 분산 정도)
    μ: 평균 (평균 에너지)

    Args:
        diff: 두 발화 간 차이 정보
        compact_acoustic: 현재 발화의 acoustic feature

    Returns:
        비교 결과가 포함된 문자열

    """
    # 에너지 CV 변화량을 "+0.123" / "-0.123" 형태로 표현
    cv_arrow = f"{diff['energy_cv_delta']:+.3f}"

    # CV 개선 여부에 따른 설명 문구
    # CV가 증가하면 보통 강세 대비가 살아났다고 판단
    cv_note = "improved — more contrast" if diff["energy_cv_improved"] else "similar or less contrast"
    
    # monotone 개선 시 강조 메시지 추가
    # (단조롭던 발화 → 강세 대비가 생긴 경우)
    monotone_note = (
        " Previously flat/monotone → now showing contrast — great improvement!"
        if diff["monotone_improved"] else ""
    )
    # 단어별 강세 순위 변화 요약 생성
    # rank 변화가 의미 있는 경우만 포함
    rank_lines = []
    for ch in diff["stress_rank_changes"]:
        # improved=True -> 더 강세가 강조된 방향 
        direction = "stressed more" if ch["improved"] else "stressed less"

        # 예: 'want': rank 3 -> 1 (stressed more)
        rank_lines.append(f"    '{ch['word']}': rank {ch['prev_rank']} → {ch['curr_rank']} ({direction})")
    
    # 변화가 없으면 fallback 메시지
    rank_summary = "\n".join(rank_lines) if rank_lines else "    (no significant rank shifts)"

    # 이전 CV 값 복원 (현재 - delta)
    prev_cv_val = round(compact_acoustic["energy_cv"] - diff["energy_cv_delta"], 3)
    return (
        f"\n[5] Comparison with previous attempt on same sentence:\n"

        # 리듬 변화(에너지분산) 설명
        f"  Energy variation (CV): {prev_cv_val:.3f} → {compact_acoustic['energy_cv']:.3f}"
        f" ({cv_arrow}) — {cv_note}. {monotone_note}\n"

        # 강세 변화 요약
        f"  Stress rank changes (≥2 positions):\n{rank_summary}\n"

        # LLM에게 개선 포인트를 반드시 언급하도록 유도
        f"  Acknowledge the change explicitly in strengths or improvements.\n"
    )


def evaluate_pronunciation(
    target_text: str,
    user_audio_path: str,
    tutor_type: str = "us",
    on_progress=None,
    prev_features: dict | None = None,
):
    """
    오디오 → STT/TTS 병렬 → acoustic 분석 → GPT 평가 → 결과 반환.
    on_progress(step, total, status): SSE 진행 상황 콜백.
    prev_features: 이전 시도의 compact_acoustic (동일 문장 재시도 비교용).
    """
    def _notify(step, total, status):
        if on_progress:
            on_progress(step, total, status)

    # 1) STT + TTS + communicative weight 병렬
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

    # transcript 영어 검증 (acoustic + GPT 평가 비용 차단)
    if user_transcript and not is_english(user_transcript):
        print(f"[비영어 발화 감지] transcript='{user_transcript[:60]}' → 분석 중단")
        raise ValueError("Non-English speech detected. Please speak in English.")

    # 2) acoustic 분석
    _notify(2, 3, "음향 분석 중...")
    t1 = time.time()
    user_duration = len(AudioSegment.from_file(user_audio_path)) / 1000.0
    acoustic_features = analyze_acoustic_features(user_audio_path, word_timestamps)
    print(f"[발화시간+음향분석] {time.time()-t1:.2f}s")

    # 3) 프롬프트 데이터 구성
    key_focus = text_analysis.get("key_focus_words", [])
    natural_weak = text_analysis.get("natural_weak_words", [])
    word_details = text_analysis.get("words", [])
    compound_nouns = text_analysis.get("compound_nouns", [])

    energies = [f["rms_energy"] for f in acoustic_features if f["rms_energy"] > 0]
    if len(energies) >= 2:
        energy_mean = float(np.mean(energies))
        energy_cv = float(np.std(energies) / energy_mean) if energy_mean > 0 else 0.0
        is_monotone = energy_cv < 0.15
    else:
        energy_cv = 0.0
        is_monotone = False

    compact_acoustic = compact_acoustic_features(acoustic_features, energy_cv, is_monotone)
    diff = compute_diff(prev_features, compact_acoustic) if prev_features else None

    weight_lines = "\n".join(
        f"  '{w.get('word', '')}': weight={w.get('communicative_weight', '')}, "
        f"stress_expected={w.get('stress_expected', False)}, "
        f"reduction_ok={w.get('reduction_acceptable', False)}, "
        f"omission_ok={w.get('omission_acceptable', False)}"
        + (f" -> {w['note']}" if w.get("note") else "")
        for w in word_details
    )

    compound_lines = "\n".join(
        f"  '{cn.get('compound', '')}': primary stress on '{cn.get('primary_stress_on', '')}', "
        f"lighter stress (do NOT penalize) on {cn.get('secondary_stress_words', [])}"
        for cn in compound_nouns
    ) or "  (none)"

    word_weight_map = {
        w.get("word", "").lower().strip(".,!?'"): w.get("communicative_weight", "low")
        for w in word_details
    }
    function_energies = [
        f["rms_energy"]
        for f in acoustic_features
        if word_weight_map.get(f["word"].lower().strip(".,!?'"), "low") == "low"
        and f["rms_energy"] > 0
    ]
    func_mean_energy = float(np.mean(function_energies)) if function_energies else 0.0

    _STRIP = ".,!?'"
    stress_violation_lines = "\n".join(
        f"  STRESS WEAK: '{f['word']}' (weight={word_weight_map.get(f['word'].lower().strip(_STRIP), 'low')}) "
        f"energy={f['rms_energy']:.4f} < func_mean={func_mean_energy:.4f}"
        for f in acoustic_features
        if word_weight_map.get(f["word"].lower().strip(_STRIP), "low") in ("high", "medium")
        and func_mean_energy > 0
        and f["rms_energy"] < func_mean_energy
    ) or "  (none — all content words are above function word mean)"

    monotone_line = (
        f"  Energy variation (CV): {energy_cv:.2f} — "
        + ("WARNING: delivery is flat/monotone. No word stands out clearly." if is_monotone
           else "OK: energy contrast is present.")
    )

    acoustic_lines = format_acoustic_for_prompt(acoustic_features)
    diff_section = _build_diff_section(diff, compact_acoustic) if diff else ""

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
        "{stress_violation_lines}"
        "{diff_section}\n"
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
        acoustic_lines=acoustic_lines or "  (no timestamp data available)",
        func_mean_energy=func_mean_energy,
        stress_violation_lines=stress_violation_lines,
        diff_section=diff_section,
    )

    # 4) GPT 평가
    _notify(3, 3, "AI 평가 중...")
    t2 = time.time()
    ai_response = call_ai(EVAL_SYSTEM_PROMPT, user_prompt)
    print(f"[GPT 평가 호출] {time.time()-t2:.2f}s")

    try:
        result = json.loads(ai_response)
    except json.JSONDecodeError:
        result = {"score": 0, "feedback": ["AI 응답 파싱 실패"]}

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
        "compact_acoustic": compact_acoustic,
    }
