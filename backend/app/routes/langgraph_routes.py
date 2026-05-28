# routes.py
from fastapi import APIRouter, Form, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.core.dependencies import get_current_user
from app.core.s3 import generate_presigned_upload_url, download_file_bytes, delete_file
from app.services.analysis_result import save_analysis_result
import asyncio, json, tempfile, os
from concurrent.futures import ThreadPoolExecutor
from app.agents.suggest_graph import run_suggest

_analysis_executor = ThreadPoolExecutor(max_workers=4)
from app.services.audio import tts_generate_us
from app.services.evaluation import analyze_communicative_weight, evaluate_pronunciation
from app.services.validation import is_english
from app.db.database import SessionLocal
from app.db.models import SessionHistory
import subprocess, base64

router = APIRouter()

# ─── 1단계: Presigned Upload URL 발급 ────────────────────────────
class PresignedUrlRequest(BaseModel):
    filename: str
    content_type: str = "audio/wav"


class PresignedUrlResponse(BaseModel):
    upload_url: str
    s3_key: str


@router.post("/upload-url", response_model=PresignedUrlResponse)
def get_upload_url(
    body: PresignedUrlRequest,
    current_user: dict = Depends(get_current_user),
):
    result = generate_presigned_upload_url(
        original_filename=body.filename,
        content_type=body.content_type,
    )
    return result


# ─── Sentence Suggestion (LangGraph tool-calling) ────────────────
class SuggestRequest(BaseModel):
    target_text: str


@router.post("/suggest")
def suggest_sentences(
    body: SuggestRequest,
    current_user: dict = Depends(get_current_user),
):
    
    return run_suggest(body.target_text)


# ─── 1.5단계: target text 사전 분석 (캐시 워밍) ─────────────────
class PrepareRequest(BaseModel):
    target_text: str


@router.post("/prepare")
def prepare_analysis(
    body: PrepareRequest,
    current_user: dict = Depends(get_current_user),
):
    text = body.target_text.strip()
    if len(text) < 10:
        raise HTTPException(status_code=400, detail="Sentence is too short. Please enter at least 10 characters.")
    if len(text) > 500:
        raise HTTPException(status_code=400, detail="Sentence is too long. Please keep it under 500 characters.")
    if not is_english(text):
        raise HTTPException(status_code=400, detail="Please enter an English sentence.")

    with ThreadPoolExecutor() as executor:
        executor.submit(analyze_communicative_weight, body.target_text)
        executor.submit(tts_generate_us, body.target_text)

    return {"status": "ready"}


# ─── SSE: 분석 진행 상황 스트리밍 ─────────────────────────────────
@router.post("/process/stream")
async def process_audio_stream(
    s3_key: str = Form(...),
    user_name: str = Form(...),
    target_text: str = Form(...),
    original_filename: str = Form(default="audio.wav"),
    current_user: dict = Depends(get_current_user),
):
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _run():
        tmp_src = tmp_dst = None
        try:
            
            # target_text 길이 및 영어 검증 (S3/STT/GPT 호출 전 차단)
            text = target_text.strip()
            if len(text) < 10:
                loop.call_soon_threadsafe(queue.put_nowait, {"error": "Sentence is too short. Please enter at least 10 characters."})
                return
            if len(text) > 500:
                loop.call_soon_threadsafe(queue.put_nowait, {"error": "Sentence is too long. Please keep it under 500 characters."})
                return
            if not is_english(text):
                loop.call_soon_threadsafe(queue.put_nowait, {"error": "Please enter an English sentence."})
                return

            # S3 다운로드 + ffmpeg 변환
            loop.call_soon_threadsafe(queue.put_nowait, {"step": 0, "total": 3, "status": "오디오 다운로드 중..."})
            audio_bytes = download_file_bytes(s3_key)

            # result[0]은 버리고 result[1] 확장자만 ext변수에 담아서 사용
            _, ext = os.path.splitext(original_filename)
            ext = ext.lower() if ext else ".bin"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
                f.write(audio_bytes)
                tmp_src = f.name
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
                tmp_dst = f.name
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_src, "-ar", "16000", "-ac", "1", "-f", "wav", tmp_dst],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            )

            # 이전 시도 acoustic_features 조회 (동일 target_text + user)
            prev_features = None
            db = SessionLocal()
            try:
                prev_session = (
                    db.query(SessionHistory)
                    .filter(
                        SessionHistory.user_id == current_user["id"],
                        SessionHistory.target_text == target_text,
                        SessionHistory.acoustic_features.isnot(None),
                    )
                    .order_by(SessionHistory.created_at.desc())
                    .first()
                )
                if prev_session:
                    prev_features = prev_session.acoustic_features
            finally:
                db.close()

            # 발음 평가
            def on_progress(step, total, status):
                loop.call_soon_threadsafe(queue.put_nowait, {"step": step, "total": total, "status": status})

            result = evaluate_pronunciation(target_text, tmp_dst, "us", on_progress=on_progress, prev_features=prev_features)

            # DB 저장
            save_analysis_result(
                user_id=current_user["id"],
                target_text=target_text,
                user_name=user_name,
                user_transcript=result.get("user_transcript"),
                score=result.get("score"),
                strengths=result.get("strengths", []),
                improvements=result.get("improvements", []),
                rhythm_feedback=result.get("rhythm_feedback"),
                acoustic_features=result.get("compact_acoustic"),
            )

            # 최종 결과 전송
            serializable = {k: v for k, v in result.items() if k not in ("reference_tts", "compact_acoustic")}
            serializable["us_audio"] = base64.b64encode(result.get("reference_tts") or b"").decode()
            loop.call_soon_threadsafe(queue.put_nowait, {"done": True, "result": serializable})

        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, {"error": str(e)})
        finally:
            delete_file(s3_key)
            for path in [tmp_src, tmp_dst]:
                if path and os.path.exists(path):
                    os.remove(path)

    async def generate():
        _analysis_executor.submit(_run)
        while True:
            msg = await queue.get()
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            if msg.get("done") or msg.get("error"):
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
