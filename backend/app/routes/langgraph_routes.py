#routes.py
from fastapi import APIRouter, UploadFile, File, Form, Depends
from app.langgraph_config.graph_runner import run_pipeline
from app.core.dependencies import get_current_user

router = APIRouter()

@router.post("/process")
async def process_audio(
    audio: UploadFile = File(...), 
    user_name: str = Form(...), 
    target_text: str = Form(...),
    current_user: dict = Depends(get_current_user),
):
    try:
        audio_bytes = await audio.read()
        # run_pipeline에 필요한 인자 전달
        result = run_pipeline(
            audio_bytes, 
            user_name, 
            target_text, 
            user_id=current_user["id"]
        )
        return result
    except Exception as e:
        return {"error": str(e)}
