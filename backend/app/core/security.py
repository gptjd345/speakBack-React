from passlib.context import CryptContext
from dotenv import load_dotenv
import os

from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings
from app.core.redis import redis_client
from uuid import uuid4
from jose import jwt, JWTError, ExpiredSignatureError
from fastapi import HTTPException

# password
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    print("**************** "+repr(password)+"**************** ")
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

# jwt
def create_access_token(user_id: int, token_version: int, username: str, email: str):
    now = datetime.utcnow()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "jti": str(uuid4()),
        "token_version": token_version,
        "username": username,
        "email": email,
        "iat": now,
        "exp": expire
    }

    encoded_jwt = jwt.encode(
        payload, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt

def create_refresh_token(user_id: int, token_version: int):
    now = datetime.utcnow()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    jti = str(uuid4())

    payload = {
        "sub": str(user_id),
        "jti": jti,
        "token_version": token_version,
        "iat": now,
        "exp": expire
    }

    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    return encoded_jwt, jti, expire

def decode_access_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except ExpiredSignatureError:
        # 만료 → 프론트에서 refresh 시도
        raise HTTPException(status_code=401, detail="Access token expired")
    except JWTError:
        # 위변조, 잘못된 형식 등 → 프론트에서 로그인 페이지로 이동처리
        raise HTTPException(status_code=403, detail="Invalid access token")

# 추후 두 토큰의 secret키가 바뀔수 있어서 함수 나눔
def decode_refresh_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except ExpiredSignatureError:
        # 만료 → 프론트에서 refresh 시도
        raise HTTPException(status_code=401, detail="Access token expired")
    except JWTError:
        # 위변조, 잘못된 형식 등 → 프론트에서 로그인 페이지로 이동처리
        raise HTTPException(status_code=403, detail="Invalid access token")
