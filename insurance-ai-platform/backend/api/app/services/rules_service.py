"""Hospital/global rule authoring and the compliance-approval gate.

A rule can never reach status='active' without a recorded approval from a
user whose role is compliance_officer -- that check is enforced here, at
the one place activation happens, not left to callers to remember.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ActorType, ApprovalStatus, RuleStatus, UserRole
from app.models.rule import Rule
from app.models.rule_approval import RuleApproval
from app.models.user import User
from app.schemas.rule import RuleApprovalCreate, RuleCreate
from app.services import audit_service


async def create_rule(db: AsyncSession, payload: RuleCreate, created_by: uuid.UUID) -> Rule:
    if payload.provider_id is not None:
        from app.models.provider import ProviderHospital

        provider = await db.get(ProviderHospital, payload.provider_id)
        if provider is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"Provider {payload.provider_id} not found")

    existing_max_version = await db.execute(
        select(func.max(Rule.version)).where(Rule.rule_code == payload.rule_code)
    )
    next_version = (existing_max_version.scalar_one_or_none() or 0) + 1

    rule = Rule(
        rule_code=payload.rule_code,
        rule_name=payload.rule_name,
        description=payload.description,
        rule_type=payload.rule_type,
        provider_id=payload.provider_id,
        rule_definition=payload.rule_definition.model_dump(),
        version=next_version,
        status=RuleStatus.draft,
        priority=payload.priority,
        created_by=created_by,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    db.add(rule)
    await db.flush()

    await audit_service.record_event(
        db,
        entity_type="rule",
        entity_id=rule.rule_id,
        event_type="rule_created",
        actor_type=ActorType.user,
        actor_id=created_by,
        description=f"Rule {rule.rule_code} v{rule.version} created as draft.",
        new_value={"status": rule.status.value, "version": rule.version},
    )

    await db.commit()
    await db.refresh(rule)
    return rule


async def get_rule(db: AsyncSession, rule_id: uuid.UUID) -> Rule:
    rule = await db.get(Rule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Rule {rule_id} not found")
    return rule


async def list_rules(db: AsyncSession, provider_id: uuid.UUID | None = None) -> list[Rule]:
    query = select(Rule).order_by(Rule.rule_code, Rule.version.desc())
    if provider_id is not None:
        query = query.where(Rule.provider_id == provider_id)
    return list((await db.execute(query)).scalars().all())


async def _get_rule_at_version(db: AsyncSession, rule_id: uuid.UUID, version: int) -> Rule:
    rule = await get_rule(db, rule_id)
    if rule.version != version:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Rule {rule_id} is at version {rule.version}, not {version}.",
        )
    return rule


async def submit_for_approval(db: AsyncSession, rule_id: uuid.UUID, version: int, submitted_by: uuid.UUID) -> Rule:
    rule = await _get_rule_at_version(db, rule_id, version)

    if rule.status != RuleStatus.draft:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Rule {rule_id} v{version} is '{rule.status.value}', not 'draft'."
        )

    rule.status = RuleStatus.pending_approval

    await audit_service.record_event(
        db,
        entity_type="rule",
        entity_id=rule.rule_id,
        event_type="rule_submitted_for_approval",
        actor_type=ActorType.user,
        actor_id=submitted_by,
        description=f"Rule {rule.rule_code} v{rule.version} submitted for compliance approval.",
        new_value={"status": rule.status.value},
    )

    await db.commit()
    await db.refresh(rule)
    return rule


async def record_approval(
    db: AsyncSession, rule_id: uuid.UUID, version: int, approver_id: uuid.UUID, payload: RuleApprovalCreate
) -> RuleApproval:
    rule = await _get_rule_at_version(db, rule_id, version)

    if rule.status != RuleStatus.pending_approval:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Rule {rule_id} v{version} is '{rule.status.value}', not 'pending_approval'.",
        )

    approver = await db.get(User, approver_id)

    if payload.approval_status == "approved" and approver.role != UserRole.compliance_officer:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only a compliance officer can approve a rule.",
        )

    approval = RuleApproval(
        rule_id=rule_id,
        rule_version=version,
        approver_id=approver_id,
        approval_status=ApprovalStatus(payload.approval_status),
        comments=payload.comments,
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(approval)

    if payload.approval_status == "rejected":
        rule.status = RuleStatus.rejected
    elif payload.approval_status == "changes_requested":
        rule.status = RuleStatus.draft
    # "approved" does not change rule.status -- activation is a separate,
    # explicit step (see activate_rule).

    await audit_service.record_event(
        db,
        entity_type="rule",
        entity_id=rule.rule_id,
        event_type="rule_approval_recorded",
        actor_type=ActorType.user,
        actor_id=approver_id,
        description=(
            f"{approver.full_name} recorded '{payload.approval_status}' for rule "
            f"{rule.rule_code} v{version}."
        ),
        new_value={"approval_status": payload.approval_status, "rule_status": rule.status.value},
    )

    await db.commit()
    await db.refresh(approval)
    return approval


async def activate_rule(db: AsyncSession, rule_id: uuid.UUID, version: int, activated_by: uuid.UUID) -> Rule:
    """The compliance gate. Whoever calls this -- an engineer, a hospital
    user, anyone with API access -- activation only succeeds if a
    compliance_officer has recorded an 'approved' approval for this exact
    rule version. The caller's own identity/role is irrelevant; what's
    checked is whether a genuine compliance sign-off exists.
    """
    rule = await _get_rule_at_version(db, rule_id, version)

    if rule.status != RuleStatus.pending_approval:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Rule {rule_id} v{version} is '{rule.status.value}', not 'pending_approval'.",
        )

    approval_result = await db.execute(
        select(RuleApproval)
        .join(User, User.user_id == RuleApproval.approver_id)
        .where(
            RuleApproval.rule_id == rule_id,
            RuleApproval.rule_version == version,
            RuleApproval.approval_status == ApprovalStatus.approved,
            User.role == UserRole.compliance_officer,
        )
        .order_by(RuleApproval.reviewed_at.desc())
        .limit(1)
    )
    approval = approval_result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This rule cannot be activated: no compliance officer has approved this version.",
        )

    # Activating a new version supersedes whatever was previously active
    # for this rule_code -- only one version should be live at a time.
    previously_active = await db.execute(
        select(Rule).where(Rule.rule_code == rule.rule_code, Rule.status == RuleStatus.active)
    )
    for old_rule in previously_active.scalars().all():
        old_rule.status = RuleStatus.deprecated
        await audit_service.record_event(
            db,
            entity_type="rule",
            entity_id=old_rule.rule_id,
            event_type="rule_deprecated",
            actor_type=ActorType.system,
            description=f"Superseded by {rule.rule_code} v{rule.version}.",
            new_value={"status": old_rule.status.value},
        )

    rule.status = RuleStatus.active
    rule.approved_by = approval.approver_id

    await audit_service.record_event(
        db,
        entity_type="rule",
        entity_id=rule.rule_id,
        event_type="rule_activated",
        actor_type=ActorType.user,
        actor_id=activated_by,
        description=f"Rule {rule.rule_code} v{rule.version} activated.",
        new_value={"status": rule.status.value, "approved_by": str(approval.approver_id)},
    )

    await db.commit()
    await db.refresh(rule)
    return rule


async def get_active_rules_for_provider(db: AsyncSession, provider_id: uuid.UUID | None) -> list[dict]:
    """Active global rules plus (if given) this hospital's active rules,
    serialized to the JSON-safe shape rule_from_dict() expects on the
    graph side.
    """
    conditions = [Rule.provider_id.is_(None)]
    if provider_id is not None:
        conditions.append(Rule.provider_id == provider_id)

    result = await db.execute(select(Rule).where(Rule.status == RuleStatus.active, or_(*conditions)))
    rules = result.scalars().all()

    return [
        {
            "rule_id": str(rule.rule_id),
            "rule_code": rule.rule_code,
            "rule_type": rule.rule_type.value,
            "version": rule.version,
            "priority": rule.priority,
            "source": "hospital" if rule.provider_id else "global",
            "condition": rule.rule_definition["condition"],
            "action": rule.rule_definition["action"],
            "reason": rule.rule_definition.get("reason", rule.rule_name),
            "effective_from": rule.effective_from.isoformat() if rule.effective_from else None,
            "effective_to": rule.effective_to.isoformat() if rule.effective_to else None,
        }
        for rule in rules
    ]
