from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import schemas, models, database
from app.core import security
from app.core.redis import redis_client
from datetime import datetime
from app.core.dependencies import get_current_user
from app.db.database import get_db
import os

router = APIRouter()

RefreshToken = models.RefreshToken

IS_PROD = os.getenv("APP_ENV") == "production"


@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(
        (models.User.username == user.username) |
        (models.User.email == user.email)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username or email already exists")

    hashed = security.hash_password(user.password)
    db_user = models.User(username=user.username, email=user.email, password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "email": db_user.email}


@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user or not security.verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    redis_client.set(f"token_version:{db_user.id}", db_user.token_version)

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

    db.add(RefreshToken(user_id=db_user.id, jti=jti, expires_at=expire))
    db.commit()

    response = JSONResponse(content={
        "access_token": access_token,
        "user": {
            "username": db_user.username,
            "email": db_user.email
        }
    })
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=14 * 24 * 60 * 60,
    )
    return response


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")

    try:
        refresh_payload = security.decode_refresh_token(refresh_token)
    except HTTPException:
        response = JSONResponse(content={"msg": "Logged out"})
        response.delete_cookie("refresh_token")
        return response

    db_refresh = db.query(RefreshToken).filter(
        RefreshToken.jti == refresh_payload["jti"]
    ).first()

    if db_refresh:
        db_refresh.revoked_at = datetime.utcnow()
        db.commit()

    response = JSONResponse(content={"msg": "Logged out"})
    response.delete_cookie("refresh_token")
    return response


@router.post("/me")
def me(current_user=Depends(get_current_user)):
    return {"user": current_user}


@router.post("/refresh")
def refresh(request: Request, db: Session = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    try:
        refresh_payload = security.decode_refresh_token(refresh_token)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    jti = refresh_payload.get("jti")
    user_id = refresh_payload.get("sub")

    db_refresh = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()

    if not db_refresh or db_refresh.revoked_at is not None:
        db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id
        ).update({"revoked_at": datetime.utcnow()})
        db.query(models.User).filter(
            models.User.id == user_id
        ).update({"token_version": models.User.token_version + 1})
        db.commit()
        raise HTTPException(status_code=401, detail="Token reuse detected")

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    db_refresh.revoked_at = datetime.utcnow()

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

    db.add(RefreshToken(user_id=db_user.id, jti=new_jti, expires_at=new_expire))
    db.commit()

    response = JSONResponse(content={
        "access_token": new_access_token,
        "user": {
            "username": db_user.username,
            "email": db_user.email
        }
    })
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=IS_PROD,
        samesite="lax",
        max_age=14 * 24 * 60 * 60,
    )
    return response
