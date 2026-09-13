"""Bridges the DB-free LangGraph pipeline (backend/graph) to real claim
data: submits a claim for AI processing, persists whatever the graph
produced (whether it paused for a human or auto-processed), builds the
adjuster review packet from Postgres, and resumes a paused graph with an
adjuster's explicit decision -- with idempotency protection so a retried
or refreshed decision can never be applied twice.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph_runtime import get_compiled_graph
from app.models.ai_recommendation import AIRecommendation
from app.models.claim import Claim
from app.models.claim_decision_request import ClaimDecisionRequest
from app.models.claim_document import ClaimDocument
from app.models.enums import (
    ActorType,
    AIRecommendationStatus,
    AIRecommendationType,
    ClaimStatus,
    FinalDecisionStatus,
)
from app.models.member import Member
from app.models.policy import Policy
from app.models.provider import ProviderHospital
from app.schemas.decision import ClaimDecisionCreate
from app.schemas.review import ClaimReviewPacket, SimilarClaimRead
from app.schemas.timeline import TimelineEvent
from app.services import audit_service
from app.services.claims_service import get_claim, get_timeline

SIMILAR_CLAIMS_LIMIT = 5


def _thread_id_for(claim_id: uuid.UUID) -> str:
    return f"claim-{claim_id}"


async def _persist_new_audit_events(
    db: AsyncSession,
    claim_id: uuid.UUID,
    audit_trail: list[dict[str, Any]],
    already_persisted: int,
) -> None:
    for event in audit_trail[already_persisted:]:
        actor_type = ActorType.user if event.get("node") == "human_review_node" else ActorType.ai_agent
        await audit_service.record_event(
            db,
            entity_type="claim",
            entity_id=claim_id,
            event_type=event.get("event_type", "graph_event"),
            actor_type=actor_type,
            description=f"[{event.get('node')}] {event.get('description', '')}",
            new_value=event.get("data") or None,
        )


async def _build_raw_input(db: AsyncSession, claim: Claim) -> dict[str, Any]:
    documents = (
        (await db.execute(select(ClaimDocument.file_name).where(ClaimDocument.claim_id == claim.claim_id)))
        .scalars()
        .all()
    )
    return {
        "claim_id": str(claim.claim_id),
        "member_id": str(claim.member_id),
        "policy_id": str(claim.policy_id),
        "provider_id": str(claim.provider_id) if claim.provider_id else None,
        "claim_type": claim.claim_type.value,
        "date_of_service": claim.date_of_service.isoformat(),
        "billed_amount": str(claim.billed_amount) if claim.billed_amount is not None else None,
        "procedure_codes": list(claim.procedure_codes or []),
        "diagnosis_codes": list(claim.diagnosis_codes or []),
        "documents": list(documents),
    }


async def submit_claim_for_review(db: AsyncSession, claim_id: uuid.UUID) -> Claim:
    """Runs the claim through the AI pipeline. Stores the graph thread id
    on the claim either way; if the graph pauses, the claim is queued for
    an adjuster and an AIRecommendation row (status=pending_review) is
    created capturing exactly what the adjuster will be shown. If the
    graph auto-processes the claim, the decision is applied immediately
    and the AIRecommendation is recorded as already accepted.
    """
    claim = await get_claim(db, claim_id)

    if claim.current_graph_thread_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "This claim has already been submitted for processing.")

    thread_id = _thread_id_for(claim_id)
    raw_input = await _build_raw_input(db, claim)

    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke({"claim_id": raw_input["claim_id"], "raw_input": raw_input}, config=config)

    claim.current_graph_thread_id = thread_id

    audit_trail = result.get("audit_trail") or []
    await _persist_new_audit_events(db, claim_id, audit_trail, already_persisted=0)

    reasoning_output = result.get("reasoning_output") or {}
    guardrail_result = result.get("guardrail_result") or {}
    extracted_data = result.get("extracted_data") or {}
    retrieved_context = result.get("retrieved_context") or []
    applicable_rules = result.get("applicable_rules") or []
    matched_rules = [r for r in applicable_rules if r.get("matched")]
    is_paused = "__interrupt__" in result

    recommendation_type_raw = reasoning_output.get("recommendation_type", "escalate")
    recommendation = AIRecommendation(
        claim_id=claim.claim_id,
        graph_thread_id=thread_id,
        recommendation_type=AIRecommendationType(recommendation_type_raw),
        confidence_score=reasoning_output.get("confidence_score"),
        reasoning=reasoning_output.get("reasoning"),
        supporting_evidence={
            "extracted_data": extracted_data,
            "policy_citations": retrieved_context,
            "guardrail_checks": guardrail_result.get("checks", []),
            "guardrail_reason": guardrail_result.get("reason"),
            "matched_rules": matched_rules,
        },
        model_name=reasoning_output.get("model_name") or "rules-engine-v1",
        status=AIRecommendationStatus.pending_review if is_paused else AIRecommendationStatus.accepted,
        reviewed_at=None if is_paused else datetime.now(timezone.utc),
    )
    db.add(recommendation)

    if is_paused:
        claim.status = ClaimStatus.pending_adjuster_review
        await audit_service.record_event(
            db,
            entity_type="claim",
            entity_id=claim.claim_id,
            event_type="paused_for_human_review",
            actor_type=ActorType.system,
            description="Graph paused; claim queued for adjuster review.",
            new_value={"graph_thread_id": thread_id},
        )
    else:
        final_outcome = result.get("final_outcome") or {}
        claim.status = ClaimStatus(final_outcome.get("claim_status", "pending_adjuster_review"))
        claim.final_decision = FinalDecisionStatus(final_outcome.get("final_decision", "pending"))
        claim.final_decision_reason = final_outcome.get("reason")
        claim.final_decision_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(claim)
    return claim


async def _get_similar_claims(db: AsyncSession, claim: Claim) -> list[Claim]:
    result = await db.execute(
        select(Claim)
        .where(
            Claim.member_id == claim.member_id,
            Claim.claim_type == claim.claim_type,
            Claim.claim_id != claim.claim_id,
        )
        .order_by(Claim.submitted_at.desc())
        .limit(SIMILAR_CLAIMS_LIMIT)
    )
    return list(result.scalars().all())


async def get_review_packet(db: AsyncSession, claim_id: uuid.UUID) -> ClaimReviewPacket:
    claim = await get_claim(db, claim_id)

    member = await db.get(Member, claim.member_id)
    policy = await db.get(Policy, claim.policy_id)
    provider = await db.get(ProviderHospital, claim.provider_id) if claim.provider_id else None

    rec_result = await db.execute(
        select(AIRecommendation)
        .where(AIRecommendation.claim_id == claim_id)
        .order_by(AIRecommendation.created_at.desc())
        .limit(1)
    )
    recommendation = rec_result.scalar_one_or_none()
    supporting_evidence = (recommendation.supporting_evidence if recommendation else None) or {}

    similar_claims = await _get_similar_claims(db, claim)
    audit_history = await get_timeline(db, claim_id)

    return ClaimReviewPacket(
        claim_id=claim.claim_id,
        claim_number=claim.claim_number,
        status=claim.status.value,
        graph_thread_id=claim.current_graph_thread_id,
        member_name=f"{member.first_name} {member.last_name}" if member else "Unknown member",
        policy_number=policy.policy_number if policy else "Unknown policy",
        provider_name=provider.name if provider else None,
        claim_type=claim.claim_type.value,
        billed_amount=claim.billed_amount,
        date_of_service=claim.date_of_service,
        extracted_fields=supporting_evidence.get("extracted_data", {}),
        policy_citations=supporting_evidence.get("policy_citations", []),
        similar_claims=[SimilarClaimRead.model_validate(c) for c in similar_claims],
        recommendation_type=recommendation.recommendation_type.value if recommendation else None,
        confidence_score=recommendation.confidence_score if recommendation else None,
        reasoning=recommendation.reasoning if recommendation else None,
        guardrail_reason=supporting_evidence.get("guardrail_reason"),
        guardrail_checks=supporting_evidence.get("guardrail_checks", []),
        matched_rules=supporting_evidence.get("matched_rules", []),
        audit_history=[TimelineEvent.model_validate(e) for e in audit_history],
    )


async def resume_claim_decision(db: AsyncSession, claim_id: uuid.UUID, payload: ClaimDecisionCreate) -> Claim:
    """Records an adjuster's decision and resumes the paused graph.

    Idempotency: a replay with the same idempotency_key and identical
    parameters returns the current claim without reprocessing. The same
    key with different parameters is rejected as a conflict, and so is a
    brand-new decision attempt against a claim that already has a final
    decision.
    """
    claim = await get_claim(db, claim_id)

    existing_request = await db.get(ClaimDecisionRequest, payload.idempotency_key)
    if existing_request is not None:
        same_request = (
            existing_request.claim_id == claim_id
            and existing_request.final_decision == payload.final_decision
            and existing_request.approved_amount == payload.approved_amount
            and existing_request.reason == payload.reason
        )
        if not same_request:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "This idempotency_key was already used with different parameters.",
            )
        return claim

    if claim.final_decision != FinalDecisionStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Claim {claim_id} already has a final decision ({claim.final_decision.value}); "
            "it cannot be decided again.",
        )

    if payload.final_decision == FinalDecisionStatus.pending:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "final_decision must not be 'pending'.")

    if not claim.current_graph_thread_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This claim has not been submitted for review yet; nothing to resume.",
        )

    graph = get_compiled_graph()
    config = {"configurable": {"thread_id": claim.current_graph_thread_id}}

    state_before = await graph.aget_state(config)
    if state_before.next != ("human_review_node",):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This claim's review is not currently awaiting a decision.",
        )
    already_persisted = len((state_before.values or {}).get("audit_trail") or [])

    result = await graph.ainvoke(
        Command(
            resume={
                "final_decision": payload.final_decision.value,
                "adjuster_id": str(payload.decided_by),
                "reason": payload.reason,
            }
        ),
        config=config,
    )

    audit_trail = result.get("audit_trail") or []
    await _persist_new_audit_events(db, claim_id, audit_trail, already_persisted=already_persisted)

    final_outcome = result.get("final_outcome") or {}
    claim.status = ClaimStatus(final_outcome.get("claim_status", "pending_adjuster_review"))
    claim.final_decision = FinalDecisionStatus(final_outcome.get("final_decision", "pending"))
    claim.final_decision_reason = final_outcome.get("reason")
    claim.final_decision_at = datetime.now(timezone.utc)
    claim.approved_amount = payload.approved_amount
    claim.assigned_adjuster_id = payload.decided_by

    rec_result = await db.execute(
        select(AIRecommendation)
        .where(
            AIRecommendation.claim_id == claim_id,
            AIRecommendation.status == AIRecommendationStatus.pending_review,
        )
        .order_by(AIRecommendation.created_at.desc())
        .limit(1)
    )
    recommendation = rec_result.scalar_one_or_none()
    if recommendation is not None:
        matches = (
            claim.final_decision == FinalDecisionStatus.approved
            and recommendation.recommendation_type == AIRecommendationType.approve
        ) or (
            claim.final_decision == FinalDecisionStatus.denied
            and recommendation.recommendation_type == AIRecommendationType.deny
        )
        recommendation.status = AIRecommendationStatus.accepted if matches else AIRecommendationStatus.overridden
        recommendation.reviewed_by = payload.decided_by
        recommendation.reviewed_at = datetime.now(timezone.utc)

    db.add(
        ClaimDecisionRequest(
            idempotency_key=payload.idempotency_key,
            claim_id=claim_id,
            adjuster_id=payload.decided_by,
            final_decision=payload.final_decision,
            approved_amount=payload.approved_amount,
            reason=payload.reason,
        )
    )

    await db.commit()
    await db.refresh(claim)
    return claim
