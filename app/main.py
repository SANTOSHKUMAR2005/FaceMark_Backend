import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import FRONTEND_ORIGIN, GCS_BUCKET, ALLOWED_EMAIL_DOMAINS
from .database import Base, engine
from . import models, auth, students, classes, storage, options

Base.metadata.create_all(bind=engine)  # creates tables in MySQL on first run

app = FastAPI(title="Face Attendance API")
app.add_middleware(CORSMiddleware, allow_origins=[FRONTEND_ORIGIN, "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(classes.router)

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
            "academic_year_start_month": options.ACADEMIC_YEAR_START_MONTH, "allowed_email_domains" : ALLOWED_EMAIL_DOMAINS}
