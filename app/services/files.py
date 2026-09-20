"""Protected employee and request document storage helpers."""

from pathlib import Path
import secrets

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.datastructures import FileStorage


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024


def store_uploaded_file(file: FileStorage, prefix: str):
    """Validate and save a document under an unpredictable, private filename."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF, PNG, JPG and WebP documents are allowed.")
    payload = file.read()
    if not payload or len(payload) > MAX_DOCUMENT_SIZE:
        raise ValueError("Choose a document smaller than 10 MB.")

    folder = Path(current_app.instance_path) / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{prefix}_{secrets.token_urlsafe(18)}{suffix}"
    target = folder / filename
    if suffix == ".pdf":
        if not payload.startswith(b"%PDF-"):
            raise ValueError("The uploaded PDF is not valid.")
        target.write_bytes(payload)
        return filename, "application/pdf", len(payload)

    try:
        from io import BytesIO

        image = Image.open(BytesIO(payload)).convert("RGB")
        image.thumbnail((2400, 2400))
        filename = Path(filename).with_suffix(".webp").name
        target = folder / filename
        image.save(target, "WEBP", quality=85, method=6)
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("The uploaded image is not valid.") from error
    return filename, "image/webp", target.stat().st_size


def store_profile_photo(file: FileStorage, prefix: str):
    """Store a profile portrait using the same private image validation path.

    PDFs are acceptable employee documents but never valid profile photographs.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("Choose a PNG, JPG or WebP profile photo.")
    return store_uploaded_file(file, prefix)


def remove_private_profile_photo(stored_name: str | None):
    """Remove a private portrait without accepting an arbitrary filesystem path."""
    if not stored_name or Path(stored_name).name != stored_name:
        return
    target = Path(current_app.instance_path) / "uploads" / stored_name
    try:
        target.unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Could not remove private profile photo: %s", stored_name)


def remove_private_upload(stored_name: str | None):
    """Remove one known private upload without accepting a filesystem path."""
    if not stored_name or Path(stored_name).name != stored_name:
        return
    try:
        (Path(current_app.instance_path) / "uploads" / stored_name).unlink(missing_ok=True)
    except OSError:
        current_app.logger.warning("Could not remove private upload: %s", stored_name)
