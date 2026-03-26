# SpeakBack

영어 발음 교정 웹 애플리케이션.
목표는 **native-level 발음이 아닌, native speaker와 무리없이 소통 가능한 발음**의 습득.

음성을 업로드하거나 녹음하면 강세·리듬 패턴을 분석해 피드백을 제공하고,
누적된 세션 이력을 벡터 DB에 임베딩하여 개인화된 연습 문장을 생성합니다.

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| **Pronunciation Coach** | 목표 문장 입력 → 음성 녹음/업로드 → 강세·리듬 분석 + GPT 피드백 |
| **Practice Lab** | 과거 세션 패턴을 RAG로 분석 → 취약 패턴 타겟 연습 문장 3개 생성 |
| **Session History** | 세션별 점수·피드백 이력 조회 |
| **JWT 인증** | Access/Refresh Token Rotation, Redis 기반 token_version 검증 |

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| **Frontend** | React, Axios |
| **Backend** | FastAPI, LangGraph |
| **AI** | OpenAI Whisper API (STT), OpenAI TTS, GPT-4o-mini |
| **Audio** | librosa (RMS energy, pyin pitch), ffmpeg |
| **DB** | PostgreSQL + pgvector, Redis, AWS S3 |
| **Infra** | Docker Compose, Alembic |

---

## 시스템 아키텍처

```
[React]
  ├─ POST /api/analyze/upload-url  → Presigned URL 발급
  ├─ PUT  {presigned_url}          → S3 직접 업로드 (FastAPI 우회)
  ├─ POST /api/analyze/prepare     → communicative weight + TTS 사전 캐싱
  └─ POST /api/analyze/process     → 분석 실행

[Pronunciation Pipeline (LangGraph)]
  S3 다운로드
  → ffmpeg (16kHz mono wav 정규화)
  → Whisper API (STT + word timestamps)    ─┐
  → OpenAI TTS (참고 음성 생성)              ├─ 병렬 실행
  → GPT communicative weight 분석          ─┘
  → librosa acoustic analysis (단어별 RMS energy, 연음 감지)
  → GPT 평가 (강세 패턴 + intelligibility → 점수 + 피드백)
  → session_history 저장 + session_patterns 임베딩 저장

[Practice Lab (RAG)]
  최근 세션 패턴 벡터 → pgvector 유사도 검색
  → 반복 취약 패턴 추출 (weak_words, Whisper mismatch 빈도)
  → GPT 개인화 피드백 + 연습 문장 3개 생성 (informal / neutral / formal)

[Auth]
  Login → access token (30m) + refresh token (14d) 발급
  /me   → JWT 검증 + Redis token_version 비교 (DB 쿼리 없음)
  /refresh → Refresh Token Rotation (재사용 감지 시 전체 세션 무효화)
```

---

## 설계 고민 기록

- [발음 분석 파이프라인 설계](docs/pronunciation-pipeline.md)
- [RAG 아키텍처 설계](docs/rag-architecture.md)

---

## 실행 방법

**Prerequisites**
- Docker, Docker Compose
- OpenAI API Key
- AWS S3 버킷 + IAM 사용자

**1. Clone**
```bash
git clone https://github.com/gptjd345/speakBack-React.git
cd speakBack-React
```

**2. 환경 변수 설정**

`backend/.env`
```env
OPENAI_API_KEY=
JWT_SECRET_KEY=
DATABASE_URL=postgresql+psycopg2://user:pass@postgres:5432/dbname
REDIS_HOST=redis
REDIS_PORT=6379

AWS_REGION=ap-northeast-2
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_BUCKET=
```

**3. 실행**
```bash
cd backend
docker compose up --build
```

**4. DB 마이그레이션**
```bash
docker compose exec fastapi alembic upgrade head
```

**5. 프론트엔드**
```bash
cd frontend
npm install
npm start
```

- Frontend: http://localhost:3000
- Backend API Docs: http://localhost:8000/docs

---

## 프로젝트 구조

```
speakBack-React/
├── frontend/                   # React
│   └── src/
│       ├── pages/              # Coach, Lab, Home
│       ├── components/         # AudioUploader, ResultViewer, Sidebar
│       └── hooks/              # useLangGraph
└── backend/
    ├── app/
    │   ├── routes/             # auth, analyze, history, lab
    │   ├── core/               # security, redis, s3, embedding
    │   ├── db/                 # models: users, session_history, session_patterns
    │   └── langgraph_config/   # pronunciation pipeline (builder, pronunciation_module)
    └── alembic/                # DB 마이그레이션
```
