"""Face encoding + matching using the free, open-source `face_recognition` library (dlib)."""
import io
import numpy as np
import face_recognition
from PIL import Image, ImageOps
from .config import FACE_TOLERANCE, FACE_MIN_AREA_RATIO


def _load(data: bytes) -> np.ndarray:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((800, 800))  # keeps matching fast
    return np.array(img)


def encode_profile_photo(data: bytes) -> list:
    """Profile photos must contain exactly one clear face."""
    arr = _load(data)
    locations = face_recognition.face_locations(arr)
    if len(locations) != 1:
        raise ValueError(f"Expected exactly 1 face but found {len(locations)}.")
    top, right, bottom, left = locations[0]
    height, width = arr.shape[:2]
    ratio = ((bottom - top) * (right - left)) / (height * width)
    if ratio < FACE_MIN_AREA_RATIO:
        raise ValueError(f"Your face covers only {ratio * 100:.0f}% of the photo. Move closer so your face fills most of the frame.")
    return [round(float(x), 6) for x in face_recognition.face_encodings(arr, locations)[0]]


def recognize(data: bytes, known: dict) -> list:
    """known: {student_id: [np.ndarray, ...]}. Returns the student ids found in the frame."""
    arr = _load(data)
    locations = face_recognition.face_locations(arr)
    found = set()
    for enc in face_recognition.face_encodings(arr, locations):
        best_id, best_dist = None, FACE_TOLERANCE
        for sid, encs in known.items():
            d = float(face_recognition.face_distance(encs, enc).min())
            if d < best_dist:
                best_id, best_dist = sid, d
        if best_id is not None:
            found.add(best_id)
    return list(found)
