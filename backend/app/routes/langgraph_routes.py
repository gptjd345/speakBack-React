#routes.py
from app.graph_runner_wrapper import run_pipeline

@router.post("/process-audio")
async def process_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = run_pipeline(audio_bytes, "username", "target_text")
    return result
