import json
from datetime import date, datetime, timedelta
from typing import List
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Student, Classroom, ClassCohort, AttendanceSession, AttendanceRecord
from .security import teacher_only
from . import faces, academic
from .options import DEPARTMENTS

router = APIRouter(prefix="/classes", tags=["classes"])
MAX_COHORTS = 8


class CohortIn(BaseModel):
    batch_start_year: int
    degree: str
    semester: int
    section: str


class ClassIn(BaseModel):
    subject: str
    department: str
    cohorts: List[CohortIn]


class SubmitIn(BaseModel):
    present_ids: List[int]


def _own_class(class_id: int, teacher: User, db: Session) -> Classroom:
    c = db.get(Classroom, class_id)
    if not c or c.teacher_id != teacher.id:
        raise HTTPException(404, "Class not found.")
    return c


def _roster(c: Classroom, db: Session) -> List[Student]:
    """Students of this department who belong to ANY cohort of the class and have face data."""
    if not c.cohorts:
        return []
    match = [and_(Student.batch_start_year == k.batch_start_year, Student.degree == k.degree,
                  Student.section == k.section) for k in c.cohorts]
    q = db.query(Student).filter(Student.department == c.department, or_(*match)).order_by(Student.roll_number)
    return [s for s in q if json.loads(s.encodings or "[]")]


def _out(c: Classroom):
    cohorts = [{"id": k.id, "batch_start_year": k.batch_start_year, "degree": k.degree, "semester": k.semester,
                "section": k.section, "batch_label": academic.batch_label(k.batch_start_year, k.degree)}
               for k in c.cohorts]
    label = "; ".join(f"{k['degree']} {k['batch_label']}, Sem {k['semester']}, Sec {k['section']}" for k in cohorts)
    return {"id": c.id, "subject": c.subject, "department": c.department, "cohorts": cohorts, "label": label}


@router.post("")
def create_class(body: ClassIn, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    if body.department not in DEPARTMENTS:
        raise HTTPException(400, "Choose a valid department.")
    if not (1 <= len(body.cohorts) <= MAX_COHORTS):
        raise HTTPException(400, f"Add 1 to {MAX_COHORTS} batches.")
    seen = set()
    for k in body.cohorts:
        academic.validate_group(k.batch_start_year, k.degree, body.department, k.section)
        if not (1 <= k.semester <= academic.total_semesters(k.degree)):
            raise HTTPException(400, f"{k.degree} has semesters 1 to {academic.total_semesters(k.degree)}.")
        key = (k.batch_start_year, k.degree, k.section)
        if key in seen:
            raise HTTPException(400, "The same batch, degree and section is added twice.")
        seen.add(key)
    c = Classroom(teacher_id=teacher.id, subject=body.subject.strip(), department=body.department)
    c.cohorts = [ClassCohort(batch_start_year=k.batch_start_year, degree=k.degree, semester=k.semester,
                             section=k.section) for k in body.cohorts]
    db.add(c)
    db.commit()
    return _out(c)


@router.get("")
def my_classes(teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    return [_out(c) for c in db.query(Classroom).filter(Classroom.teacher_id == teacher.id).order_by(Classroom.id.desc())]


@router.delete("/{class_id}")
def delete_class(class_id: int, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    db.delete(_own_class(class_id, teacher, db))
    db.commit()
    return {"ok": True}


def _student_out(s: Student):
    return {"id": s.id, "name": s.name, "roll_number": s.roll_number, "degree": s.degree,
            "batch_label": academic.batch_label(s.batch_start_year, s.degree)}


@router.get("/{class_id}/students")
def roster(class_id: int, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    c = _own_class(class_id, teacher, db)
    return {"class": _out(c), "students": [_student_out(s) for s in _roster(c, db)]}


@router.post("/{class_id}/recognize")
def recognize(class_id: int, frame: UploadFile = File(...), teacher: User = Depends(teacher_only),
              db: Session = Depends(get_db)):
    """Receives one webcam frame, returns ids of enrolled students whose faces appear in it.
    Nothing is saved here - the draft lives in the teacher's browser until they press Submit."""
    c = _own_class(class_id, teacher, db)
    known = {s.id: [np.array(e) for e in json.loads(s.encodings)] for s in _roster(c, db)}
    if not known:
        return {"recognized_ids": []}
    return {"recognized_ids": faces.recognize(frame.file.read(), known)}


@router.post("/{class_id}/submit")
def submit(class_id: int, body: SubmitIn, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    c = _own_class(class_id, teacher, db)
    students = _roster(c, db)
    present = set(body.present_ids)
    today = date.today()
    old = db.query(AttendanceSession).filter_by(classroom_id=c.id, date=today).first()
    if old:  # re-submitting the same day replaces the earlier sheet
        db.delete(old)
        db.flush()
    sess = AttendanceSession(classroom_id=c.id, date=today, submitted_at=datetime.utcnow())
    sess.records = [AttendanceRecord(student_id=s.id, present=s.id in present) for s in students]
    db.add(sess)
    db.commit()
    return {"ok": True, "present": len([s for s in students if s.id in present]), "total": len(students)}


@router.get("/{class_id}/attendance")
def recent_attendance(class_id: int, teacher: User = Depends(teacher_only), db: Session = Depends(get_db)):
    """Today + previous 4 days."""
    c = _own_class(class_id, teacher, db)
    days = [date.today() - timedelta(days=i) for i in range(5)]
    sessions = db.query(AttendanceSession).filter(AttendanceSession.classroom_id == c.id,
                                                  AttendanceSession.date.in_(days)).all()
    marks = {}  # (student_id, iso date) -> present
    for ss in sessions:
        for r in ss.records:
            marks[(r.student_id, ss.date.isoformat())] = r.present
    students = db.query(Student).filter(Student.id.in_({k[0] for k in marks})).order_by(Student.roll_number).all()
    return {"class": _out(c), "dates": [d.isoformat() for d in days],
            "students": [{**_student_out(s), "marks": {d.isoformat(): marks.get((s.id, d.isoformat())) for d in days}}
                         for s in students]}
