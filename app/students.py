import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Student, Classroom, ClassCohort, AttendanceSession, AttendanceRecord
from .security import student_only
from . import faces, storage, academic

router = APIRouter(prefix="/students", tags=["students"])
MIN_PHOTOS, MAX_PHOTOS = 3, 4


def _me(user: User, db: Session) -> Student:
    return db.query(Student).filter(Student.user_id == user.id).one()


def profile_dict(s: Student):
    paths = json.loads(s.photo_paths or "[]")
    has_batch = bool(s.batch_start_year and s.degree)
    cur = academic.current_semester(s.batch_start_year, s.degree) if has_batch else None
    total = academic.total_semesters(s.degree) if has_batch else None
    submitted = s.profile_submitted_at is not None
    photos_locked = bool(paths and cur and s.photos_semester == cur)   # already updated this semester
    next_update = None
    if photos_locked and cur < total:
        next_update = academic.semester_start_date(s.batch_start_year, cur + 1).isoformat()
    complete = all([s.name, s.roll_number, has_batch, s.department, s.section]) and submitted and len(paths) >= MIN_PHOTOS
    return {
        "name": s.name, "roll_number": s.roll_number, "phone": s.phone,
        "batch_start_year": s.batch_start_year, "degree": s.degree,
        "department": s.department, "section": s.section,
        "batch_label": academic.batch_label(s.batch_start_year, s.degree) if has_batch else None,
        "current_semester": cur, "total_semesters": total,
        "profile_locked": submitted,
        "photos": [storage.photo_url(p) for p in paths],
        "photos_locked": photos_locked, "next_photo_update": next_update,
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
    confirm: bool = False   # student must confirm that they checked everything


def apply_details(s: Student, body: ProfileIn, db: Session, by_admin: bool = False):
    if not by_admin:
        if s.profile_submitted_at:
            raise HTTPException(403, "Your profile is locked. Contact your college if something needs to be corrected.")
        if not body.confirm:
            raise HTTPException(400, "Please confirm that you have checked all details.")
    academic.validate_group(body.batch_start_year, body.degree, body.department, body.section)
    roll = body.roll_number.strip()
    if db.query(Student).filter(Student.roll_number == roll, Student.id != s.id).first():
        raise HTTPException(400, "This roll number is already used by another student.")
    s.name, s.roll_number, s.phone = body.name.strip(), roll, body.phone.strip()
    s.batch_start_year, s.degree = body.batch_start_year, body.degree
    s.department, s.section = body.department, body.section
    if s.profile_submitted_at is None:
        s.profile_submitted_at = datetime.utcnow()
    db.commit()


def apply_photos(s: Student, files: List[UploadFile], db: Session, by_admin: bool = False):
    if not (s.batch_start_year and s.degree):
        raise HTTPException(400, "Save the profile details first, then add photos.")
    cur = academic.current_semester(s.batch_start_year, s.degree)
    old_paths = json.loads(s.photo_paths or "[]")
    if not by_admin:
        if not s.profile_submitted_at:
            raise HTTPException(400, "Submit your profile first, then add photos.")
        if old_paths and s.photos_semester == cur:
            msg = "You have already updated your photos this semester."
            if cur < academic.total_semesters(s.degree):
                nxt = academic.semester_start_date(s.batch_start_year, cur + 1)
                msg += f" You can update them again from {nxt:%d %b %Y} (semester {cur + 1})."
            else:
                msg += " Contact your college if they must be changed."
            raise HTTPException(403, msg)
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
    for old in old_paths:
        storage.delete_photo(old)
    s.photo_paths = json.dumps([storage.save_photo(d, s.id, ct) for d, ct in blobs])
    s.encodings = json.dumps(encodings)
    s.photos_semester = cur
    db.commit()


@router.get("/me")
def get_profile(user: User = Depends(student_only), db: Session = Depends(get_db)):
    return profile_dict(_me(user, db))


@router.put("/me")
def submit_profile(body: ProfileIn, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Can be done once. After this the profile is locked for the student (only an admin can change it)."""
    s = _me(user, db)
    apply_details(s, body, db)
    return profile_dict(s)


@router.post("/me/photos")
def upload_photos(files: List[UploadFile] = File(...), user: User = Depends(student_only),
                  db: Session = Depends(get_db)):
    """Allowed once per semester."""
    s = _me(user, db)
    apply_photos(s, files, db)
    return profile_dict(s)


@router.get("/me/subjects")
def subjects(semester: int, user: User = Depends(student_only), db: Session = Depends(get_db)):
    """Subjects whose class includes this student's batch, degree and section for the chosen semester."""
    s = _me(user, db)
    if not (s.batch_start_year and s.degree and s.department and s.section):
        return []
    rows = (db.query(Classroom).join(ClassCohort, ClassCohort.classroom_id == Classroom.id)
            .filter(Classroom.department == s.department, ClassCohort.batch_start_year == s.batch_start_year,
                    ClassCohort.degree == s.degree, ClassCohort.section == s.section,
                    ClassCohort.semester == semester).distinct().all())
    return [{"id": c.id, "subject": c.subject, "teacher": c.teacher.name} for c in rows]


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
