from datetime import date

import pytest

from qdrant.ingestion import build_points, embed_texts, extract_text_from_pdf, split_into_sections
from qdrant.models import EMBEDDING_DIM


# --- extract_text_from_pdf: kept loose (page count + substring) since exact
# layout reconstruction from a rendered PDF is a pypdf implementation detail.


def test_extract_text_from_pdf_returns_all_pages(make_pdf):
    pdf_bytes = make_pdf(["Page one content.", "Page two content."])
    pages = extract_text_from_pdf(pdf_bytes)

    assert len(pages) == 2
    assert pages[0][0] == 1
    assert "Page one" in pages[0][1]
    assert pages[1][0] == 2
    assert "Page two" in pages[1][1]


# --- split_into_sections: exact, since it runs on text we fully control.


def test_split_into_sections_groups_paragraphs_under_heading():
    pages = [(1, "SECTION 1: COVERAGE\n\nThis plan covers annual checkups.\n\nAlso covers vaccinations.")]
    sections = split_into_sections(pages, max_chunk_chars=1000)

    assert len(sections) == 1
    assert sections[0]["page_number"] == 1
    assert sections[0]["section_title"] == "SECTION 1: COVERAGE"
    assert "annual checkups" in sections[0]["text"]
    assert "vaccinations" in sections[0]["text"]


def test_split_into_sections_starts_new_chunk_at_next_heading():
    pages = [(1, "SECTION 1: COVERAGE\n\nCovers checkups.\n\nSECTION 2: EXCLUSIONS\n\nExcludes cosmetic surgery.")]
    sections = split_into_sections(pages, max_chunk_chars=1000)

    assert len(sections) == 2
    assert sections[0]["section_title"] == "SECTION 1: COVERAGE"
    assert sections[1]["section_title"] == "SECTION 2: EXCLUSIONS"
    assert "checkups" in sections[0]["text"]
    assert "cosmetic" in sections[1]["text"]


def test_split_into_sections_respects_max_chunk_chars():
    long_paragraph = "word " * 400  # ~2000 chars, single paragraph, no heading
    sections = split_into_sections([(1, long_paragraph)], max_chunk_chars=500)

    assert len(sections) > 1
    assert all(len(s["text"]) <= 500 for s in sections)


def test_split_into_sections_never_spans_pages():
    pages = [(1, "First page text."), (2, "Second page text.")]
    sections = split_into_sections(pages, max_chunk_chars=1000)

    assert len(sections) == 2
    assert sections[0]["page_number"] == 1
    assert sections[1]["page_number"] == 2


def test_split_into_sections_handles_empty_page():
    assert split_into_sections([(1, "")], max_chunk_chars=1000) == []


# --- embed_texts ---


def test_embed_texts_returns_correct_dimension():
    vectors = embed_texts(["a policy sentence", "another sentence"])
    assert len(vectors) == 2
    assert all(len(v) == EMBEDDING_DIM for v in vectors)


def test_embed_texts_handles_empty_list():
    assert embed_texts([]) == []


# --- build_points ---


def test_build_points_attaches_required_metadata(make_pdf):
    pdf_bytes = make_pdf(["SECTION 1: COVERAGE\n\nThis plan covers annual checkups."])

    points = build_points(
        pdf_bytes,
        plan_id="GOLD-PPO-2026",
        state="CA",
        effective_date=date(2026, 1, 1),
        document_type="policy_certificate",
        source_document="gold_ppo_certificate.pdf",
    )

    assert len(points) >= 1
    point = points[0]
    assert len(point.vector) == EMBEDDING_DIM
    assert point.payload["plan_id"] == "GOLD-PPO-2026"
    assert point.payload["state"] == "CA"
    assert point.payload["effective_date"] == "2026-01-01"
    assert point.payload["document_type"] == "policy_certificate"
    assert point.payload["source_document"] == "gold_ppo_certificate.pdf"
    assert point.payload["page_number"] == 1
    assert "text" in point.payload


def test_build_points_rejects_unknown_document_type(make_pdf):
    pdf_bytes = make_pdf(["Some content."])

    with pytest.raises(ValueError):
        build_points(
            pdf_bytes,
            plan_id="GOLD-PPO-2026",
            state="CA",
            effective_date=date(2026, 1, 1),
            document_type="not_a_real_type",
            source_document="doc.pdf",
        )


def test_build_points_returns_empty_list_for_blank_pdf(make_pdf):
    pdf_bytes = make_pdf([""])

    points = build_points(
        pdf_bytes,
        plan_id="GOLD-PPO-2026",
        state="CA",
        effective_date=date(2026, 1, 1),
        document_type="policy_certificate",
        source_document="blank.pdf",
    )

    assert points == []
