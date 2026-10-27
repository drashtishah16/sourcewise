import pytest
from src.models import PassageSchema, generate_id
from src.evidence_engine import (
    EvidenceAuditor,
    STATUS_EVIDENCE_LINKED,
    STATUS_POTENTIALLY_UNSUPPORTED,
    STATUS_HUMAN_REVIEW_REQUIRED
)

@pytest.fixture
def sample_passages_map():
    p1 = PassageSchema(
        id=generate_id("pass"),
        document_id="doc_test",
        passage_label="S1",
        passage_order=1,
        text="Peak-hour 99th-percentile query latency exceeded 820ms on primary PostgreSQL clusters during Q3 2025."
    )
    p2 = PassageSchema(
        id=generate_id("pass"),
        document_id="doc_test",
        passage_label="S2",
        passage_order=2,
        text="The team measured a 42% reduction in overall database query latency, dropping p99 response times from 820ms to 475ms."
    )
    p3 = PassageSchema(
        id=generate_id("pass"),
        document_id="doc_test",
        passage_label="S3",
        passage_order=3,
        text='Elena Rostova stated: "Implementing the multi-tier caching strategy cut infrastructure overhead by $18,500 per month."'
    )
    return {"S1": p1, "S2": p2, "S3": p3}


def test_valid_evidence_linking(sample_passages_map):
    claim_text = "The team measured a 42% reduction in overall database query latency [S2]."
    claim = EvidenceAuditor.audit_claim(
        claim_label="C1",
        claim_text=claim_text,
        referenced_passage_ids=["S2"],
        passages_map=sample_passages_map,
        draft_id="draft_test",
        document_id="doc_test"
    )

    assert claim.evidence_status == STATUS_EVIDENCE_LINKED
    assert claim.requires_human_review is False
    assert len(claim.flag_reasons) == 0
    assert claim.supporting_excerpt is not None
    assert "42%" in claim.supporting_excerpt


def test_invalid_passage_id_rejection(sample_passages_map):
    claim_text = "Database latency dropped significantly [S99]."
    claim = EvidenceAuditor.audit_claim(
        claim_label="C2",
        claim_text=claim_text,
        referenced_passage_ids=["S99"],
        passages_map=sample_passages_map,
        draft_id="draft_test",
        document_id="doc_test"
    )

    assert claim.evidence_status == STATUS_POTENTIALLY_UNSUPPORTED
    assert claim.requires_human_review is True
    assert any("S99" in r for r in claim.flag_reasons)


def test_unsupported_metrics_and_percentages_detection(sample_passages_map):
    # Claim invents 85% instead of real 42%
    unsupported_claim = "The architecture delivered an 85% latency reduction."
    claim = EvidenceAuditor.audit_claim(
        claim_label="C3",
        claim_text=unsupported_claim,
        referenced_passage_ids=["S2"],
        passages_map=sample_passages_map,
        draft_id="draft_test",
        document_id="doc_test"
    )

    assert claim.evidence_status == STATUS_POTENTIALLY_UNSUPPORTED
    assert claim.requires_human_review is True
    assert any("85%" in r for r in claim.flag_reasons)


def test_unsupported_dates_detection(sample_passages_map):
    # Claim invents 2018 instead of Q3 2025
    claim_text = "Peak latency was an issue in 2018."
    claim = EvidenceAuditor.audit_claim(
        claim_label="C4",
        claim_text=claim_text,
        referenced_passage_ids=["S1"],
        passages_map=sample_passages_map,
        draft_id="draft_test",
        document_id="doc_test"
    )

    assert claim.requires_human_review is True
    assert any("2018" in r for r in claim.flag_reasons)


def test_unsupported_quotes_detection(sample_passages_map):
    # Invented quote
    claim_text = 'Elena declared: "This was the single greatest product triumph in company history."'
    claim = EvidenceAuditor.audit_claim(
        claim_label="C5",
        claim_text=claim_text,
        referenced_passage_ids=["S3"],
        passages_map=sample_passages_map,
        draft_id="draft_test",
        document_id="doc_test"
    )

    assert claim.evidence_status == STATUS_POTENTIALLY_UNSUPPORTED
    assert claim.requires_human_review is True
    assert any("Quoted assertion" in r for r in claim.flag_reasons)


def test_missing_passage_reference(sample_passages_map):
    claim_text = "Latency dropped from 820ms to 475ms."
    claim = EvidenceAuditor.audit_claim(
        claim_label="C6",
        claim_text=claim_text,
        referenced_passage_ids=[],
        passages_map=sample_passages_map,
        draft_id="draft_test",
        document_id="doc_test"
    )

    assert claim.evidence_status == STATUS_POTENTIALLY_UNSUPPORTED
    assert claim.requires_human_review is True
    assert any("No source passage" in r for r in claim.flag_reasons)


def test_sentence_classification_distinguishes_claims_and_creative_elements():
    assert EvidenceAuditor.classify_sentence("Read the complete teardown and benchmark your stack at cloudpulse.io") == "CALL_TO_ACTION"
    assert EvidenceAuditor.classify_sentence("Ever wondered how top engineering teams scale Postgres without sharding?") == "CREATIVE_HOOK"
    assert EvidenceAuditor.classify_sentence("We believe thoughtful caching is vital for database health.") == "OPINION_OR_TRANSITION"
    assert EvidenceAuditor.classify_sentence("NexusPay achieved a 42% reduction in p99 query latency within thirty days.") == "FACTUAL_CLAIM"


def test_disclaimer_scope_notice():
    note = EvidenceAuditor.get_disclaimer_note()
    assert "Evidence Traceability Notice" in note
    assert "textual alignment" in note
    assert "external real-world truth" in note

