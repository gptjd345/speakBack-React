#routes.py
from fastapi import APIRouter, UploadFile, File, Form
from app.langgraph_config.graph_runner import run_pipeline

router = APIRouter()

@router.post("/process")
async def process_audio(
    audio: UploadFile = File(...), 
    user_name: str = Form(...), 
    target_text: str = Form(...)
):
    try:
        audio_bytes = await audio.read()
        # run_pipeline에 필요한 인자 전달
        result = run_pipeline(audio_bytes, user_name, target_text)
        return result
    except Exception as e:
        return {"error": str(e)}
