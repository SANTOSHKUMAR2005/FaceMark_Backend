from datetime import date
from fastapi import HTTPException
from .options import DEGREES, DEPARTMENTS, SECTIONS, ACADEMIC_YEAR_START_MONTH


def total_semesters(degree: str) -> int:
    return DEGREES[degree] * 2


def batch_label(start_year: int, degree: str) -> str:
    return f"{start_year}-{start_year + DEGREES[degree]}"


def current_semester(start_year: int, degree: str, today: date = None) -> int:
    """Semester number for a batch, calculated from today's date. Stops at the last semester."""
    today = today or date.today()
    months = (today.year - start_year) * 12 + today.month - ACADEMIC_YEAR_START_MONTH
    return max(1, min(months // 6 + 1, total_semesters(degree)))


def validate_group(start_year: int, degree: str, department: str, section: str):
    this_year = date.today().year
    if degree not in DEGREES:
        raise HTTPException(400, "Choose a valid degree.")
    if department not in DEPARTMENTS:
        raise HTTPException(400, "Choose a valid department.")
    if section not in SECTIONS:
        raise HTTPException(400, "Choose a valid section.")
    if not (this_year - 8 <= start_year <= this_year + 1):
        raise HTTPException(400, "Choose a valid batch start year.")
