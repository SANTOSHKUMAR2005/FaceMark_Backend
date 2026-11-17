"""Photo storage: Google Cloud Storage when GCS_BUCKET is set, otherwise a local folder."""
import os
import uuid
from datetime import timedelta
from .config import GCS_BUCKET

LOCAL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")


def _bucket():
    from google.cloud import storage
    return storage.Client().bucket(GCS_BUCKET)


def save_photo(data: bytes, student_id: int, content_type: str = "image/jpeg") -> str:
    name = f"students/{student_id}/{uuid.uuid4().hex}.jpg"
    if GCS_BUCKET:
        _bucket().blob(name).upload_from_string(data, content_type=content_type)
    else:
        path = os.path.join(LOCAL_DIR, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return name


def delete_photo(name: str):
    try:
        if GCS_BUCKET:
            _bucket().blob(name).delete()
        else:
            os.remove(os.path.join(LOCAL_DIR, name))
    except Exception:
        pass


def photo_url(name: str) -> str:
    if GCS_BUCKET:  # private bucket -> temporary signed link
        return _bucket().blob(name).generate_signed_url(version="v4", expiration=timedelta(hours=1))
    return f"/uploads/{name}"
