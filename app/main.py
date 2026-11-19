import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import FRONTEND_ORIGIN, GCS_BUCKET, ALLOWED_EMAIL_DOMAINS, ADMIN_EMAIL, ADMIN_PASSWORD
from .database import Base, engine, SessionLocal
from . import models, auth, students, classes, admin, storage, options
from .security import hash_password

Base.metadata.create_all(bind=engine)  # creates tables in MySQL on first run


def seed_admin():
    """Creates the admin account from ADMIN_EMAIL / ADMIN_PASSWORD in .env if it does not exist yet."""
    if not (ADMIN_EMAIL and ADMIN_PASSWORD):
        return
    db = SessionLocal()
    try:
        if not db.query(models.User).filter(models.User.email == ADMIN_EMAIL).first():
            db.add(models.User(email=ADMIN_EMAIL, name="Administrator", role="admin", is_verified=True,
                               password_hash=hash_password(ADMIN_PASSWORD)))
            db.commit()
    finally:
        db.close()


seed_admin()

app = FastAPI(title="Face Attendance API")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN, "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(classes.router)
app.include_router(admin.router)

if not GCS_BUCKET:  # local fallback for photos
    os.makedirs(storage.LOCAL_DIR, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=storage.LOCAL_DIR), name="uploads")


@app.get("/")
def health():
    return {"status": "ok"}


@app.get("/meta")
def meta():
    """Dropdown options for the frontend (edit them in app/options.py)."""
    return {"degrees": options.DEGREES, "departments": options.DEPARTMENTS, "sections": options.SECTIONS,
            "academic_year_start_month": options.ACADEMIC_YEAR_START_MONTH,
            "allowed_email_domains": ALLOWED_EMAIL_DOMAINS}
