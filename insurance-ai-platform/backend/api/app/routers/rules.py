import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.rule import (
    RuleActivateRequest,
    RuleApprovalCreate,
    RuleApprovalRead,
    RuleCreate,
    RuleRead,
)
from app.services import rules_service

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("", response_model=RuleRead, status_code=201)
async def create_rule(payload: RuleCreate, db: AsyncSession = Depends(get_db)):
    """Creates a draft rule. Global (provider_id omitted) or hospital-scoped.
    Drafts have no effect on claim processing until activated.
    """
    return await rules_service.create_rule(db, payload)


@router.get("", response_model=list[RuleRead])
async def list_rules(
    provider_id: uuid.UUID | None = Query(default=None, description="Filter to one hospital's rules."),
    db: AsyncSession = Depends(get_db),
):
    return await rules_service.list_rules(db, provider_id)


@router.get("/{rule_id}", response_model=RuleRead)
async def get_rule(rule_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await rules_service.get_rule(db, rule_id)


@router.post("/{rule_id}/versions/{version}/submit", response_model=RuleRead)
async def submit_rule_for_approval(
    rule_id: uuid.UUID,
    version: int,
    submitted_by: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    return await rules_service.submit_for_approval(db, rule_id, version, submitted_by)


@router.post("/{rule_id}/versions/{version}/approvals", response_model=RuleApprovalRead, status_code=201)
async def record_rule_approval(
    rule_id: uuid.UUID,
    version: int,
    payload: RuleApprovalCreate,
    db: AsyncSession = Depends(get_db),
):
    """Only a user with role=compliance_officer can record an 'approved'
    decision -- rejected with 403 otherwise.
    """
    return await rules_service.record_approval(db, rule_id, version, payload)


@router.post("/{rule_id}/versions/{version}/activate", response_model=RuleRead)
async def activate_rule(
    rule_id: uuid.UUID,
    version: int,
    payload: RuleActivateRequest,
    db: AsyncSession = Depends(get_db),
):
    """The compliance gate: fails with 403 unless a compliance_officer has
    already approved this exact rule version, regardless of who calls this.
    """
    return await rules_service.activate_rule(db, rule_id, version, payload.activated_by)
