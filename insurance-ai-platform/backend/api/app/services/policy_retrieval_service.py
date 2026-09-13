"""Bridges a claim's policy record to the Qdrant-backed policy-retrieval
package (backend/qdrant), so the graph's retrieval_node can be handed real
policy-document context instead of its deterministic placeholder.

The Qdrant schema was designed around plan_id/state, but the current
Postgres schema has neither: policies only carry a free-text plan_name,
and nothing tracks a member's state. As a phase-1 simplification,
plan_name is slugified into a plan_id and every policy document is
treated as applying nationwide ("ALL"). Ingesting a real per-state
document set just means using more specific plan_id/state values at
ingest time -- this module's contract doesn't need to change.

Retrieval failures (Qdrant unreachable, collection missing, embedding
model unavailable) must never break claim submission: they're caught and
logged here, and the caller falls back to retrieval_node's built-in
placeholder by treating a None return as "no context available."
"""

import logging
import re
from functools import lru_cache

from qdrant_client import QdrantClient

from app.config import settings

from qdrant.client import get_client
from qdrant.retrieval import retrieve_policy_context

logger = logging.getLogger(__name__)

NATIONWIDE_STATE = "ALL"


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    return get_client(url=settings.qdrant_url)


def plan_id_for(plan_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", plan_name.lower()).strip("-") or "unknown-plan"


def fetch_policy_context(*, plan_name: str, claim_type: str) -> list[dict] | None:
    """Returns Qdrant chunks relevant to this plan/claim type, or None if
    retrieval could not run at all (so the caller falls back to a
    placeholder). An empty list is a real "nothing found" answer.
    """
    try:
        chunks = retrieve_policy_context(
            _client(),
            query=f"coverage rules and exclusions for {claim_type} claims",
            plan_id=plan_id_for(plan_name),
            state=NATIONWIDE_STATE,
        )
    except Exception:
        logger.warning("Policy retrieval from Qdrant failed; falling back to placeholder context.", exc_info=True)
        return None

    return [dict(chunk) for chunk in chunks]
