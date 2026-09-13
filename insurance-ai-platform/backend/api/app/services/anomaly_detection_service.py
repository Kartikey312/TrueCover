"""Statistical outlier detection for a claim's billed_amount, compared
against previously decided claims of the same claim type. This is a
shallow signal (a z-score against historical mean/stddev) rather than a
learned fraud model, but it is real, data-driven anomaly detection --
distinct from the hardcoded fraud rule it sits alongside -- and it gets
more accurate as more claims are decided, entirely from data already in
Postgres.

Needs a minimum sample size before it says anything: "3 standard
deviations from the mean of 2 samples" is noise, not a finding, so too
little history yields no signal at all rather than a guess.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.claim import Claim
from app.models.enums import ClaimType, FinalDecisionStatus

MIN_SAMPLE_SIZE = 5
Z_SCORE_THRESHOLD = 3.0


async def detect_billed_amount_anomaly(
    db: AsyncSession,
    *,
    claim_id: UUID,
    claim_type: ClaimType,
    billed_amount: Decimal | None,
) -> list[dict[str, Any]]:
    """Returns a single-item context list, or an empty one when there's no
    billed_amount to judge or not enough decided historical claims of this
    type to say anything meaningful -- never a false "not an outlier".
    """
    if billed_amount is None:
        return []

    stats = await db.execute(
        select(
            func.count(Claim.claim_id),
            func.avg(Claim.billed_amount),
            func.stddev_samp(Claim.billed_amount),
        ).where(
            Claim.claim_type == claim_type,
            Claim.claim_id != claim_id,
            Claim.final_decision != FinalDecisionStatus.pending,
            Claim.billed_amount.is_not(None),
        )
    )
    count, mean, stddev = stats.one()

    if not count or count < MIN_SAMPLE_SIZE or not stddev:
        return []

    z_score = float((billed_amount - mean) / stddev)
    is_outlier = abs(z_score) >= Z_SCORE_THRESHOLD

    return [
        {
            "source": "amount_anomaly",
            "is_outlier": is_outlier,
            "z_score": round(z_score, 2),
            "sample_size": count,
            "historical_mean": str(round(mean, 2)),
        }
    ]
