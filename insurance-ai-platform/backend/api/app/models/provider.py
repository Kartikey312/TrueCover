import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import NetworkStatus, ProviderType

provider_type_enum = ENUM(ProviderType, name="provider_type", create_type=False)
network_status_enum = ENUM(NetworkStatus, name="network_status", create_type=False)


class ProviderHospital(Base):
    __tablename__ = "providers_hospitals"

    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npi_number: Mapped[str | None] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(provider_type_enum, nullable=False)
    specialty: Mapped[str | None] = mapped_column(String(150))
    network_status: Mapped[NetworkStatus] = mapped_column(
        network_status_enum, nullable=False, default=NetworkStatus.out_of_network
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
