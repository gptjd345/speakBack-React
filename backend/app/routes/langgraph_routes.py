#routes.py
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from pydantic import BaseModel
from app.langgraph_config.graph_runner import run_pipeline
from app.core.dependencies import get_current_user
from app.core.s3 import generate_presigned_upload_url, download_file_bytes, delete_file


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
    """
    프론트가 S3에 직접 업로드할 수 있는 Presigned PUT URL 반환
    """
    result = generate_presigned_upload_url(
        original_filename=body.filename,
        content_type=body.content_type,
    )
    return result

# ─── 2단계: s3_key로 분석 실행 ───────────────────────────────────
@router.post("/process")
async def process_audio(
    s3_key: str = Form(...),
    user_name: str = Form(...), 
    target_text: str = Form(...),
    original_filename: str = Form(default="audio.wav"),
    current_user: dict = Depends(get_current_user),
):
    """
    S3에 업로드된 파일을 가져와 분석 실행
    분석 완료 후 S3 파일 즉시 삭제
    """
    # S3에서 파일 다운로드
    try:
        audio_bytes = download_file_bytes(s3_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"S3 파일 조회 실패: {str(e)}")
    
    # 분석 실행
    try:
        result = run_pipeline(
            audio_file=audio_bytes,
            user_name=user_name,
            target_text=target_text,
            user_id=current_user["id"],
            original_filename=original_filename,
        )
    finally:
        # 성공/실패 관계없이 S3 파일 삭제
        delete_file(s3_key)

    return result
