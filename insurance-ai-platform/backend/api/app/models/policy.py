import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import PolicyStatus

policy_status_enum = ENUM(PolicyStatus, name="policy_status", create_type=False)


class Policy(Base):
    __tablename__ = "policies"

    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.member_id"), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(150), nullable=False)
    coverage_type: Mapped[str] = mapped_column(String(50), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    premium_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    deductible_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    out_of_pocket_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[PolicyStatus] = mapped_column(policy_status_enum, nullable=False, default=PolicyStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
