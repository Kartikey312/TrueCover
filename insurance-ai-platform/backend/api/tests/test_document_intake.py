"""Phase 2: text/PDF claim intake. A claim can be created with minimal
structured fields and have the rest filled in from an uploaded document's
text at submit time -- through the real API + graph + Postgres, not a
mocked extraction step.
"""

import io

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

INVOICE_TEXT = """\
City General Hospital
Patient Invoice

Claim Type: Dental
Date of Service: 08/01/2026
Procedure Codes: D1110
Total Billed: $100.00
"""


def _make_pdf_bytes(lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    y = 750
    for line in lines:
        pdf.drawString(72, y, line)
        y -= 16
    pdf.save()
    return buffer.getvalue()


async def _create_minimal_claim(client, seed, claim_type="dental"):
    response = await client.post(
        "/claims",
        json={
            "member_id": seed.member_id,
            "policy_id": seed.policy_id,
            "provider_id": seed.provider_id,
            "claim_type": claim_type,
            "date_of_service": "2026-08-01",
        },
    )
    assert response.status_code == 201, response.text
    claim = response.json()
    assert claim["procedure_codes"] == []
    assert claim["billed_amount"] is None
    return claim


async def test_claim_can_be_created_without_procedure_codes_or_amount(client, seed):
    await _create_minimal_claim(client, seed)


async def test_text_document_fills_missing_fields_and_auto_processes(client, seed):
    claim = await _create_minimal_claim(client, seed)

    upload = await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.txt", INVOICE_TEXT.encode(), "text/plain")},
    )
    assert upload.status_code == 201

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "approved"
    assert body["final_decision"] == "approved"

    review = (await client.get(f"/claims/{claim['claim_id']}/review")).json()
    assert review["extracted_fields"]["billed_amount"] == "100.00"
    assert review["extracted_fields"]["procedure_codes"] == ["D1110"]


async def test_pdf_document_fills_missing_fields_and_auto_processes(client, seed):
    claim = await _create_minimal_claim(client, seed, claim_type="vision")
    pdf_bytes = _make_pdf_bytes(
        [
            "City General Hospital",
            "Patient Invoice",
            "",
            "Claim Type: Vision",
            "Date of Service: 2026-08-01",
            "Procedure Codes: 92014",
            "Total Billed: $80.00",
        ]
    )

    upload = await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload.status_code == 201

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "approved"

    review = (await client.get(f"/claims/{claim['claim_id']}/review")).json()
    assert review["extracted_fields"]["billed_amount"] == "80.00"
    assert review["extracted_fields"]["procedure_codes"] == ["92014"]


async def test_explicit_fields_are_never_overridden_by_document_text(client, seed):
    response = await client.post(
        "/claims",
        json={
            "member_id": seed.member_id,
            "policy_id": seed.policy_id,
            "provider_id": seed.provider_id,
            "claim_type": "dental",
            "date_of_service": "2026-08-01",
            "billed_amount": "50.00",
            "procedure_codes": ["D0120"],
        },
    )
    claim = response.json()

    # This document, if trusted, would overwrite both fields with
    # different values -- it must not.
    await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.txt", INVOICE_TEXT.encode(), "text/plain")},
    )
    await client.post(f"/claims/{claim['claim_id']}/submit")

    review = (await client.get(f"/claims/{claim['claim_id']}/review")).json()
    assert review["extracted_fields"]["billed_amount"] == "50.00"
    assert review["extracted_fields"]["procedure_codes"] == ["D0120"]


async def test_document_with_no_useful_fields_still_requires_human_review(client, seed):
    claim = await _create_minimal_claim(client, seed)

    await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "other"},
        files={"file": ("note.txt", b"Thanks for visiting our clinic!", "text/plain")},
    )

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_adjuster_review"

    timeline = (await client.get(f"/claims/{claim['claim_id']}/timeline")).json()
    extraction_event = next(e for e in timeline if e["event_type"] == "extraction_failed")
    assert "billed_amount" in extraction_event["description"]
    assert "procedure_codes" in extraction_event["description"]
