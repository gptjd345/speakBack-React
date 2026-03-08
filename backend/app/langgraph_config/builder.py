# 그래프 정의부
# langgraph_config/builder.py
from langgraph.graph import StateGraph, START, END
from .store import global_store
import tempfile
import soundfile as sf
import io
import os
import torch

from .pronunciation_module import evaluate_pronunciation

from langsmith import trace
from langsmith.run_helpers import traceable

from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

# 간단한 state 구조 (필요시 MessagesState 써도 됨)
class PipelineState(dict):
    @traceable
    def __merge__(self, other):
        merged = PipelineState(self)
        decisions = {}
        for k, v in other.items():
            if k in merged:
                decisions[k] = {"before": merged[k], "after": v, "action": "overwrite"}
            else:
                decisions[k] = {"before": None, "after": v, "action": "add"}
            merged[k] = v
        return {"decisions": decisions, "merged_state": dict(merged)}

# ---------------- 노드 정의 ----------------
def audio_store_node(state):
    # 사용자 음성 데이터를 numpy + tensor 로 변환하고 Whisper STT 수행
    audioFile = global_store.audio_file
    # mp3 / m4a / wav / webm 등 브라우저·업로드 포맷 모두 대응
    if audioFile is None:
        state["err_txt"] = "[audio store ERROR] No audio data found"
        return state
    
    try:
        # 1) 원본 파일을 확장자 포함 임시파일로 저장
        #    업로드 파일명에서 확장자를 가져오고, 없으면 .bin 으로 fallback
        original_filename = getattr(global_store, "original_filename", "") or ""
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower() if ext else ".bin"

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_src:
            tmp_src.write(audioFile.read())
            src_path = tmp_src.name

        # 2) ffmpeg 로 16kHz mono wav 변환 → Whisper / pydub 입력 통일
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_dst:
            dst_path = tmp_dst.name

        # ----------------------------------------------------
        # Audio data preprocessing (ffmpeg → 16kHz mono wav)
        # 다양한 디바이스/브라우저 녹음 포맷을 통일하여 STT 정확도 안정화
        # ----------------------------------------------------
        import subprocess
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", src_path,
                "-ar", "16000",   # 16kHz
                "-ac", "1",       # mono
                "-f", "wav",
                dst_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        # 원본 임시파일 정리
        os.remove(src_path)

        global_store.tmp_path = dst_path

    except subprocess.CalledProcessError as e:
        state["err_txt"] = f"[audio store ERROR] ffmpeg 변환 실패: {e.stderr.decode()}"
        return state
    except Exception as e:
        state["err_txt"] = f"[audio store ERROR] {e}"
        return state

    return state

def us_tutor_node(state: PipelineState):
    """미국 튜터 피드백 + 음성 생성"""
    target_text = global_store.target_text

    result = evaluate_pronunciation(
        target_text, 
        global_store.tmp_path,     # 사용자 임시 음성파일경로
        "us"                       # tutor type
    )

    # 디버그: 최종 결과 확인
    print("=== US Tutor Final Result ===")
    print("Score:\n", result["score"])
    print("Feedback:\n", result["feedback"])
    print("TTS Audio Bytes Length:", len(result["reference_tts"]))
    print("strengths: ",result["strengths"])
    print("improvements: ",result["improvements"])
    print("rhythm_feedback: ",result["rhythm_feedback"])
    
    global_store.score = result["score"]
    global_store.us_feedback = result["feedback"]
    global_store.tts_us_audio = result["reference_tts"]
    global_store.user_transcript = result["user_transcript"]
    global_store.user_duration = result["user_duration"]
    global_store.us_ref_duration = result["ref_duration"]

    global_store.strengths = result["strengths"]
    global_store.improvements = result["improvements"]
    global_store.rhythm_feedback = result["rhythm_feedback"]

    return state

def uk_tutor_node(state: PipelineState):
    """영국 튜터 피드백"""

    # 실제 AI 평가 로직은 여기서 audio_np 기반
    global_store.tts_uk_comment = "[UK Tutor] Try softer vowels."
    global_store.tts_uk_audio = b"fake-uk-audio-bytes"

    print("=== [uk_tutor_node] Final State Snapshot ===")
    """
    for k, v in state.items():
        if isinstance(v, (bytes, bytearray)):
            print(f"{k}: <{len(v)} bytes>")
        else:
            print(f"{k}: {v}")
    """

    return state

def tts_node(state: PipelineState):
    # TTS는 이미 us/uk tutor에서 만든 걸 합쳐서 처리 가능
    state["tts_done"] = True

    print("=== [tts_node] Final State Snapshot ===")
          
    return state

def db_save_node(state: PipelineState):
    """분석 결과를 session_history 테이블에 저장"""
    from app.db.database import SessionLocal
    from app.db.models import SessionHistory

    db = SessionLocal()
    try:
        record = SessionHistory(
            user_id=global_store.user_id,
            target_text=global_store.target_text or "",
            user_transcript=getattr(global_store, "user_transcript", None),
            score=getattr(global_store, "score", None),
            strengths=getattr(global_store, "strengths", []),
            improvements=getattr(global_store, "improvements", []),
            rhythm_feedback=getattr(global_store, "rhythm_feedback", None),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        global_store.saved_session_id = record.id
        print(f"=== [db_save_node] session_history 저장 완료 id={record.id} ===")
    except Exception as e:
        db.rollback()
        print(f"=== [db_save_node] 저장 실패: {e} ===")
    finally:
        db.close()

    return state

# ---------------- 그래프 빌더 ----------------
def build_graph():
    graph = StateGraph(PipelineState)

    graph.add_node("audio_store", audio_store_node)
    graph.add_node("us_tutor", us_tutor_node)
    graph.add_node("uk_tutor", uk_tutor_node)
    graph.add_node("tts", tts_node)
    graph.add_node("db", db_save_node)

    graph.add_edge(START, "audio_store")      # 입력 → 오디오 저장/변환
    graph.add_edge("audio_store", "us_tutor")  # 오디오 → STT
    graph.add_edge("audio_store", "uk_tutor")
    graph.add_edge("us_tutor", "tts")
    graph.add_edge("uk_tutor", "tts")
    graph.add_edge("tts", "db")
    graph.add_edge("db", END)

    # CompiledStateGraph.invoke(state) 내부에서 새로운 상태 객체를 만들거나 덮어쓰는 과정이 있어서 바깥으로 제대로 전달되지 않는 거예요
    # 컴파일을 여기서 안하기로함
    return graph.compile()
