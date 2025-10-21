from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import schemas, models, auth, database

router = APIRouter()
get_db = database.SessionLocal

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/register")
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    hashed = auth.hash_password(user.password)
    db_user = models.User(username=user.username, email=user.email, password=hashed)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "username": db_user.username, "email": db_user.email}

@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth.verify_password(user.password, db_user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = auth.create_access_token({"user_id": db_user.id})
    refresh_token = auth.create_refresh_token({"user_id": db_user.id})
    return {"access_token": access_token, "refresh_token": refresh_token}
