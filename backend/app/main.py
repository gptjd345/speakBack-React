from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.auth_routes import router as api_router
from app.database import Base, engine

app = FastAPI(title="SpeakBack API")

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

# DB 테이블 생성
Base.metadata.create_all(bind=engine)

app.include_router(api_router)
