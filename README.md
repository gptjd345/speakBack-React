# SpeakBack

영어 발음 교정 웹 애플리케이션.
목표는 **native-level 발음이 아닌, native speaker와 무리없이 소통 가능한 발음**의 습득.

음성을 업로드하거나 녹음하면 강세·리듬 패턴을 분석해 피드백을 제공하고,
누적된 세션 이력을 벡터 DB에 임베딩하여 개인화된 연습 문장을 생성합니다.

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| **Pronunciation Coach** | 목표 문장 입력 → 어조 분석·문법 교정·유사 문장 제안 → 음성 녹음/업로드 → 강세·리듬 분석 + GPT 피드백 |
| **문장 제안** | LangGraph tool calling으로 어조(formal/neutral/informal) 감지, 문법 교정, 나머지 2가지 어조 변환문 제안 |
| **Practice Lab** | 과거 세션 패턴을 RAG로 분석 → 취약 패턴 타겟 연습 문장 3개 생성 |
| **Session History** | 세션별 점수·피드백 이력 조회 |
| **JWT 인증** | Access/Refresh Token Rotation, Redis 기반 token_version 검증 |

---

## 기술 스택

| 영역 | 기술 |
|---|---|
| **Frontend** | React, Axios |
| **Backend** | FastAPI |
| **AI Agent** | LangGraph (tool calling 기반 문장 제안) |
| **AI** | OpenAI Whisper API (STT), OpenAI TTS, GPT-4o-mini |
| **Audio** | librosa (RMS energy, pyin pitch), ffmpeg |
| **DB** | PostgreSQL + pgvector, Redis, AWS S3 |
| **Infra** | Docker Compose, Alembic |

---

## 시스템 아키텍처

```
[React]
  ├─ POST /api/analyze/upload-url    → Presigned URL 발급
  ├─ PUT  {presigned_url}            → S3 직접 업로드 (FastAPI 우회)
  ├─ POST /api/analyze/prepare       → communicative weight + TTS 사전 캐싱
  ├─ POST /api/analyze/suggest       → 문장 제안 (LangGraph agent)
  └─ POST /api/analyze/process/stream → 발음 분석 (SSE 스트리밍)

[Pronunciation Pipeline]
  S3 다운로드
  → ffmpeg (16kHz mono wav 정규화)
  → Whisper API (STT + word timestamps)    ─┐
  → OpenAI TTS (참고 음성 생성)              ├─ 병렬 실행
  → GPT communicative weight 분석          ─┘
  → librosa acoustic analysis (단어별 RMS energy, 연음 감지)
  → GPT 평가 (강세 패턴 + intelligibility → 점수 + 피드백)
  → session_history 저장 + session_patterns 임베딩 저장
  ※ 각 단계 완료 시 SSE로 진행 상황을 프론트에 실시간 전송

[Sentence Suggestion (LangGraph Agent)]
  LLM이 입력 문장 분석
  → report_analysis 툴 호출 (어조 감지 + 문법 교정)
  → 해당 어조를 제외한 2개 convert 툴 동적 선택·실행
     (convert_formal / convert_neutral / convert_informal)
  → 최종 결과: 어조, 교정 문장, 2가지 변환 문장 반환

[Practice Lab (RAG)]
  최근 세션 패턴 벡터 → pgvector 유사도 검색
  → 반복 취약 패턴 추출 (weak_words, Whisper mismatch 빈도)
  → GPT 개인화 피드백 + 연습 문장 3개 생성

[Auth]
  Login   → access token (30m) + refresh token (14d) 발급
  /me     → JWT 검증 + Redis token_version 비교 (DB 쿼리 없음)
  /refresh → Refresh Token Rotation (재사용 감지 시 전체 세션 무효화)
```

---

## ERD

```
users
├── id              INTEGER PK
├── username        VARCHAR(50) UNIQUE
├── email           VARCHAR(100) UNIQUE
├── password        VARCHAR(255)
├── token_version   INTEGER          -- Redis 토큰 무효화용 버전 관리
└── created_at      DATETIME

refresh_tokens
├── id              INTEGER PK
├── user_id         INTEGER FK → users.id
├── jti             VARCHAR(64) UNIQUE  -- JWT ID (재사용 감지)
├── expires_at      DATETIME
├── revoked_at      DATETIME NULLABLE  -- 무효화 시각
└── created_at      DATETIME

session_history
├── id              INTEGER PK
├── user_id         INTEGER FK → users.id
├── target_text     TEXT             -- 목표 문장
├── user_transcript TEXT             -- STT 변환 결과
├── score           FLOAT            -- GPT 평가 점수 (0~100)
├── strengths       JSON             -- 잘한 부분 ["word", ...]
├── improvements    JSON             -- 개선 필요 ["word", ...]
├── rhythm_feedback TEXT             -- 리듬 피드백
└── created_at      DATETIME

session_patterns                     -- RAG 검색용 벡터 테이블
├── id              INTEGER PK
├── session_id      INTEGER FK → session_history.id
├── user_id         INTEGER FK → users.id
├── pattern_text    TEXT             -- 임베딩 원본 텍스트
├── weak_words      JSON             -- 강세가 약했던 내용어
├── transcript_mismatches JSON       -- target vs STT 불일치 단어
├── score           FLOAT
├── embedding       VECTOR(1536)     -- text-embedding-3-small (pgvector)
└── created_at      DATETIME
```

---

## 설계 고민 기록

- [발음 분석 파이프라인 설계](docs/pronunciation-pipeline.md)
- [RAG 아키텍처 설계](docs/rag-architecture.md)
- [문장 제안 에이전트 설계](docs/suggest-agent.md)

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
│       ├── api/                # langgraphApi, historyApi
│       └── hooks/              # useLangGraph
└── backend/
    ├── app/
    │   ├── routes/             # auth, analyze, history, lab
    │   ├── core/               # security, redis, s3, embedding
    │   ├── db/                 # models: users, session_history, session_patterns
    │   ├── services/           # pronunciation.py, analysis_result.py
    │   └── agents/             # suggest_graph.py (LangGraph)
    └── alembic/                # DB 마이그레이션
```
