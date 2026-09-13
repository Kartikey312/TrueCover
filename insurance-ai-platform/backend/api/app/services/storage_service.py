import logging
import uuid
from pathlib import Path

import pytesseract
from fastapi import UploadFile
from pdf2image import convert_from_path
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings

logger = logging.getLogger(__name__)

IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp"}


def _ocr_image(path: Path) -> str | None:
    """Runs Tesseract OCR on a single image file. Never raises -- a
    corrupt image, an unreadable format, or Tesseract being unavailable
    all just yield no text, same as a document nobody uploaded.
    """
    try:
        text = pytesseract.image_to_string(str(path)).strip()
        return text or None
    except Exception:
        logger.warning("OCR failed for %s", path, exc_info=True)
        return None


def _ocr_pdf_pages(path: Path) -> str | None:
    """Rasterizes each PDF page to an image and OCRs it -- the fallback
    for a scanned/image-only PDF, where pypdf's extract_text() (built for
    a PDF's embedded text layer) returns nothing because there is none.
    """
    try:
        pages = convert_from_path(str(path))
        texts = [pytesseract.image_to_string(page).strip() for page in pages]
        text = "\n".join(t for t in texts if t).strip()
        return text or None
    except Exception:
        logger.warning("PDF OCR fallback failed for %s", path, exc_info=True)
        return None


def extract_text(storage_path: str, mime_type: str | None) -> str | None:
    """Best-effort text extraction for claim intake: embedded PDF text or
    a plain-text file first; OCR (Tesseract) for image uploads and for
    PDFs with no embedded text layer (scanned documents). Never raises --
    a bad or unsupported file just yields no text, same as a document
    nobody uploaded.
    """
    path = Path(storage_path)

    if mime_type == "application/pdf":
        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
        except (PdfReadError, OSError):
            text = ""
        return text or _ocr_pdf_pages(path)

    if mime_type and mime_type.startswith("text/"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            return text or None
        except OSError:
            return None

    if mime_type in IMAGE_MIME_TYPES:
        return _ocr_image(path)

    return None


async def save_claim_document(claim_id: uuid.UUID, upload: UploadFile) -> tuple[str, int]:
    claim_dir = Path(settings.storage_root) / "claims" / str(claim_id)
    claim_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4()}_{upload.filename}"
    destination = claim_dir / safe_name

    size = 0
    try:
        with destination.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise ValueError("File exceeds maximum allowed size")
                f.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return str(destination), size
