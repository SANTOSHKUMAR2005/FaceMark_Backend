import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/attendance_db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TEACHER_SIGNUP_CODE = os.getenv("TEACHER_SIGNUP_CODE", "TEACHER123")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
# Only these email domains may register / log in, e.g. ALLOWED_EMAIL_DOMAINS=college.edu,student.college.edu
# Leave empty to allow any email.
ALLOWED_EMAIL_DOMAINS = [d.strip().lower().lstrip("@") for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",") if d.strip()]
ACCESS_TOKEN_HOURS = 12
FACE_TOLERANCE = 0.5  # lower = stricter matching

# Email (SendGrid). Leave SENDGRID_API_KEY empty to print codes in the backend console instead (for testing).
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Face Attendance")
CODE_EXPIRE_MINUTES = 10
CODE_MAX_ATTEMPTS = 5
CODE_RESEND_SECONDS = 60

# The admin account is created automatically at startup from these two values.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# A profile photo is rejected if the face covers less than this share of the picture (0.12 = 12%).
FACE_MIN_AREA_RATIO = float(os.getenv("FACE_MIN_AREA_RATIO", "0.12"))
 