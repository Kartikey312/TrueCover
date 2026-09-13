from graph.document_parser import extract_fields_from_text

SAMPLE_FORM = """\
City General Hospital
Patient Invoice

Claim Type: Dental
Date of Service: 08/01/2026
Procedure Codes: D1110, D0120
Diagnosis Codes: K02.9
Total Billed: $150.00

Thank you for your visit.
"""


def test_extracts_all_fields_from_a_well_formed_form():
    fields = extract_fields_from_text(SAMPLE_FORM)

    assert fields["claim_type"] == "dental"
    assert fields["date_of_service"] == "2026-08-01"
    assert fields["procedure_codes"] == ["D1110", "D0120"]
    assert fields["diagnosis_codes"] == ["K02.9"]
    assert fields["billed_amount"] == "150.00"


def test_recognizes_label_synonyms():
    text = "Service Date: 2026-08-01\nCPT Codes: 99213\nAmount Due: $75.50\n"
    fields = extract_fields_from_text(text)

    assert fields["date_of_service"] == "2026-08-01"
    assert fields["procedure_codes"] == ["99213"]
    assert fields["billed_amount"] == "75.50"


def test_label_matching_is_case_insensitive_and_tolerates_whitespace():
    text = "  BILLED AMOUNT  :   $200.00  \n"
    fields = extract_fields_from_text(text)
    assert fields["billed_amount"] == "200.00"


def test_unrecognized_claim_type_value_is_dropped_not_passed_through():
    # Never hand back a free-text value that isn't one of the known
    # categories -- that would trip the "unrecognized claim type" rule
    # and auto-deny a claim purely because of a parsing quirk.
    text = "Claim Type: Emergency Room Visit\n"
    fields = extract_fields_from_text(text)
    assert "claim_type" not in fields


def test_unparseable_amount_is_dropped():
    text = "Total Billed: see attached schedule\n"
    fields = extract_fields_from_text(text)
    assert "billed_amount" not in fields


def test_unparseable_date_is_dropped():
    text = "Date of Service: sometime last week\n"
    fields = extract_fields_from_text(text)
    assert "date_of_service" not in fields


def test_lines_without_a_colon_are_ignored():
    fields = extract_fields_from_text("This is just a note with no fields.\n")
    assert fields == {}


def test_empty_text_returns_no_fields():
    assert extract_fields_from_text("") == {}


def test_unrecognized_labels_are_ignored():
    fields = extract_fields_from_text("Patient Name: Jane Doe\nAccount Number: 12345\n")
    assert fields == {}


def test_first_matching_line_wins_when_a_label_repeats():
    text = "Total Billed: $100.00\nTotal Billed: $999.00\n"
    fields = extract_fields_from_text(text)
    assert fields["billed_amount"] == "100.00"


def test_code_list_splits_on_various_separators():
    assert extract_fields_from_text("Procedure Codes: D1110; D0120\n")["procedure_codes"] == ["D1110", "D0120"]
    assert extract_fields_from_text("Diagnosis Codes: K02.9 and F41.1\n")["diagnosis_codes"] == ["K02.9", "F41.1"]
