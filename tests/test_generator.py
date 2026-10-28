import os
import json
import pytest
from unittest.mock import MagicMock, patch
from src.source_processor import SourceProcessor
from src.models import BrandProfileSchema
from src.generator import DemoGenerator, LLMProviderInterface, SUPPORTED_PLATFORMS
from src.gemini_service import GeminiGenerator, GeminiGenerationError, sanitize_ai_error
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
    passages_map = {p.passage_label: p for p in processed_doc.passages}

    draft1 = DemoGenerator.generate_linkedin(processed_doc, brand_profile, passages_map)
    draft2 = DemoGenerator.generate_linkedin(processed_doc, brand_profile, passages_map)

    assert draft1.primary_content == draft2.primary_content
    assert draft1.hook_title == draft2.hook_title
    assert len(draft1.claims) == len(draft2.claims)


def test_llm_interface_fallback_without_keys(processed_doc, brand_profile, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = LLMProviderInterface.generate(processed_doc, brand_profile, ["linkedin"])

    assert result.mode_used == "demo"
    assert len(result.drafts) == 1
    assert result.drafts[0].generation_mode == "demo"


def test_gemini_generation_mocked_success(processed_doc, brand_profile):
    """Verifies GeminiGenerator parses structured JSON and preserves evidence traceability."""
    mock_payload = {
        "hook_title": "How NexusPay Cut Latency by 42%",
        "primary_content": "Scaling high-throughput architectures requires careful caching. [S1]\n\nNexusPay deployed a two-tier caching architecture in October 2025. [S2]\n\nWithin 30 days, query latency fell by 42%. [S3]",
        "cta_text": "Read the full case study.",
        "hashtags": "#Fintech #Architecture",
        "claims": [
            {
                "claim_label": "C1",
                "claim_text": "NexusPay deployed a two-tier caching architecture in October 2025.",
                "referenced_passage_ids": ["S2"],
                "supporting_excerpt": "deployed a two-tier caching architecture in October 2025"
            },
            {
                "claim_label": "C2",
                "claim_text": "Within thirty days, query latency fell by 42%.",
                "referenced_passage_ids": ["S3"],
                "supporting_excerpt": "measured a 42% reduction in overall database query latency"
            }
        ]
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_payload)

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client

        drafts = GeminiGenerator.generate_all(
            document=processed_doc,
            brand_profile=brand_profile,
            selected_platforms=["linkedin"],
            api_key="mock-gemini-key-12345",
            model_name="gemini-2.5-flash"
        )

        assert len(drafts) == 1
        draft = drafts[0]
        assert draft.generation_mode == "gemini"
        assert draft.hook_title == "How NexusPay Cut Latency by 42%"
        assert len(draft.claims) == 2
        assert draft.claims[0].claim_label == "C1"
        assert draft.claims[0].referenced_passage_ids == ["S2"]
        assert draft.compliance_score > 0


def test_gemini_generation_failure_does_not_silently_fallback(processed_doc, brand_profile, monkeypatch):
    """
    Verifies that when a configured Gemini API call fails,
    an explicit GeminiGenerationError is raised and the system DOES NOT silently hide the error.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "mock-invalid-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")

    with patch("google.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API rate limit exceeded")
        mock_client_cls.return_value = mock_client

        with pytest.raises(GeminiGenerationError) as exc_info:
            LLMProviderInterface.generate(
                document=processed_doc,
                brand_profile=brand_profile,
                selected_platforms=["linkedin"]
            )
        assert "API request failed" in str(exc_info.value) or "API rate limit" in str(exc_info.value)


def test_sanitize_ai_error():
    """Verifies that API keys and sensitive tokens are masked from AI error messages."""
    raw_error = "google.genai.errors.APIError: 400 API_KEY_INVALID key=AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q token='secret-token-value'"
    safe_error = sanitize_ai_error(raw_error)
    assert "AIzaSyA1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6Q" not in safe_error
    assert "secret-token-value" not in safe_error
    assert "AIzaSy***" in safe_error or "key=***" in safe_error


def test_real_gemini_api_call_if_key_present(processed_doc, brand_profile):
    """
    Tests live Gemini API generation ONLY when a real key is configured in the environment.
    Clearly skips if no real key is present.
    """
    real_key = os.getenv("GEMINI_API_KEY")
    if not real_key or real_key.startswith("mock") or real_key == "":
        pytest.skip("GEMINI_API_KEY is not configured in local environment; skipping live API test.")

    # If real key is provided:
    drafts = GeminiGenerator.generate_all(
        document=processed_doc,
        brand_profile=brand_profile,
        selected_platforms=["linkedin"],
        api_key=real_key,
        model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    )
    assert len(drafts) == 1
    assert drafts[0].generation_mode == "gemini"
    assert len(drafts[0].claims) > 0
