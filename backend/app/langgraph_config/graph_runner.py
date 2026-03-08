# 그래프 실행부
# langgraph_config/graph_runner.py
from .builder import build_graph
from .store import global_store
import io
import base64

# 간단한 state 구조 (필요시 MessagesState 써도 됨)
class PipelineState(dict):
    pass

def run_pipeline(audio_file, user_name: str, target_text: str, user_id: int = None, original_filename: str = "audio.wav"):
    try : 
        state = {
            "user_name": user_name,
            "target_text": target_text,
        }
        print("DEBUG inputs:", state)

        compiled_graph = build_graph()
        global_store.audio_file = io.BytesIO(audio_file)  # state가 아닌 store에 저장
        global_store.audio_file.seek(0)  # Whisper 등에서 읽기 위해 포인터 처음으로
        global_store.target_text = target_text
        global_store.original_filename = original_filename  # 확장자 감지용
        global_store.user_id = user_id       # db_save_node 에서 사용
        global_store.user_name = user_name
        print("DEBUG: run_graph 시작")
        
        compiled_graph.invoke(state)

        # 👇 화면단으로 전달할 데이터 구조 확정
        result = {
            "user_name": user_name,
            "target_text": target_text,
            "us_audio": base64.b64encode(getattr(global_store, "tts_us_audio", None)),  # US 튜터 TTS 음성
            "uk_audio": base64.b64encode(getattr(global_store, "tts_uk_audio", None)),  # UK 튜터 TTS 음성
            "us_feedback": getattr(global_store, "us_feedback", ""), # UK 튜터 피드백
            "uk_feedback": getattr(global_store, "uk_feedback", ""), # UK 튜터 피드백
            "score": getattr(global_store, "score", ""), # 점수
            "user_duration": getattr(global_store, "user_duration", ""), # 청크들
            "us_ref_duration": getattr(global_store, "us_ref_duration", ""), # 청크들

            "strengths": getattr(global_store, "strengths", []),             # 강점
            "improvements": getattr(global_store, "improvements", []),       # 개선점
            "rhythm_feedback": getattr(global_store, "rhythm_feedback", ""), # 리듬 피드백

        }
        
        return result
    except Exception as e:
        print("DEBUG run_graph error:", e)
        return {"error": str(e)}
