"""Dropdown options."""

# Degree -> duration in years (B.Tech = 4, B.Tech + M.Tech = 5, M.Tech = 2)
DEGREES = {"B.Tech": 4, "B.Tech + M.Tech": 5, "M.Tech": 2}

DEPARTMENTS = [
    "Computer Science",
    "Electronics and Communication Engineering",
    "Electrical Engineering",
    "Machanical Engineering",
    "Civil Engineering",
    "Material Science",
    "Other"
]

SECTIONS = ["A", "B", "C", "D"]

# Month (1-12) in which a new batch starts and semester 1 begins. 7 = July.
# Semesters then change every 6 months (odd: Jul-Dec, even: Jan-Jun).
ACADEMIC_YEAR_START_MONTH = 7
