import pytest
import csv
import io
import json
from src.models import ContentDraftSchema, ClaimEvidenceSchema, SourceDocumentSchema
from src.export_service import ExportService

@pytest.fixture
def sample_export_data():
    doc = SourceDocumentSchema(
        id="doc_export",
        title="Scaling Microservices with Redis & PostgreSQL",
        source_type="Case Study",
        source_url="https://example.com/case-study",
        raw_text="Sample text content for export testing.",
        word_count=6,
        passage_count=1
    )

    c1 = ClaimEvidenceSchema(
        draft_id="draft_exp_1",
        document_id="doc_export",
        claim_label="C1",
        claim_text="Measured a 42% reduction in latency.",
        referenced_passage_ids=["S1"],
        supporting_excerpt="Excerpt text with 42% latency reduction.",
        evidence_status="Evidence Linked",
        requires_human_review=False
    )

    c2 = ClaimEvidenceSchema(
        draft_id="draft_exp_1",
        document_id="doc_export",
        claim_label="C2",
        claim_text="Peak throughput reached 15,000 req/s.",
        referenced_passage_ids=["S2"],
        supporting_excerpt=None,
        evidence_status="Potentially Unsupported",
        requires_human_review=True,
        flag_reasons=["Metric '15,000 req/s' unverified in S2."]
    )

    draft1 = ContentDraftSchema(
        id="draft_exp_1",
        document_id="doc_export",
        platform="linkedin",
        hook_title="Unlocking 42% Speedup 🚀",
        primary_content="Multi-line content:\nLine 1 with comma, and quotes \"inside\".\nLine 2 with Unicode 💡 and 42% speedup.",
        cta_text="Visit demo.com",
        hashtags="#Postgres #Caching",
        review_status="approved",
        claims=[c1, c2]
    )

    return doc, [draft1]


def test_csv_export_format_and_escaping(sample_export_data):
    doc, drafts = sample_export_data
    csv_str = ExportService.to_csv(drafts, doc)

    assert csv_str is not None
    assert len(csv_str) > 0

    # Parse with standard csv reader to verify RFC 4180 compliance
    reader = list(csv.DictReader(io.StringIO(csv_str)))
    assert len(reader) == 1
    row = reader[0]

    assert row["draft_id"] == "draft_exp_1"
    assert row["platform"] == "linkedin"
    assert "Unlocking 42% Speedup 🚀" in row["hook_title"]
    assert "Line 1 with comma, and quotes \"inside\"." in row["primary_content"]
    assert row["source_title"] == "Scaling Microservices with Redis & PostgreSQL"
    assert "C1, C2" in row["claim_ids"]
    assert "Evidence Linked" in row["evidence_statuses"]
    assert row["review_status"] == "approved"


def test_json_export_structure(sample_export_data):
    doc, drafts = sample_export_data
    json_str = ExportService.to_json(drafts, doc)

    parsed = json.loads(json_str)
    assert "metadata" in parsed
    assert parsed["metadata"]["total_drafts"] == 1
    assert parsed["metadata"]["source_document"]["title"] == "Scaling Microservices with Redis & PostgreSQL"

    assert "drafts" in parsed
    assert len(parsed["drafts"]) == 1
    d = parsed["drafts"][0]
    assert d["id"] == "draft_exp_1"
    assert len(d["claims"]) == 2
    assert d["claims"][0]["claim_label"] == "C1"
    assert d["claims"][1]["evidence_status"] == "Potentially Unsupported"


def test_empty_collection_exports():
    csv_str = ExportService.to_csv([], None)
    reader = list(csv.DictReader(io.StringIO(csv_str)))
    assert len(reader) == 0

    json_str = ExportService.to_json([], None)
    parsed = json.loads(json_str)
    assert parsed["metadata"]["total_drafts"] == 0
    assert parsed["drafts"] == []


def test_credential_leak_safety(sample_export_data):
    doc, drafts = sample_export_data
    csv_str = ExportService.to_csv(drafts, doc)
    json_str = ExportService.to_json(drafts, doc)

    # Ensure no internal keys or passwords are leaked
    for dangerous in ["postgres://", "password=", "secret", "bearer", "api_key"]:
        assert dangerous not in csv_str.lower()
        assert dangerous not in json_str.lower()
