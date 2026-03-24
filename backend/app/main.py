from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routes.auth_routes import router as api_router
from app.routes.langgraph_routes import router as analyze_router
from app.routes.history_routes import router as history_router
from app.db.database import Base, engine
from app.langgraph_config.pronunciation_module import warmup_librosa

app = FastAPI(title="SpeakBack API")

@app.on_event("startup")
async def startup():
    warmup_librosa()  # 서버 시작 시 numba JIT 컴파일 백그라운드 실행

# CORS 설정 (React 프론트엔드 접근 허용)
origins = [
    "http://localhost:3000",  # React dev server
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 테이블 생성 alembic으로 관리할 예정
# Base.metadata.create_all(bind=engine)

app.include_router(api_router, prefix="/api/auth", tags=["auth"])
app.include_router(analyze_router, prefix="/api/analyze", tags=["analyze"])
app.include_router(history_router, prefix="/api/history", tags=["history"])
