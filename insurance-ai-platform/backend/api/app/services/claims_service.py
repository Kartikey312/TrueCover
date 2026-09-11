import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_recommendation import AIRecommendation
from app.models.audit_event import AuditEvent
from app.models.claim import Claim
from app.models.claim_document import ClaimDocument
from app.models.enums import (
    ActorType,
    AIRecommendationStatus,
    ClaimStatus,
    DocumentType,
    FinalDecisionStatus,
)
from app.models.member import Member
from app.models.policy import Policy
from app.models.provider import ProviderHospital
from app.schemas.claim import ClaimCreate
from app.schemas.decision import ClaimDecisionCreate
from app.services import audit_service


async def _next_claim_number(db: AsyncSession) -> str:
    year = datetime.now(timezone.utc).year
    result = await db.execute(select(func.nextval("claim_number_seq")))
    seq = result.scalar_one()
    return f"CLM-{year}-{seq:06d}"


async def create_claim(db: AsyncSession, payload: ClaimCreate) -> Claim:
    member = await db.get(Member, payload.member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Member {payload.member_id} not found")

    policy = await db.get(Policy, payload.policy_id)
    if policy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Policy {payload.policy_id} not found")
    if policy.member_id != payload.member_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Policy does not belong to this member")

    if payload.provider_id is not None:
        provider = await db.get(ProviderHospital, payload.provider_id)
        if provider is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Provider {payload.provider_id} not found")

    claim = Claim(
        claim_number=await _next_claim_number(db),
        member_id=payload.member_id,
        policy_id=payload.policy_id,
        provider_id=payload.provider_id,
        claim_type=payload.claim_type,
        date_of_service=payload.date_of_service,
        billed_amount=payload.billed_amount,
        status=ClaimStatus.submitted,
        final_decision=FinalDecisionStatus.pending,
    )
    db.add(claim)
    await db.flush()

    await audit_service.record_event(
        db,
        entity_type="claim",
        entity_id=claim.claim_id,
        event_type="claim_created",
        actor_type=ActorType.user,
        description=f"Claim {claim.claim_number} submitted for member {member.member_number}",
        new_value={"status": claim.status.value, "final_decision": claim.final_decision.value},
    )

    await db.commit()
    await db.refresh(claim)
    return claim


async def get_claim(db: AsyncSession, claim_id: uuid.UUID) -> Claim:
    claim = await db.get(Claim, claim_id)
    if claim is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Claim {claim_id} not found")
    return claim


async def add_document(
    db: AsyncSession,
    claim_id: uuid.UUID,
    *,
    document_type: DocumentType,
    file_name: str,
    storage_path: str,
    mime_type: str | None,
    file_size_bytes: int | None,
    uploaded_by: uuid.UUID | None,
) -> ClaimDocument:
    claim = await get_claim(db, claim_id)

    document = ClaimDocument(
        claim_id=claim.claim_id,
        document_type=document_type,
        file_name=file_name,
        storage_path=storage_path,
        mime_type=mime_type,
        file_size_bytes=file_size_bytes,
        uploaded_by=uploaded_by,
    )
    db.add(document)
    await db.flush()

    await audit_service.record_event(
        db,
        entity_type="claim",
        entity_id=claim.claim_id,
        event_type="document_uploaded",
        actor_type=ActorType.user if uploaded_by else ActorType.system,
        actor_id=uploaded_by,
        description=f"Document '{file_name}' ({document_type.value}) uploaded",
        new_value={"document_id": str(document.document_id), "file_name": file_name},
    )

    await db.commit()
    await db.refresh(document)
    return document


async def get_timeline(db: AsyncSession, claim_id: uuid.UUID) -> list[AuditEvent]:
    await get_claim(db, claim_id)

    result = await db.execute(
        select(AuditEvent)
        .where(AuditEvent.entity_type == "claim", AuditEvent.entity_id == claim_id)
        .order_by(AuditEvent.created_at.asc())
    )
    return list(result.scalars().all())


async def record_decision(db: AsyncSession, claim_id: uuid.UUID, payload: ClaimDecisionCreate) -> Claim:
    claim = await get_claim(db, claim_id)

    if payload.final_decision == FinalDecisionStatus.pending:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "final_decision must be 'approved', 'denied', or 'partially_approved'",
        )

    previous_status = claim.status
    previous_decision = claim.final_decision

    claim.final_decision = payload.final_decision
    claim.final_decision_reason = payload.reason
    claim.final_decision_at = datetime.now(timezone.utc)
    claim.approved_amount = payload.approved_amount
    if payload.final_decision == FinalDecisionStatus.approved:
        claim.status = ClaimStatus.approved
    elif payload.final_decision == FinalDecisionStatus.denied:
        claim.status = ClaimStatus.denied
    else:
        claim.status = ClaimStatus.closed

    result = await db.execute(
        select(AIRecommendation)
        .where(
            AIRecommendation.claim_id == claim_id,
            AIRecommendation.status == AIRecommendationStatus.pending_review,
        )
        .order_by(AIRecommendation.created_at.desc())
        .limit(1)
    )
    recommendation = result.scalar_one_or_none()
    if recommendation is not None:
        matches = (
            payload.final_decision == FinalDecisionStatus.approved
            and recommendation.recommendation_type.value == "approve"
        ) or (
            payload.final_decision == FinalDecisionStatus.denied
            and recommendation.recommendation_type.value == "deny"
        )
        recommendation.status = AIRecommendationStatus.accepted if matches else AIRecommendationStatus.overridden
        recommendation.reviewed_by = payload.decided_by
        recommendation.reviewed_at = datetime.now(timezone.utc)

    await audit_service.record_event(
        db,
        entity_type="claim",
        entity_id=claim.claim_id,
        event_type="decision_recorded",
        actor_type=ActorType.user,
        actor_id=payload.decided_by,
        description=payload.reason,
        old_value={"status": previous_status.value, "final_decision": previous_decision.value},
        new_value={"status": claim.status.value, "final_decision": claim.final_decision.value},
    )

    await db.commit()
    await db.refresh(claim)
    return claim


async def get_latest_recommendation(db: AsyncSession, claim_id: uuid.UUID) -> AIRecommendation:
    await get_claim(db, claim_id)

    result = await db.execute(
        select(AIRecommendation)
        .where(AIRecommendation.claim_id == claim_id)
        .order_by(AIRecommendation.created_at.desc())
        .limit(1)
    )
    recommendation = result.scalar_one_or_none()
    if recommendation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No AI recommendation exists for this claim yet")
    return recommendation
