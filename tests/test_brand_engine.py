import pytest
from src.models import BrandProfileSchema, ContentDraftSchema
from src.brand_engine import BrandEngine

@pytest.fixture
def sample_brand():
    return BrandProfileSchema(
        name="FinScale",
        target_audience="Engineers",
        tone_of_voice="Professional",
        preferred_terminology=["latency reduction", "cloud-native", "benchmarks"],
        forbidden_terminology=["cheap", "magic bullet", "guarantee"],
        primary_cta="Visit finscale.io/demo to run your test.",
        required_disclaimer="Results vary according to individual cluster topology.",
        hashtag_preferences="#Fintech #SystemDesign",
        content_length_prefs={
            "linkedin_min": 50,
            "linkedin_max": 250,
            "instagram_min": 30,
            "instagram_max": 150,
            "video_seconds": 60
        }
    )

def test_forbidden_terms_detection(sample_brand):
    dirty_text = "Our tool is cheap and offers a magic bullet guarantee for database latency."
    results = BrandEngine.check_forbidden_terms(dirty_text, sample_brand.forbidden_terminology)

    assert len(results) == 3
    for r in results:
        assert r.status == "FAIL"
        assert "forbidden term" in r.explanation

def test_clean_text_passes_forbidden_check(sample_brand):
    clean_text = "Our platform provides verified latency reduction for mission-critical databases."
    results = BrandEngine.check_forbidden_terms(clean_text, sample_brand.forbidden_terminology)
    assert len(results) == 0

def test_preferred_terms_check(sample_brand):
    partial_text = "We achieved significant latency reduction on the cluster."
    results = BrandEngine.check_preferred_terms(partial_text, sample_brand.preferred_terminology)
    assert len(results) == 1
    # missing cloud-native and benchmarks
    assert results[0].status == "WARNING"
    assert "benchmarks" in results[0].explanation

def test_required_disclaimer_presence_and_absence(sample_brand):
    # Missing disclaimer
    res_missing = BrandEngine.check_disclaimer("Great results overall.", sample_brand.required_disclaimer)
    assert res_missing.status == "FAIL"

    # Present disclaimer
    res_present = BrandEngine.check_disclaimer(
        "Great results. Note: Results vary according to individual cluster topology.",
        sample_brand.required_disclaimer
    )
    assert res_present.status == "PASS"

def test_cta_check(sample_brand):
    draft_with_cta = ContentDraftSchema(
        document_id="doc_1",
        platform="linkedin",
        hook_title="Test Hook",
        primary_content="Some content",
        cta_text="Visit finscale.io/demo to run your test."
    )
    res_pass = BrandEngine.check_cta(draft_with_cta, sample_brand.primary_cta)
    assert res_pass.status == "PASS"

    draft_without_cta = ContentDraftSchema(
        document_id="doc_1",
        platform="linkedin",
        hook_title="Test Hook",
        primary_content="Some content without action",
        cta_text=""
    )
    res_warn = BrandEngine.check_cta(draft_without_cta, sample_brand.primary_cta)
    assert res_warn.status == "WARNING"

def test_overall_evaluation_and_score(sample_brand):
    # Compliant draft
    compliant_draft = ContentDraftSchema(
        document_id="doc_1",
        platform="linkedin",
        hook_title="Scaling Databases",
        primary_content=(
            "We achieved latency reduction using cloud-native benchmarks across all clusters. " * 8 +
            "Results vary according to individual cluster topology."
        ),
        cta_text="Visit finscale.io/demo to run your test."
    )
    score, checks = BrandEngine.evaluate_draft(compliant_draft, sample_brand)
    assert score >= 90
    assert all(c.status != "FAIL" for c in checks)

