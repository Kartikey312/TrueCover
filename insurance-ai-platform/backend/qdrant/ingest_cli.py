"""CLI entry point for uploading a policy document PDF into Qdrant.

Usage:
    python -m qdrant.ingest_cli path/to/document.pdf \\
        --plan-id GOLD-PPO-2026 --state CA \\
        --effective-date 2026-01-01 --document-type policy_certificate
"""

import argparse
from datetime import date
from pathlib import Path

from .client import ensure_collection, get_client
from .ingestion import ingest_policy_document
from .models import POLICY_DOCUMENT_TYPES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path, help="Path to the policy document PDF.")
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--state", required=True, help="Two-letter state code this document applies to.")
    parser.add_argument("--effective-date", required=True, type=date.fromisoformat, help="YYYY-MM-DD")
    parser.add_argument("--document-type", required=True, choices=POLICY_DOCUMENT_TYPES)
    parser.add_argument("--qdrant-url", default=None, help="Qdrant server URL. Omit to use local on-disk storage.")
    args = parser.parse_args()

    client = get_client(url=args.qdrant_url, path=None if args.qdrant_url else "./qdrant_storage")
    ensure_collection(client)

    chunk_count = ingest_policy_document(
        client,
        args.pdf_path.read_bytes(),
        plan_id=args.plan_id,
        state=args.state,
        effective_date=args.effective_date,
        document_type=args.document_type,
        source_document=args.pdf_path.name,
    )

    print(f"Ingested {chunk_count} chunk(s) from {args.pdf_path.name}.")


if __name__ == "__main__":
    main()
