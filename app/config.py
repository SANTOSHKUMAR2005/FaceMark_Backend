import os
from dotenv import load_dotenv

load_dotenv()

# DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/attendance_db")
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
TEACHER_SIGNUP_CODE = os.getenv("TEACHER_SIGNUP_CODE", "TEACHER123")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
ACCESS_TOKEN_HOURS = 12
FACE_TOLERANCE = 0.5  # lower = stricter matching

# Email (SendGrid). Leave SENDGRID_API_KEY empty to print codes in the backend console instead (for testing).
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Face Attendance")
CODE_EXPIRE_MINUTES = 10
CODE_MAX_ATTEMPTS = 5
CODE_RESEND_SECONDS = 60

# Allowed domins
ALLOWED_EMAIL_DOMAINS=[d.strip().lower().lstrip("@") for d in os.getenv("ALLOWED_EMAIL_DOMAINS","").split(",") if d.strip()]
