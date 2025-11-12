from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import schemas, models, database
from app.core import auth, security
from app.core.redis import redis_client
from uuid import uuid4
import json
from pydantic import BaseModel
from typing import Optional

router = APIRouter()
get_db = database.SessionLocal

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

ACCESS_TTL = 60 * 30  # 30분

@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    hashed = auth.hash_password(user.password)
    db_user = models.User(username=user.username, email=user.email, password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "email": db_user.email}

@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
        # 1. 헤더에서 access_key 확인 (로컬 테스트용)
    access_key = request.headers.get("X-Access-Key")

    # 1. 헤더에서 access_key 확인 (운영용)
    #access_key = request.cookies.get("access_key") 이후 쿠키 사용시 주석해제한다.

    session_data = redis_client.get(f"access_key:{access_key}")
    if session_data:
        data = json.loads(session_data)
        user_id = data.get("user_id")
        redis_client.delete(f"access_key:{access_key}")

        db_user = db.query(models.User).get(user_id)
        # if refresh_token exist, delete
        if db_user:
            db_user.refresh_token = None
            db.commit()

    redis_client.delete(access_key)
    print(f"### Redis session deleted: {access_key}")        

    return {"msg": "Logged out"}

@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth.verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # JWT create (core/security.py)
    access_token = security.create_access_token({"user_id": db_user.id})
    refresh_token = security.create_refresh_token({"user_id": db_user.id})

    # Store refresh_token to DB
    db_user.refresh_token = refresh_token
    db.commit()
    db.refresh(db_user)

    print("#### Redis ping test: ", redis_client.ping())  # True 나오면 연결 정상

    # access_key 생성 + Redis 저장 TTL 30 min
    access_key = str(uuid4())
 
    redis_client.set(
        f"access_token:{access_key}", 
        json.dumps({"user_id": db_user.id, "access_token": access_token}), 
        ex=ACCESS_TTL
    )

    # access_key: str, user: dict
    return create_access_response(
        access_key = access_key,
        user = {"id": db_user.id, "username": db_user.username, "email": db_user.email}
    ) 

@router.post("/refresh")
def refresh(access_key: str, db: Session = Depends(get_db)):
    session_data = redis_client.get(f"access:{access_key}")
    if not session_data:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    data = json.loads(session_data)
    user_id = data.get("user_id")
    db_user = db.query(models.User).get(user_id)

    if not db_user or not db_user.refresh_token:
        raise HTTPException(status_code=401, detail="Login required")

    if not security.verify_token(db_user.refresh_token):
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # 새 access token 발급
    new_access_token = security.create_access_token({"user_id": user_id})
    new_access_key = str(uuid4())
    redis_client.set(
        f"access:{new_access_key}",
        json.dumps({"user_id": user_id, "access_token": new_access_token}),
        ex=ACCESS_TTL
    )

    # access_key: str, user: dict
    return create_access_response(
        access_key = new_access_key,
        user = {"id": db_user.id, "username": db_user.username, "email": db_user.email}
    ) 

class AccessKeyPayload(BaseModel):
    access_key: Optional[str] = None

@router.post("/me")
def get_current_user(request: Request, db: Session = Depends(get_db)):
    # 목적 : 현재 로그인된 사용자의 정보만 조회
    # 과정 
    # if access 키가 존재하는 경우 
        # access 키를 이용해 access토큰을 레디스에서 조회 
            # if access 토큰이 존재하는 경우 
                # 토큰 검증 
                    # 성공시 토큰에서 사용자 id를 뽑아서 db 조회후 사용자로그인정보를 리턴
                    # 실패시 토큰 변조로 무조건 실패 처리 후 종료
            # else access 토큰이 존재하지 않는경우
                # access 키에 존재하는 사용자 id 를 이용해 db 조회해서 refresh 토큰 존재여부 확인 
                    # refresh 토큰이 존재하는 경우 JWT 디코딩 검증(verify_token) 만료된 refresh 토큰도 통과할 가능성이 있기 때문
                    # 검증성공시 이미 가지고 있던 id를 활용해서 access 토큰을 생성해서 레디스에 저장하고 사용자 정보 조회해서 리턴

                    # refresh 토큰이 존재하지 않는 경우 그냥 로그인이 안된거라 데이터 리턴 할거 없으니 종료 
                     
    # else access 키가 없는 경우 
        # 로그인이 안되있음으로 인식
    # 1. 헤더에서 access_key 확인 (로컬 테스트용)
    access_key = request.headers.get("X-Access-Key")

    # 1. 헤더에서 access_key 확인 (운영용)
    #access_key = request.cookies.get("access_key") 이후 쿠키 사용시 주석해제한다.
    print("### /api/auth/me cookies.get : access_key:", access_key)

    # 1. access_key 존재 여부 확인
    if not access_key or access_key == "undefined":
        return {"user": None}
    
    # 2. Redis에서 access token 조회 및 검증 
    session_data = redis_client.get(f"access_token:{access_key}")
    print("### /api/auth/me session_data : session_data:", session_data)
    if session_data:
        try:
            data = json.loads(session_data)
            payload = security.verify_token(data["access_token"])
            user_id = payload.get("user_id")
            if not user_id:
                return {"user": None}
            
            user = db.query(models.User).get(user_id)
            if not user:
                return {"user": None}
            
            # access_key: str, user: dict
            return create_access_response(
                access_key = access_key,
                user = {"id": user.id, "username": user.username, "email": user.email}
            ) 
        except Exception as e:
            print("### /me exception:", e)
            return {"user": None}

    # 3. refresh token 확인 및 검증(access_key는 있는데 레디스에 access token이 없는경우)
    # (현업에서는 fresh_token 매핑 테이블을 따로 두는 경우가 많음 -> 일단 이건 추후)
    data = json.loads(session_data)
    user_id = data.get("user_id")
    db_user = db.query(models.User).get(user_id)
    if not db_user or not db_user.refresh_token:
        return {"user": None}

    # refresh token 검증
    if not security.verify_token(db_user.refresh_token):
        return {"user": None}

    # 4. 새 access token 발급
    new_access_token = security.create_access_token({"user_id": user_id})
    new_access_key = str(uuid4())
    redis_client.set(
        f"access_token:{new_access_key}", 
        json.dumps({
        "user_id": user_id,
        "access_token": new_access_token
    }), ex=ACCESS_TTL)

    # access_key: str, user: dict
    return create_access_response(
        access_key = new_access_key,
        user = {"id": db_user.id, "username": db_user.username, "email": db_user.email}
    ) 
   
def create_access_response(access_key: str, user: dict):
    """
        access_key를 쿠키에 세팅하고 JSONResponse를 만들어 반환
        쿠키만료시간 14일 기준: Refresh 토큰 만료시간 
    """

    response = JSONResponse(
        content={
            "access_key": access_key,
            "user": user
        }
    )
    
    """
        추후 쿠키 사용시 사용
    response.set_cookie(
        key="access_key",
        value=access_key,
        httponly=True,
        samesite="None", # 이후 CSRF 토큰 로직 추가 예정
        max_age=14*24*60*60,  # 14일 (초 단위)
        secure=True, # https 연결시 사용
    )
    """
    return response

