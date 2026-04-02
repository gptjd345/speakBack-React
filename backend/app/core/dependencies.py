from fastapi import Request, HTTPException, Depends
from app.core import security
from app.core.redis import redis_client

def get_current_user(request: Request):
    access_token = request.headers.get("Authorization", "").replace("Bearer ", "")
    
    # 1. 토큰 디코딩
    try:
        access_payload = security.decode_access_token(access_token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid access token")
    
    user_id = access_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # 2. payload의 token version 과 레디스에 캐시해놓은 token version이 동일한지 확인
    redis_version = redis_client.get(f"token_version:{user_id}")
    token_version = access_payload.get("token_version")

    # 3. 레디스 
    if redis_version is None:
        # Redis에 없으면 → 로그인 필요 (재로그인 유도)
        raise HTTPException(status_code=401, detail="Session not found")

    if int(redis_version) != token_version:
        raise HTTPException(status_code=401, detail="Token invalidated")

    # dict가 아닌 user 정보 객체로 반환
    return {
        "id": int(user_id),
        "username": access_payload.get("username"),
        "email": access_payload.get("email"),
    }