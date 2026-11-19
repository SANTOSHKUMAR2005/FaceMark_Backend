from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .config import TEACHER_SIGNUP_CODE, ALLOWED_EMAIL_DOMAINS
from .database import get_db
from .models import User, Student
from .security import hash_password, verify_password, create_token
from .emailcodes import issue_code, check_code

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    name: str
    email: str
    password: str
    role: str  # "teacher" | "student"
    teacher_code: str = ""


class LoginIn(BaseModel):
    email: str
    password: str
    role: str


class EmailIn(BaseModel):
    email: str


class VerifyIn(BaseModel):
    email: str
    code: str


class ResetIn(BaseModel):
    email: str
    code: str
    new_password: str


def _email(raw: str) -> str:
    return raw.strip().lower()


def _domain_ok(email: str) -> bool:
    """Exact domain match: 'a@college.edu' passes, 'a@evil-college.edu' and 'a@x.college.edu' do not."""
    if email.count("@") != 1 or not all(email.split("@")):
        return False
    return not ALLOWED_EMAIL_DOMAINS or email.split("@")[1] in ALLOWED_EMAIL_DOMAINS


def _require_domain(email: str):
    if not _domain_ok(email):
        if ALLOWED_EMAIL_DOMAINS:
            raise HTTPException(400, "Only " + " or ".join("@" + d for d in ALLOWED_EMAIL_DOMAINS) + " email addresses can be used.")
        raise HTTPException(400, "Enter a valid email address.")


def _token_response(user: User):
    return {"token": create_token(user), "role": user.role, "name": user.name}


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """Creates the account (unverified) and emails a 6-digit code. No login until the code is entered."""
    if body.role not in ("teacher", "student"):
        raise HTTPException(400, "Role must be teacher or student.")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    if body.role == "teacher" and body.teacher_code != TEACHER_SIGNUP_CODE:
        raise HTTPException(403, "Wrong teacher signup code.")
    email = _email(body.email)
    _require_domain(email)
    old = db.query(User).filter(User.email == email).first()
    if old and old.is_verified:
        raise HTTPException(400, "This email is already registered. Try logging in.")
    if old:  # earlier sign-up that was never verified: start again
        db.query(Student).filter(Student.user_id == old.id).delete()
        db.delete(old)
        db.flush()
    user = User(email=email, name=body.name.strip(), role=body.role,
                password_hash=hash_password(body.password), is_verified=False)
    db.add(user)
    db.flush()
    if body.role == "student":
        db.add(Student(user_id=user.id, name=user.name))
    db.commit()
    issue_code(db, email, "verify")
    return {"verification_required": True, "email": email}


@router.post("/verify-email")
def verify_email(body: VerifyIn, db: Session = Depends(get_db)):
    email = _email(body.email)
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(400, "No active code. Please ask for a new one.")
    check_code(db, email, "verify", body.code)
    user.is_verified = True
    db.commit()
    return _token_response(user)


@router.post("/resend-verification")
def resend_verification(body: EmailIn, db: Session = Depends(get_db)):
    email = _email(body.email)
    user = db.query(User).filter(User.email == email).first()
    if user and not user.is_verified and _domain_ok(email):
        issue_code(db, email, "verify")
    return {"message": "If this email needs verification, a new code has been sent."}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    _require_domain(_email(body.email))
    user = db.query(User).filter(User.email == _email(body.email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    if user.role != body.role:
        raise HTTPException(403, f"This account is not a {body.role} account.")
    if not user.is_verified:
        try:
            issue_code(db, user.email, "verify")
        except HTTPException as e:
            if e.status_code != 429:  # a code was just sent; the old one still works
                raise
        raise HTTPException(403, {"code": "email_not_verified",
                                  "message": "Please verify your email. We have sent you a code."})
    return _token_response(user)


@router.post("/forgot-password")
def forgot_password(body: EmailIn, db: Session = Depends(get_db)):
    """Always gives the same answer, so nobody can use it to find out which emails are registered."""
    email = _email(body.email)
    user = db.query(User).filter(User.email == email).first()
    if user and user.is_verified and _domain_ok(email):
        try:
            issue_code(db, email, "reset")
        except HTTPException as e:
            if e.status_code != 429:
                raise
    return {"message": "If this email is registered, a code has been sent to it."}


@router.post("/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    if len(body.new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    email = _email(body.email)
    user = db.query(User).filter(User.email == email, User.is_verified == True).first()  # noqa: E712
    if not user:
        raise HTTPException(400, "No active code. Please ask for a new one.")
    check_code(db, email, "reset", body.code)
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"ok": True}
