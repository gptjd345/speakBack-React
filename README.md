# SpeakBack

English pronunciation coaching web application powered by Whisper STT, OpenAI TTS, and GPT-4o-mini.

---

## Tech Stack

| | |
|---|---|
| **Frontend** | React |
| **Backend** | FastAPI, Uvicorn |
| **AI** | Whisper API (STT), OpenAI TTS, GPT-4o-mini |
| **Infra** | Docker Compose, PostgreSQL, Redis, AWS S3 |
| **Auth** | JWT (Access / Refresh Token) |
| **Pipeline** | LangGraph |

---

## Architecture

```
[React]
  │  Authorization: Bearer {access_token}
  │  X-Refresh-Token: {refresh_token}
  ▼
[FastAPI]
  ├─ /auth/login        → issue access + refresh token
  ├─ /auth/me           → verify token_version via Redis (no DB query)
  ├─ /auth/refresh      → Refresh Token Rotation
  └─ /auth/logout       → revoke refresh token
  │
  ├─ [PostgreSQL]       refresh_tokens, users, session_history tables
  └─ [Redis]            token_version cache, TTS audio cache (6h TTL)

[File Upload Flow]
  React
    → POST /api/analyze/upload-url  → FastAPI generates S3 Presigned URL
    → PUT {presigned_url}           → React uploads directly to S3 (bypass FastAPI)
    → POST /api/analyze/process     → FastAPI downloads from S3 → pipeline → delete S3 file

[Pronunciation Pipeline]
  FastAPI
    → S3 download
    → ffmpeg (normalize to 16kHz mono wav)
    → Whisper API (STT) + OpenAI TTS (parallel)
    → GPT-4o-mini (scoring + feedback)
    → Save to session_history (DB)
    → Response

[Session History]
  GET /api/history/         → list (limit 20)
  GET /api/history/{id}     → detail
```

---

## Auth Flow

**Login**
- Issue access token (30m) + refresh token (14d)
- Cache `token_version` in Redis

**`/me`**
- Verify JWT signature
- Compare `token_version` in payload vs Redis — no DB query

**`/refresh` — Refresh Token Rotation**
- Revoke current refresh token, issue new one
- If reuse detected → revoke all sessions + increment `token_version`

**Logout**
- Revoke refresh token in DB

---

## S3 File Upload

Audio files are uploaded directly to S3 via Presigned URL, bypassing the FastAPI server.

- Max file size: **25MB**
- Files are stored under `uploads/` prefix
- S3 Lifecycle rule automatically deletes files after **24 hours**
- FastAPI deletes the file immediately after analysis completes

**Required AWS setup**
1. S3 bucket with CORS configured for `PUT` from your frontend origin
2. S3 Lifecycle rule: `uploads/` prefix → expire after 1 day
3. IAM user with minimal permissions (`s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `uploads/*`)

---

## Getting Started

**Requirements**
- Docker, Docker Compose
- OpenAI API Key
- AWS account (S3 bucket + IAM user)

**1. Clone**
```bash
git clone https://github.com/gptjd345/speakBack-React.git
cd speakBack-React
```

**2. Configure environment**
```bash
cp .env.example .env
# fill in the following:
```

`backend/.env`
```env
OPENAI_API_KEY=
JWT_SECRET_KEY=
DATABASE_URL=

AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=
```

**3. Run**
```bash
docker compose up --build
```

**4. DB migration**
```bash
docker compose exec fastapi alembic upgrade head
```

Frontend: http://localhost:3000  
Backend: http://localhost:8000/docs

---

## Project Structure

```
speakBack-React/
├── frontend/          # React
└── backend/
    ├── app/
    │   ├── routes/    # auth, analyze, history
    │   ├── core/      # security, redis, s3
    │   ├── db/        # models (users, refresh_tokens, session_history)
    │   └── langgraph/ # STT → TTS → GPT pipeline
    └── alembic/       # DB migrations
```