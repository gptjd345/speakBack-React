from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import schemas, models, database
from app.core import security
from app.core.redis import redis_client
from uuid import uuid4
import json
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.dependencies import get_current_user
from app.db.database import get_db

router = APIRouter()

RefreshToken = models.RefreshToken

@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):

    # 1. 중복 체크
    existing = db.query(models.User).filter(
        (models.User.username == user.username) | 
        (models.User.email == user.email)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists")
    
    # 2. 회원데이터 저장
    hashed = security.hash_password(user.password)
    db_user = models.User(username=user.username, email=user.email, password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "email": db_user.email}

@router.post("/logout") # 완
def logout(
    request: Request, db: Session = Depends(get_db)
):  
    # 운영: 쿠키에서 추출
    """
    refresh_token = request.cookies.get("refresh_token")
    """

    # 로컬: 헤더에서 추출
    refresh_token = request.headers.get("X-Refresh-Token")

    # 1. refresh 토큰 서명 검증
    try:
        refresh_payload = security.decode_refresh_token(refresh_token)
    # 만료되거나 서명검증 오류의 경우 메시지만 리턴    
    except HTTPException:
        return {"msg": "Logged out"}

    # 2. DB에서 refresh 토큰 찾기
    db_refresh = db.query(RefreshToken).filter(
        RefreshToken.jti == refresh_payload["jti"]
    ).first()

    # 3. revoked 된 날짜 저장
    if db_refresh:
        db_refresh.revoked_at = datetime.utcnow()
        db.commit()

    # 토큰이 없어도 그냥 종료(토큰유무를 굳이 알릴필요없음)
    return {"msg": "Logged out"}
               

@router.post("/login") # 완
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    # 1. 유저 확인
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user or not security.verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # 2. token_version Redis에 캐시 (이후 /me는 DB 조회 없음)
    redis_client.set(f"token_version:{db_user.id}", db_user.token_version)

    # 3. 토큰 생성
    access_token = security.create_access_token(
        user_id=db_user.id,
        token_version=db_user.token_version,
        username=db_user.username,
        email=db_user.email,
    )
    refresh_token, jti, expire = security.create_refresh_token(
        user_id=db_user.id,
        token_version=db_user.token_version
    )

    # 4. Srefresh_token data 저장
    refresh_entity = RefreshToken(
        user_id=db_user.id,
        jti=jti,
        expires_at=expire
    )

    db.add(refresh_entity)
    db.commit()
    
    # 응답 반환 (access + refresh 둘 다 반환)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": db_user.username,
            "email": db_user.email
        }
    }

# me 요청
# 토큰 디코딩 -> token version 확인 -> 응답반환(DB 호출없음)
@router.post("/me")
def me(current_user=Depends(get_current_user)):
    return {"user": current_user}

@router.post("/refresh")
def refresh(request: Request, db: Session = Depends(get_db)):
    # 운영: 쿠키에서 추출
    """
    refresh_token = request.cookies.get("refresh_token")
    """

    # 로컬: 헤더에서 추출
    refresh_token = request.headers.get("X-Refresh-Token")
    
    # 1. refresh token 서명 검증
    try:
        refresh_payload = security.decode_refresh_token(refresh_token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    jti = refresh_payload.get("jti")
    user_id = refresh_payload.get("sub")

    # 2. DB에서 refresh token 찾기
    db_refresh = db.query(RefreshToken).filter(
        RefreshToken.jti == jti
    ).first()

    # 3. Refresh Token Rotation - 이미 사용됬거나 revoke된 토큰이면
    # 탈취 가능성 있으므로 해당 유저의 모든 refresh token revoke
    if not db_refresh or db_refresh.revoked_at is not None:
        # refresh 테이블에서 모든 세션을 revoke 처리
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id
        ).update({"revoked_at": datetime.utcnow()})

        # 살아있는 access token도 version 불일치로 즉시 차단
        db.query(models.User).filter(
            models.User.id == user_id
        ).update({"token_version": models.User.token_version + 1})
        db.commit()
        raise HTTPException(status_code=401, detail="Token reuse detected")

    # 4. 유저 조회 (payload의 userid로 찾기)
    db_user = db.query(models.User).filter(
        models.User.id == user_id
    ).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    # 5. 기존 refresh token revoke
    db_refresh.revoked_at = datetime.utcnow()

    # 6. 새 토큰 발급
    new_access_token = security.create_access_token(
        user_id=db_user.id,
        token_version=db_user.token_version,
        username=db_user.username,
        email=db_user.email,
    )
    new_refresh_token, new_jti, new_expire = security.create_refresh_token(
        user_id=db_user.id,
        token_version=db_user.token_version
    )

    # 7. 새 refresh token DB 저장
    db.add(RefreshToken(
        user_id=db_user.id,
        jti=new_jti,
        expires_at=new_expire
    ))
    db.commit()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "user": {
            "username": db_user.username,
            "email": db_user.email
        }
    }
   
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

