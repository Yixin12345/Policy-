"""Unit tests for the CanonicalMapper domain service."""
from __future__ import annotations

import pytest

from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.table_extraction import TableCell, TableExtraction
from backend.domain.services.canonical_mapper import CanonicalMapper
from backend.domain.value_objects import CanonicalFieldIndex, CanonicalGroup
from backend.domain.value_objects.confidence import Confidence


@pytest.fixture()
def mapper() -> CanonicalMapper:
    return CanonicalMapper(schema_version="test-1.0.0", confidence_override=0.9)


def labels_for_group(group: CanonicalGroup) -> list[str]:
    return [
        field.label
        for field in CanonicalFieldIndex.for_group(group)
        if not field.is_identity_block_member and field.include_in_group
    ]


def make_field(
    name: str,
    value: str,
    *,
    confidence: float = 0.95,
    page_number: int = 1,
) -> FieldExtraction:
    return FieldExtraction.create(
        field_name=name,
        value=value,
        field_type="text",
        confidence=confidence,
        page_number=page_number,
    )


def test_build_empty_bundle_includes_all_groups(mapper: CanonicalMapper) -> None:
    bundle = mapper.build_empty_bundle()

    assert bundle["schemaVersion"] == "test-1.0.0"
    assert set(bundle.keys()).issuperset({"invoice", "cmr", "ub04"})

    assert list(bundle["invoice"].keys()) == labels_for_group(CanonicalGroup.GENERAL_INVOICE)
    assert list(bundle["cmr"].keys()) == labels_for_group(CanonicalGroup.CMR)
    assert list(bundle["ub04"].keys()) == labels_for_group(CanonicalGroup.UB04)


def test_build_empty_bundle_filters_groups(mapper: CanonicalMapper) -> None:
    bundle = mapper.build_empty_bundle(["INVOICE"])

    assert "invoice" in bundle
    assert "cmr" not in bundle
    assert "ub04" not in bundle

    # documentCategories should preserve provided casing order
    assert bundle["documentCategories"] == ["INVOICE"]


def test_map_document_populates_values_and_sources(mapper: CanonicalMapper) -> None:
    invoice_number = make_field("invoice number", "INV-9087", confidence=0.82)
    provider_name = make_field("provider name", "Evergreen Residence", confidence=0.88)
    low_confidence = make_field("total amount", "1290.55", confidence=0.4)

    page = PageExtraction.create(page_number=1, fields=[invoice_number, provider_name, low_confidence], tables=[])

    bundle = mapper.map_document([page])

    invoice_entry = bundle["invoice"]["Invoice number"]
    assert invoice_entry["value"] == "INV-9087"
    assert invoice_entry["confidence"] == pytest.approx(0.82)
    assert invoice_entry["sources"][0]["page"] == 1
    assert invoice_entry["sources"][0]["fieldId"] == str(invoice_number.id)

    provider_entry = bundle["invoice"]["Provider name"]
    assert provider_entry["value"] == "Evergreen Residence"

    amount_entry = bundle["invoice"]["Total amount"]
    assert amount_entry["value"] == "1290.55"
    # Low confidence still stored because no competing higher confidence value
    assert amount_entry["confidence"] == pytest.approx(0.4)

    source_map = bundle["sourceMap"].get("INVOICE_NUMBER")
    assert source_map is not None
    assert source_map["fieldIds"]
    assert source_map["pages"] == [1]


def test_map_document_groups_invoice_line_items(mapper: CanonicalMapper) -> None:
    description_one = make_field("Description / activity", "Monthly rent", confidence=0.81, page_number=1)
    start_one = make_field("Start date", "2025-01-01", confidence=0.77, page_number=1)
    end_one = make_field("End date", "2025-01-31", confidence=0.76, page_number=1)
    amount_one = make_field("Charges / amount", "$3,200", confidence=0.8, page_number=1)

    description_two = make_field("Description / activity", "Care services", confidence=0.79, page_number=1)
    start_two = make_field("Start date", "2025-01-10", confidence=0.74, page_number=1)
    quantity_two = make_field("Unit / quantity", "12", confidence=0.7, page_number=1)
    credits_two = make_field("Credits", "$150", confidence=0.71, page_number=1)

    page = PageExtraction.create(
        page_number=1,
        fields=[
            description_one,
            start_one,
            end_one,
            amount_one,
            description_two,
            start_two,
            quantity_two,
            credits_two,
        ],
        tables=[],
    )

    bundle = mapper.map_document([page])

    assert "invoiceLineItems" in bundle
    line_items = bundle["invoiceLineItems"]
    assert isinstance(line_items, list)
    assert len(line_items) == 2

    first_item = line_items[0]
    assert first_item["description"]["value"] == "Monthly rent"
    assert first_item["startDate"]["value"] == "2025-01-01"
    assert first_item["endDate"]["value"] == "2025-01-31"
    assert first_item["chargesAmount"]["value"] == "$3,200"

    second_item = line_items[1]
    assert second_item["description"]["value"] == "Care services"
    assert second_item["startDate"]["value"] == "2025-01-10"
    assert second_item["unitQuantity"]["value"] == "12"
    assert second_item["credits"]["value"] == "$150"

    source_map = bundle["sourceMap"]
    assert "DESCRIPTION_ACTIVITY" in source_map
    assert source_map["DESCRIPTION_ACTIVITY"]["pages"] == [1]


def test_map_document_aggregates_identity_blocks(mapper: CanonicalMapper) -> None:
    policy_number = make_field("policy_number_duplicate", "POL-001")
    policyholder_name = make_field("policyholder_name_duplicate", "Jane Doe")
    patient_name = make_field("patient_name_duplicate", "Resident One")

    page = PageExtraction.create(
        page_number=2,
        fields=[policy_number, policyholder_name, patient_name],
        tables=[],
    )

    bundle = mapper.map_document([page])

    identity_blocks = bundle["identityBlocks"]
    assert len(identity_blocks) == 2

    policy_block = next(block for block in identity_blocks if block["blockType"] == "policyHolderIdentity")
    assert policy_block["policyNumber"] == "POL-001"
    assert policy_block["policyholderName"] == "Jane Doe"
    assert policy_block["sequence"] == 1
    assert set(policy_block["presentFields"]) == {
        "CMR_POLICY_NUMBER_DUPLICATE",
        "CMR_POLICYHOLDER_NAME_DUPLICATE",
    }
    assert policy_block["source"]["page"] == 2

    patient_block = next(block for block in identity_blocks if block["blockType"] == "patientIdentity")
    assert patient_block["patientName"] == "Resident One"
    assert patient_block["presentFields"] == ["PATIENT_NAME_DUPLICATE"]


def test_map_document_respects_confidence_override(mapper: CanonicalMapper) -> None:
    high_confidence = make_field("invoice number", "INV-HIGH", confidence=0.95)
    low_confidence = make_field("invoice number", "INV-LOW", confidence=0.5)

    page = PageExtraction.create(page_number=1, fields=[low_confidence, high_confidence], tables=[])
    bundle = mapper.map_document([page])

    invoice_entry = bundle["invoice"]["Invoice number"]
    assert invoice_entry["value"] == "INV-HIGH"
    assert invoice_entry["confidence"] == pytest.approx(0.95)
    field_ids = {source["fieldId"] for source in invoice_entry["sources"]}
    assert field_ids == {str(low_confidence.id), str(high_confidence.id)}


def test_map_document_honors_page_categories(mapper: CanonicalMapper) -> None:
    invoice_policy = make_field("policy number", "INV-123", page_number=1)
    cmr_policy = make_field("policy number", "CMR-456", page_number=2)

    invoice_page = PageExtraction.create(page_number=1, fields=[invoice_policy], tables=[])
    cmr_page = PageExtraction.create(page_number=2, fields=[cmr_policy], tables=[])

    bundle = mapper.map_document(
        [invoice_page, cmr_page],
        document_categories=["INVOICE", "CMR"],
        page_categories={1: ["INVOICE"], 2: ["CMR"]},
    )

    assert bundle["invoice"]["Policy number"]["value"] == "INV-123"
    assert bundle["cmr"]["Policy number"]["value"] == "CMR-456"

    cmr_policy_entry = bundle["cmr"]["Policy number"]
    assert cmr_policy_entry["sources"][0]["page"] == 2
    assert bundle["invoice"]["Policy number"]["sources"][0]["page"] == 1


def test_map_document_normalizes_absence_details(mapper: CanonicalMapper) -> None:
    absence_field = make_field(
        "absence_details",
        "Departure: 2025-01-01; Return: 2025-01-05; Reason: Vacation",
        confidence=0.87,
        page_number=3,
    )
    page = PageExtraction.create(page_number=3, fields=[absence_field], tables=[])

    bundle = mapper.map_document([page])

    absence_entry = bundle["cmr"]["Absence details (if yes)"]
    assert isinstance(absence_entry["value"], dict)
    assert absence_entry["value"]["departureDate"] == "2025-01-01"
    assert absence_entry["value"]["returnDate"] == "2025-01-05"
    assert absence_entry["value"]["reason"] == "Vacation"

    source_map = bundle["sourceMap"].get("ABSENCE_DETAILS")
    assert source_map is not None
    assert source_map["page"] == 3


def test_map_document_extracts_line_items_from_tables(mapper: CanonicalMapper) -> None:
    headers = [
        TableCell(row=0, column=0, content="Revenue Code", is_header=True, confidence=Confidence(0.9)),
        TableCell(row=0, column=1, content="Description", is_header=True, confidence=Confidence(0.9)),
        TableCell(row=0, column=2, content="Units", is_header=True, confidence=Confidence(0.9)),
        TableCell(row=0, column=3, content="Total Charge", is_header=True, confidence=Confidence(0.9)),
    ]
    row_one = [
        TableCell(row=1, column=0, content="0100", confidence=Confidence(0.82)),
        TableCell(row=1, column=1, content="Room and board", confidence=Confidence(0.8)),
        TableCell(row=1, column=2, content="5", confidence=Confidence(0.78)),
        TableCell(row=1, column=3, content="$1,000", confidence=Confidence(0.79)),
    ]
    row_two = [
        TableCell(row=2, column=0, content="0120", confidence=Confidence(0.81)),
        TableCell(row=2, column=1, content="Therapy", confidence=Confidence(0.8)),
        TableCell(row=2, column=2, content="2", confidence=Confidence(0.77)),
        TableCell(row=2, column=3, content="$400", confidence=Confidence(0.76)),
    ]

    table = TableExtraction.create(
        cells=headers + row_one + row_two,
        page_number=2,
        confidence=0.83,
        title="Line Items Table",
    )
    page = PageExtraction.create(page_number=2, fields=[], tables=[table])

    bundle = mapper.map_document([page])

    line_item_tables = bundle["ub04LineItems"]
    assert len(line_item_tables) == 1
    table_payload = line_item_tables[0]
    assert table_payload["tableId"] == str(table.id)
    assert table_payload["confidence"] == pytest.approx(0.79125, abs=1e-3)

    headers = table_payload["headers"]
    header_keys = {header["key"] for header in headers}
    assert {"revenueCode", "description", "units", "totalCharge"}.issubset(header_keys)

    items = table_payload["items"]
    assert len(items) == 2
    assert items[0]["revenueCode"]["value"] == "0100"
    assert items[0]["totalCharge"]["value"] == "$1,000"
    assert items[1]["description"]["value"] == "Therapy"
    assert table_payload["sources"][0]["tableId"] == str(table.id)

    source_map = bundle["sourceMap"].get("LINE_ITEMS")
    assert source_map is not None
    assert str(table.id) in source_map["tableIds"]
