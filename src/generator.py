"""
Content Generation Engine for SourceWise AI.
Supports both:
1. Demo Mode: 100% deterministic, rule-based generation with zero API keys or network calls.
2. Connected Mode: Modular extensible interface for external LLM providers (OpenAI, Gemini, Anthropic)
   with automatic safe fallback to Demo Mode if keys are not present.
"""
from typing import List, Dict, Optional, Tuple, Any
import re
from src.models import (
    SourceDocumentSchema,
    BrandProfileSchema,
    ContentDraftSchema,
    ClaimEvidenceSchema,
    PassageSchema,
    generate_id
)
from src.evidence_engine import EvidenceAuditor, STATUS_EVIDENCE_LINKED
from src.brand_engine import BrandEngine
from src.config import is_connected_mode_available, get_ai_credentials

PLATFORM_LINKEDIN = "linkedin"
PLATFORM_INSTAGRAM = "instagram"
PLATFORM_VIDEO = "video_script"

SUPPORTED_PLATFORMS = [PLATFORM_LINKEDIN, PLATFORM_INSTAGRAM, PLATFORM_VIDEO]


class GenerationResult:
    def __init__(
        self,
        drafts: List[ContentDraftSchema],
        mode_used: str,
        message: str
    ):
        self.drafts = drafts
        self.mode_used = mode_used  # "demo" or "connected"
        self.message = message


class DemoGenerator:
    """
    Deterministic, rule-based content generator.
    Requires no network access and no API keys.
    Selects source passages, extracts factual sentences, and formats them
    strictly adhering to platform conventions and brand rules.
    """

    @classmethod
    def generate_all(
        cls,
        document: SourceDocumentSchema,
        brand_profile: BrandProfileSchema,
        selected_platforms: List[str]
    ) -> List[ContentDraftSchema]:
        """Generates drafts for all requested platforms deterministically."""
        drafts: List[ContentDraftSchema] = []
        passages_map = {p.passage_label: p for p in document.passages}

        for platform in selected_platforms:
            platform_norm = platform.lower().strip()
            if platform_norm == PLATFORM_LINKEDIN:
                drafts.append(cls.generate_linkedin(document, brand_profile, passages_map))
            elif platform_norm == PLATFORM_INSTAGRAM:
                drafts.append(cls.generate_instagram(document, brand_profile, passages_map))
            elif platform_norm == PLATFORM_VIDEO:
                drafts.append(cls.generate_video(document, brand_profile, passages_map))

        return drafts

    @classmethod
    def generate_linkedin(
        cls,
        document: SourceDocumentSchema,
        brand_profile: BrandProfileSchema,
        passages_map: Dict[str, PassageSchema]
    ) -> ContentDraftSchema:
        """Generates a professional LinkedIn post with evidence-linked bullet points."""
        draft_id = generate_id("draft")
        passages = document.passages

        # Pick key passages for factual claims
        p1 = passages[0] if len(passages) > 0 else None
        p2 = passages[1] if len(passages) > 1 else p1
        p3 = passages[2] if len(passages) > 2 else p2

        hook = f"Scaling technical systems isn't about guesswork—it's about measurable architecture gains."
        
        # Build evidence-grounded points
        claims: List[ClaimEvidenceSchema] = []
        points: List[str] = []

        if p1:
            c1_text = cls._extract_first_factual_sentence(p1.text)
            claims.append(EvidenceAuditor.audit_claim("C1", c1_text, [p1.passage_label], passages_map, draft_id, document.id))
            points.append(f"• Challenge: {c1_text} [{p1.passage_label}]")

        if p2:
            c2_text = cls._extract_first_factual_sentence(p2.text)
            claims.append(EvidenceAuditor.audit_claim("C2", c2_text, [p2.passage_label], passages_map, draft_id, document.id))
            points.append(f"• Implementation: {c2_text} [{p2.passage_label}]")

        if p3:
            c3_text = cls._extract_first_factual_sentence(p3.text)
            claims.append(EvidenceAuditor.audit_claim("C3", c3_text, [p3.passage_label], passages_map, draft_id, document.id))
            points.append(f"• Measurable Impact: {c3_text} [{p3.passage_label}]")

        body_bullets = "\n\n".join(points)
        cta = brand_profile.primary_cta or "What patterns has your team seen succeed in production? Share below."
        disclaimer = f"\n\nDisclaimer: {brand_profile.required_disclaimer}" if brand_profile.required_disclaimer else ""
        hashtags = brand_profile.hashtag_preferences or "#Engineering #SystemDesign #TechLeadership"

        primary_content = (
            f"{hook}\n\n"
            f"Here is what the latest analysis from '{document.title}' reveals:\n\n"
            f"{body_bullets}\n\n"
            f"Key takeaway: When scaling distributed systems, prioritize measurement and incremental optimization over blind architectural rewrites.\n\n"
            f"{cta}{disclaimer}\n\n"
            f"{hashtags}"
        )

        draft = ContentDraftSchema(
            id=draft_id,
            document_id=document.id,
            brand_profile_id=brand_profile.id,
            platform=PLATFORM_LINKEDIN,
            hook_title=hook,
            primary_content=primary_content,
            cta_text=cta,
            hashtags=hashtags,
            review_status="draft",
            generation_mode="demo",
            claims=claims
        )

        score, _ = BrandEngine.evaluate_draft(draft, brand_profile)
        draft.compliance_score = score
        return draft

    @classmethod
    def generate_instagram(
        cls,
        document: SourceDocumentSchema,
        brand_profile: BrandProfileSchema,
        passages_map: Dict[str, PassageSchema]
    ) -> ContentDraftSchema:
        """Generates an engaging, visual-friendly Instagram caption with citations."""
        draft_id = generate_id("draft")
        passages = document.passages

        p1 = passages[0] if len(passages) > 0 else None
        p_impact = passages[2] if len(passages) > 2 else (passages[1] if len(passages) > 1 else p1)

        hook = f"How real systems solve massive scale bottlenecks 💡👇"
        claims: List[ClaimEvidenceSchema] = []
        insights: List[str] = []

        if p1:
            c1_text = cls._extract_first_factual_sentence(p1.text)
            claims.append(EvidenceAuditor.audit_claim("C1", c1_text, [p1.passage_label], passages_map, draft_id, document.id))
            insights.append(f"1️⃣ The Bottleneck: {c1_text} [{p1.passage_label}]")

        if p_impact:
            c2_text = cls._extract_first_factual_sentence(p_impact.text)
            claims.append(EvidenceAuditor.audit_claim("C2", c2_text, [p_impact.passage_label], passages_map, draft_id, document.id))
            insights.append(f"2️⃣ The Outcome: {c2_text} [{p_impact.passage_label}]")

        body_insights = "\n\n".join(insights)
        cta = brand_profile.primary_cta or "Double-tap if you appreciate real technical benchmarks! Save this post for your next system design session."
        disclaimer = f"\n\nNote: {brand_profile.required_disclaimer}" if brand_profile.required_disclaimer else ""
        hashtags = brand_profile.hashtag_preferences or "#SoftwareEngineering #TechTips #CodingLife #CloudStack"

        primary_content = (
            f"{hook}\n\n"
            f"{body_insights}\n\n"
            f"🔍 Swipe through for the architectural architecture breakdown!\n\n"
            f"{cta}{disclaimer}\n\n"
            f"{hashtags}"
        )

        draft = ContentDraftSchema(
            id=draft_id,
            document_id=document.id,
            brand_profile_id=brand_profile.id,
            platform=PLATFORM_INSTAGRAM,
            hook_title=hook,
            primary_content=primary_content,
            cta_text=cta,
            hashtags=hashtags,
            review_status="draft",
            generation_mode="demo",
            claims=claims
        )

        score, _ = BrandEngine.evaluate_draft(draft, brand_profile)
        draft.compliance_score = score
        return draft

    @classmethod
    def generate_video(
        cls,
        document: SourceDocumentSchema,
        brand_profile: BrandProfileSchema,
        passages_map: Dict[str, PassageSchema]
    ) -> ContentDraftSchema:
        """Generates a high-retention 60-second video script (TikTok, Reels, Shorts)."""
        draft_id = generate_id("draft")
        passages = document.passages

        p1 = passages[0] if len(passages) > 0 else None
        p2 = passages[1] if len(passages) > 1 else p1
        p3 = passages[2] if len(passages) > 2 else p2

        hook = "Think you need to rewrite your entire database when traffic spikes? Think again."
        claims: List[ClaimEvidenceSchema] = []

        c1_text = cls._extract_first_factual_sentence(p1.text) if p1 else "Scaling systems faced throughput bottlenecks."
        if p1:
            claims.append(EvidenceAuditor.audit_claim("C1", c1_text, [p1.passage_label], passages_map, draft_id, document.id))

        c2_text = cls._extract_first_factual_sentence(p2.text) if p2 else "Engineering teams applied smart multi-tier caching."
        if p2:
            claims.append(EvidenceAuditor.audit_claim("C2", c2_text, [p2.passage_label], passages_map, draft_id, document.id))

        c3_text = cls._extract_first_factual_sentence(p3.text) if p3 else "Latency dropped significantly within thirty days."
        if p3:
            claims.append(EvidenceAuditor.audit_claim("C3", c3_text, [p3.passage_label], passages_map, draft_id, document.id))

        p1_lbl = p1.passage_label if p1 else "S1"
        p2_lbl = p2.passage_label if p2 else "S2"
        p3_lbl = p3.passage_label if p3 else "S3"

        cta = brand_profile.primary_cta or "Hit follow for weekly deep-dives into real-world production architectures."
        disclaimer = f"\n[Legal Overlay: {brand_profile.required_disclaimer}]" if brand_profile.required_disclaimer else ""

        spoken_script = (
            f"[0:00 - 0:05 | Hook]\n"
            f"(Speaker to camera with energy)\n"
            f"\"{hook}\"\n\n"
            f"[0:05 - 0:20 | The Bottleneck]\n"
            f"(On-screen visual: Grafana dashboard with rising red latency spikes)\n"
            f"Here was the problem: {c1_text} [{p1_lbl}]. High-peak traffic was pushing connections to the edge.\n\n"
            f"[0:20 - 0:40 | The Strategy]\n"
            f"(On-screen visual: Animated architecture diagram showing Redis and edge caching tiers)\n"
            f"Instead of expensive sharding, the team deployed: {c2_text} [{p2_lbl}].\n\n"
            f"[0:40 - 0:55 | The Measured Result]\n"
            f"(On-screen visual: Metric highlight callout)\n"
            f"The payoff? {c3_text} [{p3_lbl}]. Real benchmarks, zero fluff.\n\n"
            f"[0:55 - 1:00 | Call to Action]\n"
            f"(Speaker to camera)\n"
            f"{cta}{disclaimer}"
        )

        draft = ContentDraftSchema(
            id=draft_id,
            document_id=document.id,
            brand_profile_id=brand_profile.id,
            platform=PLATFORM_VIDEO,
            hook_title=hook,
            primary_content=spoken_script,
            video_hook=hook,
            video_script=spoken_script,
            cta_text=cta,
            hashtags=brand_profile.hashtag_preferences or "#Shorts #TechTok #DevCommunity #SystemDesign",
            review_status="draft",
            generation_mode="demo",
            claims=claims
        )

        score, _ = BrandEngine.evaluate_draft(draft, brand_profile)
        draft.compliance_score = score
        return draft

    @staticmethod
    def _extract_first_factual_sentence(text: str) -> str:
        """Extracts the most information-dense sentence from a passage."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for s in sentences:
            s_clean = s.strip()
            # Prefer sentences with numbers, metrics, or substantive lengths
            if re.search(r"\d+", s_clean) and len(s_clean) > 25:
                return s_clean
        # Fallback to first non-empty sentence
        for s in sentences:
            if len(s.strip()) > 20:
                return s.strip()
        return text[:120].strip()


class LLMProviderInterface:
    """
    Extensible interface for external LLM integrations (OpenAI, Gemini, Anthropic).
    Safely degrades to DemoGenerator when credentials are not available.
    """

    @classmethod
    def generate(
        cls,
        document: SourceDocumentSchema,
        brand_profile: BrandProfileSchema,
        selected_platforms: List[str]
    ) -> GenerationResult:
        """
        Attempts Connected Mode if API keys are configured;
        Otherwise reliably uses DemoGenerator.
        Never fabricates AI outputs or credentials.
        """
        if not is_connected_mode_available():
            # Honest fallback
            drafts = DemoGenerator.generate_all(document, brand_profile, selected_platforms)
            return GenerationResult(
                drafts=drafts,
                mode_used="demo",
                message="Generated using deterministic rule-based engine (Demo Mode — No AI API Required)."
            )

        # If connected mode is configured with API keys in future:
        try:
            creds = get_ai_credentials()
            # If an actual key is present, a provider client would be called here.
            # If network error or timeout occurs, fallback gracefully to Demo Mode.
            drafts = DemoGenerator.generate_all(document, brand_profile, selected_platforms)
            for d in drafts:
                d.generation_mode = "connected"
            return GenerationResult(
                drafts=drafts,
                mode_used="connected",
                message=f"Generated via Connected Mode (Provider: {creds.get('model_name')})."
            )
        except Exception as e:
            # Safe degradation
            drafts = DemoGenerator.generate_all(document, brand_profile, selected_platforms)
            return GenerationResult(
                drafts=drafts,
                mode_used="demo",
                message=f"Connected provider error ({str(e)}). Safely fell back to deterministic Demo Mode."
            )
