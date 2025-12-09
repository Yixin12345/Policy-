from backend.infrastructure.vision.vision_response_parser import VisionResponseParser


def test_parse_page_with_fields_and_tables():
    parser = VisionResponseParser()
    payload = {
        "documentType": {"label": "facility_invoice", "confidence": 0.82, "reasons": ["invoice keywords"]},
        "fields": [
            {
                "id": "field-1",
                "name": "Invoice Number",
                "value": "INV-001",
                "confidence": 0.8,
                "type": "text",
                "bbox": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1},
            }
        ],
        "tables": [
            {
                "id": "table-1",
                "confidence": 0.6,
                "rows": [
                    [
                        {"value": "Item", "confidence": 0.6},
                        {"value": "Amount", "confidence": 0.6},
                    ],
                    [
                        {"value": "Service A", "confidence": 0.6},
                        {"value": "$100", "confidence": 0.6},
                    ],
                ],
            }
        ],
    }

    page = parser.parse_page(page_number=1, payload=payload, image_path="/tmp/page-1.png")

    assert page.page_number == 1
    assert page.image_path == "/tmp/page-1.png"
    assert page.total_extractions == 2

    first_field = page.fields[0]
    assert first_field.field_name == "Invoice Number"
    assert first_field.value == "INV-001"
    assert first_field.confidence.value == 0.8
    assert first_field.bounding_box is not None
    assert first_field.bounding_box.x == 0.1

    first_table = page.tables[0]
    assert first_table.num_rows == 2
    assert first_table.num_columns == 2
    assert first_table.confidence.value == 0.6
    assert first_table.cells[0].content == "Item"
    assert first_table.cells[3].content == "$100"
