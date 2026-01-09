FROM --platform=linux/amd64 python:3.11-slim

WORKDIR /app

# 필수 OS 패키지 설치 (ffmpeg 포함)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# TTS 모델 미리 다운로드
RUN python - <<EOF
from TTS.api import TTS
TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False, gpu=False)
EOF

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
