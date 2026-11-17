from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, Date, DateTime, Boolean,
                        ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(10), nullable=False)  # "teacher" | "student"
    name = Column(String(100), nullable=False)
    is_verified = Column(Boolean, nullable=False, default=False)  # email confirmed with a code
    student = relationship("Student", back_populates="user", uselist=False)


class EmailCode(Base):
    """One-time 6-digit codes for email verification and password reset (stored hashed)."""
    __tablename__ = "email_codes"
    __table_args__ = (UniqueConstraint("email", "purpose"),)
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    purpose = Column(String(10), nullable=False)   # "verify" | "reset"
    code_hash = Column(String(64), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    name = Column(String(100))
    roll_number = Column(String(50), unique=True)
    batch_start_year = Column(Integer)             # end year = start + degree duration
    degree = Column(String(30))                    # B.Tech | B.Tech + M.Tech | M.Tech
    department = Column(String(100))
    section = Column(String(10))
    phone = Column(String(20))
    photos_semester = Column(Integer)              # semester in which the photos were last updated
    photo_paths = Column(Text, default="[]")   # JSON list of GCS object names
    encodings = Column(Text, default="[]")     # JSON list of 128-number face encodings
    user = relationship("User", back_populates="student")


class Classroom(Base):
    __tablename__ = "classrooms"
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)      # auto label: degree, department, batch, section
    subject = Column(String(100), nullable=False)
    batch_start_year = Column(Integer, nullable=False)
    degree = Column(String(30), nullable=False)
    department = Column(String(100), nullable=False)
    section = Column(String(10), nullable=False)
    semester = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    teacher = relationship("User")
    sessions = relationship("AttendanceSession", cascade="all, delete-orphan")


class AttendanceSession(Base):
    """One submitted attendance sheet for a class on a given day."""
    __tablename__ = "attendance_sessions"
    __table_args__ = (UniqueConstraint("classroom_id", "date"),)
    id = Column(Integer, primary_key=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=False)
    date = Column(Date, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    records = relationship("AttendanceRecord", cascade="all, delete-orphan")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("attendance_sessions.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    present = Column(Boolean, nullable=False, default=False)
