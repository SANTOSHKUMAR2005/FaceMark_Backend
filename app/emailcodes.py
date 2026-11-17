import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from .config import SECRET_KEY, CODE_EXPIRE_MINUTES, CODE_MAX_ATTEMPTS, CODE_RESEND_SECONDS
from .models import EmailCode
from .email_service import send_email

TEXTS = {
    "verify": ("Verify your email", "Use this code to verify your email and finish creating your account."),
    "reset": ("Reset your password", "Use this code to set a new password for your account."),
}


def _hash(email: str, purpose: str, code: str) -> str:
    return hashlib.sha256(f"{SECRET_KEY}:{email}:{purpose}:{code}".encode()).hexdigest()


def issue_code(db: Session, email: str, purpose: str):
    """Create a new 6-digit code and email it. Raises 429 if asked again within 60 seconds."""
    now = datetime.utcnow()
    row = db.query(EmailCode).filter_by(email=email, purpose=purpose).first()
    if row:
        wait = CODE_RESEND_SECONDS - int((now - row.created_at).total_seconds())
        if wait > 0:
            raise HTTPException(429, f"Please wait {wait} seconds before asking for another code.")
        db.delete(row)
        db.flush()
    code = f"{secrets.randbelow(1_000_000):06d}"
    row = EmailCode(email=email, purpose=purpose, code_hash=_hash(email, purpose, code),
                    created_at=now, expires_at=now + timedelta(minutes=CODE_EXPIRE_MINUTES))
    db.add(row)
    db.commit()
    subject, line = TEXTS[purpose]
    text = f"{line}\n\nYour code: {code}\n\nIt expires in {CODE_EXPIRE_MINUTES} minutes. If you did not ask for this, ignore this email."
    html = (f"<div style='font-family:Arial,sans-serif;max-width:420px'><h2>{subject}</h2><p>{line}</p>"
            f"<p style='font-size:32px;letter-spacing:8px;font-weight:bold;background:#eaf0ee;padding:14px;text-align:center'>{code}</p>"
            f"<p style='color:#555'>It expires in {CODE_EXPIRE_MINUTES} minutes. If you did not ask for this, ignore this email.</p></div>")
    try:
        send_email(email, f"{subject} - Face Attendance", text, html)
    except HTTPException:
        db.delete(row)  # let the person try again straight away
        db.commit()
        raise


def check_code(db: Session, email: str, purpose: str, code: str):
    """Raises 400 unless the code is right. A correct code is used up."""
    row = db.query(EmailCode).filter_by(email=email, purpose=purpose).first()
    if not row:
        raise HTTPException(400, "No active code. Please ask for a new one.")
    if row.expires_at < datetime.utcnow():
        db.delete(row); db.commit()
        raise HTTPException(400, "This code has expired. Please ask for a new one.")
    if row.attempts >= CODE_MAX_ATTEMPTS:
        db.delete(row); db.commit()
        raise HTTPException(400, "Too many wrong attempts. Please ask for a new code.")
    if not hmac.compare_digest(row.code_hash, _hash(email, purpose, code.strip())):
        row.attempts += 1
        db.commit()
        raise HTTPException(400, "Wrong code. Check the email and try again.")
    db.delete(row)
    db.flush()
