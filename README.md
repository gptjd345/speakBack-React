# SpeakBack

English pronunciation coaching web application powered by Whisper STT, OpenAI TTS, and GPT-4o-mini.

---

## Tech Stack

| | |
|---|---|
| **Frontend** | React |
| **Backend** | FastAPI, Uvicorn |
| **AI** | Whisper API (STT), OpenAI TTS, GPT-4o-mini |
| **Infra** | Docker Compose, PostgreSQL, Redis |
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
  ├─ /auth/login    → issue access + refresh token
  ├─ /auth/me       → verify token_version via Redis (no DB query)
  ├─ /auth/refresh  → Refresh Token Rotation
  └─ /auth/logout   → revoke refresh token
  │
  ├─ [PostgreSQL]   refresh_tokens table, users table
  └─ [Redis]        token_version cache

[Pronunciation Pipeline]
  React (mic input)
    → FastAPI
    → ffmpeg (normalize to 16kHz mono wav)
    → Whisper API (STT) + OpenAI TTS (parallel) 
    → GPT-4o-mini (scoring + feedback)
    → Response
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

## Getting Started

**Requirements**
- Docker, Docker Compose
- OpenAI API Key

**1. Clone**
```bash
git clone https://github.com/gptjd345/speakBack-React.git
cd speakBack-React
```

**2. Configure environment**
```bash
cp .env.example .env
# fill in OPENAI_API_KEY, JWT_SECRET_KEY, DATABASE_URL
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
    │   ├── routes/    # auth, analyze
    │   ├── core/      # security, redis
    │   ├── db/        # models, schemas
    │   └── langgraph/ # STT → TTS → GPT pipeline
    └── alembic/       # DB migrations
```