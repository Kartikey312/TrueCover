import io

import pytest
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas


def _build_pdf(pages_text: list[str]) -> bytes:
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=LETTER)
    for page_text in pages_text:
        y = 750
        for line in page_text.split("\n"):
            pdf_canvas.drawString(72, y, line)
            y -= 14
        pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


@pytest.fixture
def make_pdf():
    """Returns a function: make_pdf(["page 1 text", "page 2 text", ...]) -> bytes"""
    return _build_pdf
