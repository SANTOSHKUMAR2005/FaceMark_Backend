from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Student
from .security import admin_only
from .students import ProfileIn, profile_dict, apply_details, apply_photos
from . import academic

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_only)])


def _student(student_id: int, db: Session) -> Student:
    s = db.get(Student, student_id)
    if not s:
        raise HTTPException(404, "Student not found.")
    return s


def _full(s: Student):
    return {**profile_dict(s), "id": s.id, "email": s.user.email}


@router.get("/students")
def list_students(q: str = "", department: str = "", degree: str = "", batch_start_year: int = 0,
                  section: str = "", db: Session = Depends(get_db)):
    query = db.query(Student).join(User, User.id == Student.user_id)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter((Student.name.like(like)) | (Student.roll_number.like(like)) | (User.email.like(like)))
    if department:
        query = query.filter(Student.department == department)
    if degree:
        query = query.filter(Student.degree == degree)
    if batch_start_year:
        query = query.filter(Student.batch_start_year == batch_start_year)
    if section:
        query = query.filter(Student.section == section)
    out = []
    for s in query.order_by(Student.roll_number, Student.name).limit(300).all():
        p = profile_dict(s)
        out.append({"id": s.id, "name": s.name, "email": s.user.email, "roll_number": s.roll_number,
                    "department": s.department, "degree": s.degree, "batch_label": p["batch_label"],
                    "section": s.section, "current_semester": p["current_semester"],
                    "photo_count": len(p["photos"]), "profile_locked": p["profile_locked"],
                    "profile_complete": p["profile_complete"]})
    return out


@router.get("/students/{student_id}")
def get_student(student_id: int, db: Session = Depends(get_db)):
    return _full(_student(student_id, db))


@router.put("/students/{student_id}")
def update_student(student_id: int, body: ProfileIn, db: Session = Depends(get_db)):
    s = _student(student_id, db)
    apply_details(s, body, db, by_admin=True)
    return _full(s)


@router.post("/students/{student_id}/photos")
def update_photos(student_id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """Admin can replace photos at any time (no once-per-semester limit)."""
    s = _student(student_id, db)
    apply_photos(s, files, db, by_admin=True)
    return _full(s)
