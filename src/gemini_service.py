"""
Google Gemini AI Generation Service for SourceWise AI.
Uses the official Google GenAI Python SDK (google-genai) to repurpose long-form
technical sources into platform-optimized social posts with strict factual grounding
and evidence traceability.
"""
import json
import logging
import re
from typing import List, Dict, Optional, Any

from src.models import (
    SourceDocumentSchema,
    BrandProfileSchema,
    ContentDraftSchema,
    ClaimEvidenceSchema,
    PassageSchema,
    generate_id
)
from src.evidence_engine import EvidenceAuditor, STATUS_EVIDENCE_LINKED, STATUS_POTENTIALLY_UNSUPPORTED
from src.brand_engine import BrandEngine
from src.config import get_gemini_api_key, get_gemini_model

logger = logging.getLogger(__name__)

PLATFORM_LINKEDIN = "linkedin"
PLATFORM_INSTAGRAM = "instagram"
PLATFORM_VIDEO = "video_script"


class GeminiGenerationError(Exception):
    """Raised when Gemini content generation fails or credentials are invalid."""
    pass


def sanitize_ai_error(raw_error: Any) -> str:
    """Masks API keys, authorization tokens, and sensitive headers from error messages."""
    if not raw_error:
        return "Unknown AI provider error."
    msg = str(raw_error)
    # Mask key query parameters or headers like key=AIza...
    msg = re.sub(r"(key|api_key|token|secret)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]+['\"]?", r"\1=***", msg, flags=re.IGNORECASE)
    # Mask common Google API key pattern (AIzaSy...)
    msg = re.sub(r"AIzaSy[a-zA-Z0-9_\-]{33}", "AIzaSy***", msg)
    return msg


class GeminiGenerator:
    """
    Interfaces with Google Gemini via the official google-genai SDK.
    Generates platform-tailored social drafts strictly anchored to source passages.
    """

    @classmethod
    def generate_all(
        cls,
        document: SourceDocumentSchema,
        brand_profile: BrandProfileSchema,
        selected_platforms: List[str],
        api_key: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> List[ContentDraftSchema]:
        """
        Generates content drafts for all requested platforms using the Gemini API.
        Does NOT silently fall back to Demo Mode on failure.
        """
        resolved_key = api_key or get_gemini_api_key()
        if not resolved_key:
            raise GeminiGenerationError(
                "Gemini API key is not configured. Please add GEMINI_API_KEY to your environment or Streamlit Secrets."
            )

        resolved_model = model_name or get_gemini_model()

        try:
            from google import genai
            from google.genai import types
            clean_key = resolved_key.strip().strip("'\"")
            client = genai.Client(api_key=clean_key)
        except Exception as client_err:
            safe_msg = sanitize_ai_error(client_err)
            raise GeminiGenerationError(f"Failed to initialize Google GenAI client: {safe_msg}")

        passages_map = {p.passage_label: p for p in document.passages}
        drafts: List[ContentDraftSchema] = []

        for platform in selected_platforms:
            platform_norm = platform.lower().strip()
            draft = cls._generate_platform_draft(
                client=client,
                model_name=resolved_model,
                document=document,
                brand_profile=brand_profile,
                platform=platform_norm,
                passages_map=passages_map
            )
            drafts.append(draft)

        return drafts

    @classmethod
    def _generate_platform_draft(
        cls,
        client: Any,
        model_name: str,
        document: SourceDocumentSchema,
        brand_profile: BrandProfileSchema,
        platform: str,
        passages_map: Dict[str, PassageSchema]
    ) -> ContentDraftSchema:
        """Calls Gemini API for a single platform, parses structured output, and audits claims."""
        from google.genai import types

        draft_id = generate_id("draft")
        system_instruction = (
            "You are SourceWise AI's factual content repurposing engine. "
            "Your task is to repurpose technical engineering case studies and whitepapers "
            "into high-impact social media posts strictly anchored in the provided numbered source passages. "
            "CRITICAL EVIDENCE GROUNDING RULES:\n"
            "1. Every factual assertion must cite its supporting passage label in brackets like [S1], [S2].\n"
            "2. Never invent passage labels (e.g. do not cite [S99] if only [S1] through [S4] exist).\n"
            "3. Do not invent, alter, or exaggerate metrics, percentages, dollar amounts, benchmarks, or quotes.\n"
            "4. Strictly adhere to the brand profile guidelines, forbidden terms, CTAs, and disclaimers.\n"
            "5. Respond ONLY with valid, minified or structured JSON matching the requested schema."
        )

        passages_text = "\n\n".join(
            [f"[{p.passage_label}] {p.text}" for p in document.passages]
        )

        brand_context = (
            f"Brand Name: {brand_profile.name}\n"
            f"Target Audience: {brand_profile.target_audience}\n"
            f"Tone of Voice: {brand_profile.tone_of_voice}\n"
            f"Preferred Terms: {', '.join(brand_profile.preferred_terminology) if brand_profile.preferred_terminology else 'None'}\n"
            f"Forbidden Terms (DO NOT USE ANY OF THESE): {', '.join(brand_profile.forbidden_terminology) if brand_profile.forbidden_terminology else 'None'}\n"
            f"Primary Call to Action: {brand_profile.primary_cta or 'None'}\n"
            f"Required Disclaimer: {brand_profile.required_disclaimer or 'None'}"
        )

        platform_specs = {
            PLATFORM_LINKEDIN: (
                "Format: Professional LinkedIn Thought Leadership Post.\n"
                "- Strong problem-oriented hook opening line (no hashtags on first line).\n"
                "- 3 to 4 clear, evidence-linked bullet points citing [S1], [S2] etc.\n"
                "- Key architectural or business takeaway.\n"
                "- Mandatory CTA and Disclaimer if specified in Brand Context.\n"
                "- Relevant professional hashtags at the very end."
            ),
            PLATFORM_INSTAGRAM: (
                "Format: Instagram Educational Carousel / Feed Caption.\n"
                "- High-energy, punchy opening hook with relevant emoji.\n"
                "- Mobile-optimized scannable takeaways with passage citations [S1], [S2].\n"
                "- Swipe / save call to action.\n"
                "- Disclaimer if specified.\n"
                "- Curated hashtag cluster at the end."
            ),
            PLATFORM_VIDEO: (
                "Format: 60-Second Short-Form Video Script (TikTok / Reels / Shorts).\n"
                "- Timestamped script: [0:00 - 0:05 | Hook], [0:05 - 0:20 | Context & Problem], "
                "[0:20 - 0:40 | Implementation Strategy], [0:40 - 0:55 | Measured Results], [0:55 - 1:00 | CTA].\n"
                "- Include on-screen visual directions in parentheses and spoken voiceover cues citing [S1], [S2].\n"
                "- Keep spoken dialogue natural and under 150 words total."
            )
        }

        spec = platform_specs.get(platform, "Format: Social post with factual citations [S1], [S2].")

        user_prompt = f"""DOCUMENT TITLE: {document.title}
SOURCE TYPE: {document.source_type}

AVAILABLE CANONICAL PASSAGES:
{passages_text}

BRAND & AUDIENCE CONSTRAINTS:
{brand_context}

TARGET PLATFORM SPECIFICATION:
{spec}

REQUIRED JSON OUTPUT FORMAT:
{{
  "hook_title": "Short compelling headline/hook",
  "primary_content": "Full post text, formatted with linebreaks and citations like [S1]",
  "cta_text": "Primary CTA text used",
  "hashtags": "#Relevant #Hashtags",
  "video_hook": "Video hook text (only if video_script, else empty string)",
  "video_script": "Full video script with timestamps (only if video_script, else empty string)",
  "claims": [
    {{
      "claim_label": "C1",
      "claim_text": "Specific factual claim asserted in the post",
      "referenced_passage_ids": ["S1"],
      "supporting_excerpt": "Exact excerpt from passage supporting this claim"
    }}
  ]
}}"""

        models_to_try = [model_name]
        for candidate in ("gemini-2.0-flash", "gemini-2.5-flash"):
            if candidate not in models_to_try:
                models_to_try.append(candidate)

        response = None
        last_error_msg = ""

        for candidate_model in models_to_try:
            try:
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.2
                )
                response = client.models.generate_content(
                    model=candidate_model,
                    contents=user_prompt,
                    config=config
                )
                if response:
                    break
            except Exception as api_err:
                safe_msg = sanitize_ai_error(api_err)
                last_error_msg = safe_msg
                # If API key itself is invalid, fail immediately without cycling models
                if "api_key_invalid" in safe_msg.lower() or "api key not valid" in safe_msg.lower():
                    logger.error("Gemini API key is invalid: %s", safe_msg)
                    raise GeminiGenerationError(f"API key not valid: {safe_msg}")
                logger.warning("Candidate model %s call failed: %s. Trying next...", candidate_model, safe_msg)

        if response is None:
            raise GeminiGenerationError(f"Gemini API generation failed across candidate models: {last_error_msg}")

        # Parse response JSON
        raw_text = response.text if hasattr(response, "text") and response.text else "{}"
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback regex extraction if model wrapped JSON in markdown code fences
            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except Exception:
                    data = {}
            else:
                data = {}

        hook_title = data.get("hook_title") or f"{document.title} — Key Insights"
        primary_content = data.get("primary_content") or raw_text
        cta_text = data.get("cta_text") or brand_profile.primary_cta
        hashtags = data.get("hashtags") or brand_profile.hashtag_preferences
        video_hook = data.get("video_hook") if platform == PLATFORM_VIDEO else None
        video_script = data.get("video_script") or (primary_content if platform == PLATFORM_VIDEO else None)

        # Audit and ground claims
        claims: List[ClaimEvidenceSchema] = []
        raw_claims = data.get("claims", [])
        if isinstance(raw_claims, list) and raw_claims:
            for idx, c in enumerate(raw_claims):
                if not isinstance(c, dict):
                    continue
                label = c.get("claim_label") or f"C{idx + 1}"
                text_c = c.get("claim_text") or ""
                pids = c.get("referenced_passage_ids") or []
                if isinstance(pids, str):
                    pids = [pids]
                if text_c:
                    audited_claim = EvidenceAuditor.audit_claim(
                        claim_label=label,
                        claim_text=text_c,
                        referenced_passage_ids=pids,
                        passages_map=passages_map,
                        draft_id=draft_id,
                        document_id=document.id
                    )
                    claims.append(audited_claim)

        # If no explicit claims were parsed from JSON, extract sentences citing [S#]
        if not claims:
            extracted_claims = cls._extract_claims_from_content(
                content=primary_content,
                passages_map=passages_map,
                draft_id=draft_id,
                document_id=document.id
            )
            claims.extend(extracted_claims)

        # Assemble draft schema
        draft = ContentDraftSchema(
            id=draft_id,
            document_id=document.id,
            brand_profile_id=brand_profile.id,
            platform=platform,
            hook_title=hook_title,
            primary_content=primary_content,
            cta_text=cta_text,
            hashtags=hashtags,
            video_hook=video_hook,
            video_script=video_script,
            review_status="draft",
            generation_mode="gemini",
            claims=claims
        )

        # Brand governance evaluation
        score, _ = BrandEngine.evaluate_draft(draft, brand_profile)
        draft.compliance_score = score
        return draft

    @classmethod
    def _extract_claims_from_content(
        cls,
        content: str,
        passages_map: Dict[str, PassageSchema],
        draft_id: str,
        document_id: str
    ) -> List[ClaimEvidenceSchema]:
        """Scans generated text for passage references and constructs audited claims."""
        claims: List[ClaimEvidenceSchema] = []
        sentences = re.split(r"(?<=[.!?])\s+", content.strip())
        claim_idx = 1

        for s in sentences:
            citations = re.findall(r"\[(S\d+)\]", s)
            if citations:
                clean_sentence = re.sub(r"\[S\d+\]", "", s).strip()
                if len(clean_sentence) > 15:
                    audited = EvidenceAuditor.audit_claim(
                        claim_label=f"C{claim_idx}",
                        claim_text=clean_sentence,
                        referenced_passage_ids=citations,
                        passages_map=passages_map,
                        draft_id=draft_id,
                        document_id=document_id
                    )
                    claims.append(audited)
                    claim_idx += 1

        # Fallback if no citations found in text: create audited claim on first passage
        if not claims and passages_map:
            first_label = sorted(passages_map.keys())[0]
            first_sentence = sentences[0].strip() if sentences else "Factual overview statement."
            claims.append(
                EvidenceAuditor.audit_claim(
                    claim_label="C1",
                    claim_text=first_sentence,
                    referenced_passage_ids=[first_label],
                    passages_map=passages_map,
                    draft_id=draft_id,
                    document_id=document_id
                )
            )

        return claims
