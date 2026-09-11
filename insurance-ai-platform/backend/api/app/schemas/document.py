import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentType


class ClaimDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    claim_id: uuid.UUID
    document_type: DocumentType
    file_name: str
    storage_path: str
    mime_type: str | None
    file_size_bytes: int | None
    uploaded_by: uuid.UUID | None
    uploaded_at: datetime
