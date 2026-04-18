"""EXIF metadata extraction for camera trap images."""
from datetime import datetime
from pathlib import Path
from typing import Optional


def extract_image_metadata(image_path: Path) -> dict:
    """Extract EXIF metadata from a camera trap image.

    Returns dict with keys: width, height, captured_at, temperature_c, trigger_mode.
    All values are Optional — missing data returns None.
    """
    result: dict = {
        "width": None,
        "height": None,
        "captured_at": None,
        "temperature_c": None,
        "trigger_mode": None,
    }
    try:
        from PIL import Image as PILImage
        from PIL.ExifTags import TAGS

        with PILImage.open(image_path) as img:
            result["width"] = img.width
            result["height"] = img.height

            exif_data = img._getexif()
            if not exif_data:
                return result

            date_str = exif_data.get(36867) or exif_data.get(306)
            if date_str:
                result["captured_at"] = _parse_exif_date(date_str)

            maker_note = exif_data.get(37500)
            if maker_note and isinstance(maker_note, bytes):
                temp = _parse_reconyx_temperature(maker_note)
                if temp is not None:
                    result["temperature_c"] = temp
                trigger = _parse_reconyx_trigger(maker_note)
                if trigger:
                    result["trigger_mode"] = trigger

            user_comment = exif_data.get(37510)
            if user_comment and isinstance(user_comment, (str, bytes)):
                comment_str = user_comment.decode("utf-8", errors="ignore") if isinstance(user_comment, bytes) else user_comment
                if "timelapse" in comment_str.lower():
                    result["trigger_mode"] = "timelapse"
                elif "motion" in comment_str.lower():
                    result["trigger_mode"] = "motion"

    except Exception:
        pass

    return result


def _parse_exif_date(date_str: str) -> Optional[datetime]:
    """Parse EXIF date string like '2023:11:10 14:23:05'."""
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except (ValueError, AttributeError):
            continue
    return None


def _parse_reconyx_temperature(maker_note: bytes) -> Optional[float]:
    """Attempt to extract temperature from Reconyx MakerNote.

    Reconyx cameras store ambient temperature at specific byte offsets.
    This varies by firmware version; we try common offsets.
    """
    try:
        if len(maker_note) >= 50:
            for offset in (44, 46, 48):
                raw = int.from_bytes(maker_note[offset:offset + 2], byteorder="little", signed=True)
                temp_c = raw / 10.0
                if -40.0 <= temp_c <= 60.0:
                    return temp_c
    except Exception:
        pass
    return None


def _parse_reconyx_trigger(maker_note: bytes) -> Optional[str]:
    """Attempt to extract trigger mode from Reconyx MakerNote."""
    try:
        if len(maker_note) >= 12:
            trigger_byte = maker_note[10]
            if trigger_byte == 0:
                return "motion"
            elif trigger_byte == 1:
                return "timelapse"
            elif trigger_byte == 2:
                return "external"
    except Exception:
        pass
    return None
