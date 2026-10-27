import pytest
from src.source_processor import SourceProcessor
from src.models import BrandProfileSchema
from src.generator import DemoGenerator, LLMProviderInterface, SUPPORTED_PLATFORMS
from src.sample_data import SAMPLE_ARTICLE_TITLE, SAMPLE_ARTICLE_TEXT, SAMPLE_BRAND_PROFILE

@pytest.fixture
def processed_doc():
    return SourceProcessor.process_source(SAMPLE_ARTICLE_TITLE, SAMPLE_ARTICLE_TEXT, "Case Study")

@pytest.fixture
def brand_profile():
    return BrandProfileSchema(**SAMPLE_BRAND_PROFILE)

def test_demo_generation_all_platforms(processed_doc, brand_profile):
    drafts = DemoGenerator.generate_all(processed_doc, brand_profile, SUPPORTED_PLATFORMS)
    assert len(drafts) == 3

    platforms = {d.platform for d in drafts}
    assert platforms == {"linkedin", "instagram", "video_script"}

    for d in drafts:
        assert d.generation_mode == "demo"
        assert d.document_id == processed_doc.id
        assert len(d.claims) > 0
        assert d.compliance_score > 0
        assert d.hook_title

def test_platform_formatting_differences(processed_doc, brand_profile):
    passages_map = {p.passage_label: p for p in processed_doc.passages}

    li_draft = DemoGenerator.generate_linkedin(processed_doc, brand_profile, passages_map)
    ig_draft = DemoGenerator.generate_instagram(processed_doc, brand_profile, passages_map)
    vid_draft = DemoGenerator.generate_video(processed_doc, brand_profile, passages_map)

    # LinkedIn has bullet points and professional takeaways
    assert "• Challenge:" in li_draft.primary_content
    assert "• Measurable Impact:" in li_draft.primary_content

    # Instagram has mobile indicators and punchy framing
    assert "💡👇" in ig_draft.primary_content or "1️⃣" in ig_draft.primary_content

    # Video has timestamp cues and visual directions
    assert "[0:00 - 0:05 | Hook]" in vid_draft.video_script
    assert "On-screen visual:" in vid_draft.video_script

def test_deterministic_reproducibility(processed_doc, brand_profile):
    # Running generation twice with the exact same inputs produces identical content
    passages_map = {p.passage_label: p for p in processed_doc.passages}

    draft1 = DemoGenerator.generate_linkedin(processed_doc, brand_profile, passages_map)
    draft2 = DemoGenerator.generate_linkedin(processed_doc, brand_profile, passages_map)

    assert draft1.primary_content == draft2.primary_content
    assert draft1.hook_title == draft2.hook_title
    assert len(draft1.claims) == len(draft2.claims)

def test_llm_interface_fallback_without_keys(processed_doc, brand_profile):
    # Without any API keys configured, LLMProviderInterface must transparently produce demo content
    result = LLMProviderInterface.generate(processed_doc, brand_profile, ["linkedin"])

    assert result.mode_used == "demo"
    assert "Demo Mode" in result.message
    assert len(result.drafts) == 1
    assert result.drafts[0].generation_mode == "demo"

