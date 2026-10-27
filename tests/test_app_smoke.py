"""
End-to-end smoke test validating the complete SourceWise AI pipeline.
Executes the full content repurposing lifecycle:
Source Input -> Passage Extraction -> Demo Generation -> Evidence Auditing
-> Brand Compliance -> Storage -> Approval -> Export.
Runs without network access or live API keys.
"""
import pytest
from src.source_processor import SourceProcessor
from src.models import BrandProfileSchema
from src.generator import DemoGenerator, SUPPORTED_PLATFORMS
from src.brand_engine import BrandEngine
from src.database import DatabaseManager, _MEMORY_STORE
from src.export_service import ExportService
from src.sample_data import (
    SAMPLE_ARTICLE_TITLE,
    SAMPLE_ARTICLE_TEXT,
    SAMPLE_ARTICLE_TYPE,
    SAMPLE_BRAND_PROFILE
)

def test_full_application_lifecycle_smoke():
    _MEMORY_STORE.clear()

    # Step 1: Process raw source text into versioned document & passages
    doc = SourceProcessor.process_source(
        title=SAMPLE_ARTICLE_TITLE,
        raw_text=SAMPLE_ARTICLE_TEXT,
        source_type=SAMPLE_ARTICLE_TYPE
    )
    assert doc.id is not None
    assert doc.passage_count >= 4
    assert len(doc.passages) == doc.passage_count

    # Step 2: Configure brand profile
    brand = BrandProfileSchema(**SAMPLE_BRAND_PROFILE)
    ok_b, _ = DatabaseManager.save_brand_profile(brand)
    assert ok_b is True

    # Step 3: Persist document
    ok_d, _ = DatabaseManager.save_source_document(doc)
    assert ok_d is True

    # Step 4: Generate drafts across all target platforms (Demo Mode)
    drafts = DemoGenerator.generate_all(doc, brand, SUPPORTED_PLATFORMS)
    assert len(drafts) == 3

    for draft in drafts:
        # Step 5: Verify platform content and evidence linking
        assert draft.platform in SUPPORTED_PLATFORMS
        assert draft.hook_title
        assert len(draft.claims) >= 1

        # Every claim must have verified passage references
        for claim in draft.claims:
            assert claim.claim_label.startswith("C")
            assert len(claim.referenced_passage_ids) >= 1
            for pid in claim.referenced_passage_ids:
                assert any(p.passage_label == pid for p in doc.passages)

        # Step 6: Verify brand compliance score
        score, checks = BrandEngine.evaluate_draft(draft, brand)
        assert score >= 70

        # Step 7: Persist draft
        ok_draft, _ = DatabaseManager.save_content_draft(draft)
        assert ok_draft is True

        # Step 8: Approve draft
        ok_app, _ = DatabaseManager.update_draft_status(draft.id, "approved", notes="Verified by reviewer.")
        assert ok_app is True

    # Step 9: Verify library listing
    saved_drafts = DatabaseManager.list_content_drafts()
    assert len(saved_drafts) == 3
    assert all(d.review_status == "approved" for d in saved_drafts)

    # Step 10: Export to CSV and JSON
    csv_export = ExportService.to_csv(saved_drafts, doc)
    assert len(csv_export) > 100
    assert "draft_id" in csv_export
    assert "Evidence Linked" in csv_export

    json_export = ExportService.to_json(saved_drafts, doc)
    assert len(json_export) > 100
    assert '"total_drafts": 3' in json_export

