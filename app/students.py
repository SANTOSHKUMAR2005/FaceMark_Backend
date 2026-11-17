import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Student, Classroom, AttendanceSession, AttendanceRecord
from .security import student_only
from . import faces, storage, academic

router = APIRouter(prefix="/students", tags=["students"])
MIN_PHOTOS, MAX_PHOTOS = 3, 4


def _me(user: User, db: Session) -> Student:
    return db.query(Student).filter(Student.user_id == user.id).one()


def _profile(s: Student):
    paths = json.loads(s.photo_paths or "[]")
    has_batch = bool(s.batch_start_year and s.degree)
    cur = academic.current_semester(s.batch_start_year, s.degree) if has_batch else None
    complete = all([s.name, s.roll_number, has_batch, s.department, s.section]) and len(paths) >= MIN_PHOTOS
    return {
        "name": s.name, "roll_number": s.roll_number, "phone": s.phone,
        "batch_start_year": s.batch_start_year, "degree": s.degree,
        "department": s.department, "section": s.section,
        "batch_label": academic.batch_label(s.batch_start_year, s.degree) if has_batch else None,
        "current_semester": cur,
        "total_semesters": academic.total_semesters(s.degree) if has_batch else None,
        "photos": [storage.photo_url(p) for p in paths],
        "photos_outdated": bool(paths and cur and s.photos_semester != cur),
        "profile_complete": bool(complete),
    }


class ProfileIn(BaseModel):
    name: str
    roll_number: str
    batch_start_year: int
    degree: str
    department: str
    section: str
    phone: str = ""


@router.get("/me")
def get_profile(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return _profile(_me(user, db))


@router.put("/me")
def update_profile(body: ProfileIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    academic.validate_group(body.batch_start_year, body.degree, body.department, body.section)
    s = _me(user, db)
    roll = body.roll_number.strip()
    if db.query(Student).filter(Student.roll_number == roll, Student.id != s.id).first():
        raise HTTPException(400, "This roll number is already used by another student.")
    s.name, s.roll_number, s.phone = body.name.strip(), roll, body.phone.strip()
    s.batch_start_year, s.degree = body.batch_start_year, body.degree
    s.department, s.section = body.department, body.section
    db.commit()
    return _profile(s)


@router.post("/me/photos")
def upload_photos(files: List[UploadFile] = File(...), user: User = Depends(student_only),
                  db: Session = Depends(get_db)):
    """Can be repeated any time. Each upload replaces the old photos (do this every semester)."""
    s = _me(user, db)
    if not (s.batch_start_year and s.degree):
        raise HTTPException(400, "Save your details first, then add photos.")
    if not (MIN_PHOTOS <= len(files) <= MAX_PHOTOS):
        raise HTTPException(400, f"Upload {MIN_PHOTOS} to {MAX_PHOTOS} photos.")
    blobs, encodings = [], []
    for i, f in enumerate(files, 1):
        data = f.file.read()
        try:
            encodings.append(faces.encode_profile_photo(data))
        except ValueError as e:
            raise HTTPException(400, f"Photo {i}: {e} Use a clear photo with only your face.")
        except Exception:
            raise HTTPException(400, f"Photo {i} could not be read as an image.")
        blobs.append((data, f.content_type or "image/jpeg"))
    for old in json.loads(s.photo_paths or "[]"):
        storage.delete_photo(old)
    s.photo_paths = json.dumps([storage.save_photo(d, s.id, ct) for d, ct in blobs])
    s.encodings = json.dumps(encodings)
    s.photos_semester = academic.current_semester(s.batch_start_year, s.degree)
    db.commit()
    return _profile(s)


@router.get("/me/subjects")
def subjects(semester: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Subjects of this student's batch, degree, department and section for the chosen semester."""
    s = _me(user, db)
    if not (s.batch_start_year and s.degree and s.department and s.section):
        return []
    rows = db.query(Classroom).filter(
        Classroom.batch_start_year == s.batch_start_year, Classroom.degree == s.degree,
        Classroom.department == s.department, Classroom.section == s.section,
        Classroom.semester == semester).all()
    return [{"id": c.id, "name": c.name, "subject": c.subject, "teacher": c.teacher.name} for c in rows]


@router.get("/me/attendance")
def my_attendance(classroom_id: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    s = _me(user, db)
    rows = (db.query(AttendanceSession.date, AttendanceRecord.present)
            .join(AttendanceRecord, AttendanceRecord.session_id == AttendanceSession.id)
            .filter(AttendanceSession.classroom_id == classroom_id, AttendanceRecord.student_id == s.id)
            .order_by(AttendanceSession.date.desc()).all())
    attended = sum(1 for _, p in rows if p)
    total = len(rows)
    return {"records": [{"date": d.isoformat(), "present": p} for d, p in rows],
            "total": total, "attended": attended,
            "percentage": round(attended * 100 / total, 1) if total else 0}
