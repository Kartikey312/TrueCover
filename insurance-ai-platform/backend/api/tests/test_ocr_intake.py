"""OCR claim intake: an image upload, or a scanned (image-only) PDF with
no embedded text layer, both still fill in missing claim fields and
auto-process -- through the real API + graph + Postgres + Tesseract, not
a mocked extraction step. Same contract as test_document_intake.py's
text/PDF cases, just for documents that need OCR to become text at all.
"""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

pytestmark = pytest.mark.asyncio(loop_scope="session")

INVOICE_LINES = [
    "City General Hospital",
    "Patient Invoice",
    "",
    "Claim Type: Vision",
    "Date of Service: 08/01/2026",
    "Procedure Codes: 92014",
    "Total Billed: $80.00",
]


def _make_invoice_image() -> Image.Image:
    # PIL's tiny bitmap default font (no size arg) is unreadable to
    # Tesseract -- a real photographed invoice has far more resolution
    # than that. A larger scalable default font is the portable stand-in
    # (no external font file/path dependency across platforms/CI).
    font = ImageFont.load_default(size=28)
    img = Image.new("RGB", (900, 320), color="white")
    draw = ImageDraw.Draw(img)
    y = 10
    for line in INVOICE_LINES:
        draw.text((10, y), line, fill="black", font=font)
        y += 40
    return img


def _make_png_bytes() -> bytes:
    buffer = io.BytesIO()
    _make_invoice_image().save(buffer, format="PNG")
    return buffer.getvalue()


def _make_scanned_pdf_bytes() -> bytes:
    """A PDF whose only content is a rasterized image of the invoice --
    no text layer at all, the same shape a real scanned document has.
    pypdf's extract_text() must return nothing for this; only the OCR
    fallback (pdf2image + Tesseract) can recover its text.
    """
    from reportlab.lib.pagesizes import LETTER
    from reportlab.pdfgen import canvas

    image_bytes = io.BytesIO()
    _make_invoice_image().save(image_bytes, format="PNG")
    image_bytes.seek(0)

    from reportlab.lib.utils import ImageReader

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=LETTER)
    pdf.drawImage(ImageReader(image_bytes), 72, 500, width=375, height=165)
    pdf.save()
    return buffer.getvalue()


async def _create_minimal_vision_claim(client, seed):
    response = await client.post(
        "/claims",
        json={
            "member_id": seed.member_id,
            "policy_id": seed.policy_id,
            "provider_id": seed.provider_id,
            "claim_type": "vision",
            "date_of_service": "2026-08-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_image_upload_fills_missing_fields_via_ocr(client, seed):
    claim = await _create_minimal_vision_claim(client, seed)

    upload = await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("invoice.png", _make_png_bytes(), "image/png")},
    )
    assert upload.status_code == 201

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "approved"
    assert body["billed_amount"] == "80.00"
    assert body["procedure_codes"] == ["92014"]


async def test_corrupt_image_upload_never_breaks_submission(client, seed):
    """OCR failing (a corrupt/unsupported file, not a real image despite
    its declared mime type) must degrade to "no text extracted", the same
    outcome as a document with no useful fields -- never a 500."""
    claim = await _create_minimal_vision_claim(client, seed)

    upload = await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("not_really_an_image.png", b"this is not valid image data", "image/png")},
    )
    assert upload.status_code == 201

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_adjuster_review"


async def test_scanned_pdf_with_no_text_layer_fills_missing_fields_via_ocr(client, seed):
    claim = await _create_minimal_vision_claim(client, seed)

    upload = await client.post(
        f"/claims/{claim['claim_id']}/documents",
        data={"document_type": "invoice"},
        files={"file": ("scanned_invoice.pdf", _make_scanned_pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201

    submitted = await client.post(f"/claims/{claim['claim_id']}/submit")
    assert submitted.status_code == 200
    body = submitted.json()
    assert body["status"] == "approved"
    assert body["billed_amount"] == "80.00"
    assert body["procedure_codes"] == ["92014"]
