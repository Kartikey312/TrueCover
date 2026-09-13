import uuid
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings


def extract_text(storage_path: str, mime_type: str | None) -> str | None:
    """Best-effort text extraction for claim intake (Phase 2: text/PDF
    only -- a PDF with embedded text, or a plain-text file). Scanned/
    image-only documents need real OCR, which stays out of scope until
    this path is proven reliable; they're just not extractable here.
    Never raises -- a bad or unsupported file just yields no text, same
    as a document nobody uploaded.
    """
    path = Path(storage_path)

    if mime_type == "application/pdf":
        try:
            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
            return text or None
        except (PdfReadError, OSError):
            return None

    if mime_type and mime_type.startswith("text/"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
            return text or None
        except OSError:
            return None

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
