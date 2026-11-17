"""Sends email through the SendGrid HTTP API (no extra package needed)."""
import json
import urllib.request
import urllib.error
from fastapi import HTTPException
from .config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME


def send_email(to: str, subject: str, text: str, html: str):
    if not SENDGRID_API_KEY:  # test mode: show the message in the backend console
        print(f"\n[EMAIL - SendGrid key not set] To: {to}\nSubject: {subject}\n{text}\n")
        return
    if not SENDGRID_FROM_EMAIL:
        raise HTTPException(500, "Email is not configured: set SENDGRID_FROM_EMAIL in .env.")
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": SENDGRID_FROM_EMAIL, "name": SENDGRID_FROM_NAME},
        "subject": subject,
        "content": [{"type": "text/plain", "value": text}, {"type": "text/html", "value": html}],
    }
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send", data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as e:
        print("SendGrid error:", e.code, e.read().decode(errors="ignore"))
        raise HTTPException(502, "Could not send the email. Please try again in a moment.")
    except Exception as e:
        print("SendGrid error:", e)
        raise HTTPException(502, "Could not send the email. Please try again in a moment.")
