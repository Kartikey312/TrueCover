import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DocumentType

document_type_enum = ENUM(DocumentType, name="document_type", create_type=False)


class ClaimDocument(Base):
    __tablename__ = "claim_documents"

    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claims.claim_id", ondelete="CASCADE"), nullable=False
    )
    document_type: Mapped[DocumentType] = mapped_column(document_type_enum, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    # Text pulled from a PDF/text upload at intake time (see
    # storage_service.extract_text) -- feeds extraction_node's
    # document_text field. Null for images/unsupported types or when
    # nothing could be extracted.
    ocr_extracted_text: Mapped[str | None] = mapped_column(Text)
    # Pointer only -- the embedding itself lives in Qdrant. Postgres remains
    # the source of truth for what documents exist on a claim.
    qdrant_point_id: Mapped[str | None] = mapped_column(String(255))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.user_id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
