import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings


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
