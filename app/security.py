from datetime import datetime, timedelta
import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from .config import SECRET_KEY, ACCESS_TOKEN_HOURS
from .database import get_db
from .models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user: User) -> str:
    exp = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_HOURS)
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": exp}, SECRET_KEY, algorithm="HS256")


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        uid = int(jwt.decode(token, SECRET_KEY, algorithms=["HS256"])["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired login. Please log in again.")
    user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "User not found.")
    return user


def teacher_only(user: User = Depends(current_user)) -> User:
    if user.role != "teacher":
        raise HTTPException(403, "Teachers only.")
    return user


def student_only(user: User = Depends(current_user)) -> User:
    if user.role != "student":
        raise HTTPException(403, "Students only.")
    return user
