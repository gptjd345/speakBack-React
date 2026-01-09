# app/core/tts_manager.py
from TTS.api import TTS

_tts_us_model = None

def get_us_tts():
    global _tts_us_model
    if _tts_us_model is None:
        _tts_us_model = TTS(
            model_name="tts_models/en/ljspeech/tacotron2-DDC",
            progress_bar=False,
            gpu=False
        )
    return _tts_us_model
