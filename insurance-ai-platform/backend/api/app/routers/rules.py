import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.rule import (
    RuleApprovalCreate,
    RuleApprovalRead,
    RuleCreate,
    RuleRead,
)
from app.services import rules_service

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("", response_model=RuleRead, status_code=201)
async def create_rule(
    payload: RuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Creates a draft rule. Global (provider_id omitted) or hospital-scoped.
    Drafts have no effect on claim processing until activated.
    """
    return await rules_service.create_rule(db, payload, current_user.user_id)


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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rules_service.submit_for_approval(db, rule_id, version, current_user.user_id)


@router.post("/{rule_id}/versions/{version}/approvals", response_model=RuleApprovalRead, status_code=201)
async def record_rule_approval(
    rule_id: uuid.UUID,
    version: int,
    payload: RuleApprovalCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Only a user with role=compliance_officer can record an 'approved'
    decision -- rejected with 403 otherwise. Who recorded it is always the
    authenticated caller, never a client-supplied id.
    """
    return await rules_service.record_approval(db, rule_id, version, current_user.user_id, payload)


@router.post("/{rule_id}/versions/{version}/activate", response_model=RuleRead)
async def activate_rule(
    rule_id: uuid.UUID,
    version: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The compliance gate: fails with 403 unless a compliance_officer has
    already approved this exact rule version, regardless of who calls this.
    """
    return await rules_service.activate_rule(db, rule_id, version, current_user.user_id)
