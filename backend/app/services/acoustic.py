import numpy as np

from app.services.audio import librosa_warmup_done


# ─── Acoustic feature extraction ─────────────────────────────────────────────

def analyze_acoustic_features(audio_path: str, word_timestamps: list) -> list:
    """
    단어별 음향 특징 추출 (librosa + Whisper 타임스탬프).

    Returns list of dicts:
        word, start, end, duration,
        rms_energy, mean_pitch,
        linking_next,
        energy_rank (1 = 가장 강함), energy_rank_pct
    """
    import librosa

    if not word_timestamps:
        return []

    # warmup 완료 대기 (최대 30초)
    if not librosa_warmup_done.wait(timeout=30):
        print("[analyze_acoustic_features] librosa warmup 타임아웃 — 그냥 진행")

    y, sr = librosa.load(audio_path, sr=16000)

    raw_features = []
    for i, w in enumerate(word_timestamps):
        start_s = max(0.0, w["start"])
        end_s = min(len(y) / sr, w["end"])
        if end_s <= start_s:
            continue

        seg = y[int(start_s * sr): int(end_s * sr)]
        duration = end_s - start_s

        rms = float(np.sqrt(np.mean(seg ** 2))) if len(seg) > 0 else 0.0

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

        gap = word_timestamps[i + 1]["start"] - w["end"] if i < len(word_timestamps) - 1 else 1.0
        linking_next = gap < 0.05

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

    # 문장 내 에너지 순위 계산 (절대값 대신 상대 순위로 강세 판정)
    if raw_features:
        total = len(raw_features)
        sorted_indices = sorted(range(total), key=lambda i: raw_features[i]["rms_energy"], reverse=True)
        rank_map = {idx: rank + 1 for rank, idx in enumerate(sorted_indices)}
        for i, f in enumerate(raw_features):
            rank = rank_map[i]
            f["energy_rank"] = rank
            f["energy_rank_pct"] = round(rank / total * 100, 1)

    return raw_features


# ─── Compact representation for DB storage ───────────────────────────────────

def compact_acoustic_features(acoustic_features: list, energy_cv: float, is_monotone: bool) -> dict:
    return {
        "energy_cv": round(energy_cv, 4),
        "is_monotone": is_monotone,
        "words": [
            {
                "word": f["word"],
                "rms_energy": round(f["rms_energy"], 6),
                "energy_rank": f["energy_rank"],
                "duration": f["duration"],
            }
            for f in acoustic_features
        ],
    }


# ─── Session-to-session diff ─────────────────────────────────────────────────

def compute_diff(prev: dict, curr: dict) -> dict:
    """이전 시도와 현재 시도의 음향 피처 비교."""
    cv_delta = round(curr.get("energy_cv", 0.0) - prev.get("energy_cv", 0.0), 4)

    prev_words = {w["word"].lower(): w for w in prev.get("words", [])}
    curr_words = {w["word"].lower(): w for w in curr.get("words", [])}

    stress_changes = []
    for word, cw in curr_words.items():
        if word in prev_words:
            delta = prev_words[word]["energy_rank"] - cw["energy_rank"]  # 양수 = 더 강하게
            if abs(delta) >= 2:
                stress_changes.append({
                    "word": word,
                    "prev_rank": prev_words[word]["energy_rank"],
                    "curr_rank": cw["energy_rank"],
                    "improved": delta > 0,
                })

    return {
        "energy_cv_delta": cv_delta,
        "energy_cv_improved": cv_delta > 0.02,
        "was_monotone": prev.get("is_monotone", False),
        "now_monotone": curr.get("is_monotone", False),
        "monotone_improved": prev.get("is_monotone", False) and not curr.get("is_monotone", False),
        "stress_rank_changes": stress_changes,
    }


# ─── Prompt formatting ───────────────────────────────────────────────────────

def format_acoustic_for_prompt(acoustic_features: list) -> str:
    total = len(acoustic_features)
    if total == 0:
        return ""
    lines = []
    for f in acoustic_features:
        rank_str = f"rank {f['energy_rank']}/{total} (top {f['energy_rank_pct']}%)"
        linking_tag = " [LINKED->next]" if f["linking_next"] else ""
        lines.append(
            f"  '{f['word']}': energy={f['rms_energy']:.4f} ({rank_str}), "
            f"dur={f['duration']}s{linking_tag}"
        )
    return "\n".join(lines)
