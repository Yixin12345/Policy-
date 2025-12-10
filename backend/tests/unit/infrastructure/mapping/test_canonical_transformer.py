from backend.domain.entities.field_extraction import FieldExtraction
from backend.domain.entities.job import Job
from backend.domain.entities.page_extraction import PageExtraction
from backend.domain.entities.table_extraction import TableCell, TableExtraction
from backend.domain.value_objects.bounding_box import BoundingBox
from backend.infrastructure.mapping.canonical_transformer import CanonicalTransformer


def test_build_payload_from_job() -> None:
    job = Job.create(job_id="job-123", filename="invoice.pdf")

    field = FieldExtraction.create(
        field_name="invoice_number",
        value="INV-100",
        confidence=0.9,
        bounding_box=BoundingBox(0.1, 0.1, 0.2, 0.05),
        page_number=1,
    )

    header_cell = TableCell(row=0, column=0, content="Item", is_header=True)
    value_cell = TableCell(row=1, column=0, content="Consultation", confidence=None)
    table = TableExtraction.create(
        cells=[header_cell, value_cell],
        page_number=1,
        confidence=0.8,
        title="Services",
    )

    page = PageExtraction.create(
        page_number=1,
        fields=[field],
        tables=[table],
        image_path="/tmp/page-1.png",
    )
    job = job.with_pages([page])

    transformer = CanonicalTransformer()
    payload = transformer.build_payload(
        job,
        aggregated={"total": 100.0},
        metadata={"originalFilename": "invoice.pdf"},
    )
    data = payload.payload

    assert data["jobId"] == "job-123"
    assert data["originalFilename"] == "invoice.pdf"
    assert data["aggregated"] == {"total": 100.0}
    assert data["documentCategories"] == []
    assert data["pageCategories"] == {}
    assert len(data["pages"]) == 1

    page_payload = data["pages"][0]
    assert page_payload["pageNumber"] == 1
    assert page_payload["imagePath"] == "/tmp/page-1.png"
    assert len(page_payload["fields"]) == 1
    assert len(page_payload["tables"]) == 1

    field_payload = page_payload["fields"][0]
    assert field_payload["name"] == "invoice_number"
    assert field_payload["value"] == "INV-100"
    assert field_payload["confidence"] == 0.9
    assert field_payload["bbox"]["width"] == 0.2

    table_payload = page_payload["tables"][0]
    assert table_payload["title"] == "Services"
    assert table_payload["numRows"] == 2
    assert table_payload["rows"][0][0]["isHeader"] is True
    assert table_payload["rows"][1][0]["value"] == "Consultation"
