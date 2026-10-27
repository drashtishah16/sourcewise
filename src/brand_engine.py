"""
Brand Compliance and Content Quality Engine.
Enforces brand terminology, forbidden word bans, mandatory disclaimers,
call-to-action requirements, and platform-specific length constraints.
Provides explainable feedback with suggested corrections.
"""
import re
from typing import List, Dict, Any, Tuple
from src.models import BrandProfileSchema, ContentDraftSchema

class BrandCheckResult:
    """Represents the outcome of an individual compliance rule check."""
    def __init__(self, rule_name: str, status: str, explanation: str, suggested_correction: str = ""):
        self.rule_name = rule_name
        self.status = status  # 'PASS', 'WARNING', 'FAIL'
        self.explanation = explanation
        self.suggested_correction = suggested_correction

    def to_dict(self) -> Dict[str, str]:
        return {
            "rule": self.rule_name,
            "status": self.status,
            "explanation": self.explanation,
            "suggested_correction": self.suggested_correction
        }


class BrandEngine:
    """Evaluates drafts against brand profiles and platform standards."""

    @classmethod
    def check_forbidden_terms(cls, text: str, forbidden_terms: List[str]) -> List[BrandCheckResult]:
        """Flags any banned or risky terminology."""
        results: List[BrandCheckResult] = []
        if not forbidden_terms:
            return results

        text_lower = text.lower()
        for term in forbidden_terms:
            term_clean = term.strip().lower()
            if not term_clean:
                continue
            # Word boundary matching
            pattern = r"\b" + re.escape(term_clean) + r"\b"
            if re.search(pattern, text_lower):
                results.append(BrandCheckResult(
                    rule_name="Forbidden Terminology",
                    status="FAIL",
                    explanation=f"Draft contains forbidden term '{term}'.",
                    suggested_correction=f"Remove or replace '{term}' with compliant terminology."
                ))
        return results

    @classmethod
    def check_preferred_terms(cls, text: str, preferred_terms: List[str]) -> List[BrandCheckResult]:
        """Checks if key brand terms are incorporated."""
        results: List[BrandCheckResult] = []
        if not preferred_terms:
            return results

        text_lower = text.lower()
        missing_terms = []
        for term in preferred_terms:
            term_clean = term.strip().lower()
            if not term_clean:
                continue
            pattern = r"\b" + re.escape(term_clean) + r"\b"
            if not re.search(pattern, text_lower):
                missing_terms.append(term)

        if missing_terms:
            results.append(BrandCheckResult(
                rule_name="Preferred Terminology",
                status="WARNING",
                explanation=f"Consider including key brand terminology: {', '.join(missing_terms[:3])}.",
                suggested_correction=f"Weave preferred terms like '{missing_terms[0]}' into the narrative."
            ))
        else:
            results.append(BrandCheckResult(
                rule_name="Preferred Terminology",
                status="PASS",
                explanation="All key preferred brand terms are present."
            ))
        return results

    @classmethod
    def check_disclaimer(cls, text: str, required_disclaimer: str) -> BrandCheckResult:
        """Verifies inclusion of legal/performance disclaimer if mandated."""
        if not required_disclaimer or not required_disclaimer.strip():
            return BrandCheckResult("Mandatory Disclaimer", "PASS", "No disclaimer required for this brand profile.")

        disclaimer_clean = required_disclaimer.strip().lower()
        # Check if substantive portion is present
        key_words = [w for w in re.findall(r"\w+", disclaimer_clean) if len(w) > 3]
        text_lower = text.lower()

        matched = [w for w in key_words if w in text_lower]
        match_ratio = len(matched) / max(len(key_words), 1)

        if match_ratio >= 0.6:
            return BrandCheckResult("Mandatory Disclaimer", "PASS", "Required disclaimer is present.")
        else:
            return BrandCheckResult(
                rule_name="Mandatory Disclaimer",
                status="FAIL",
                explanation="Required brand disclaimer is missing or incomplete.",
                suggested_correction=f"Append the disclaimer: '{required_disclaimer}'"
            )

    @classmethod
    def check_cta(cls, draft: ContentDraftSchema, primary_cta: str) -> BrandCheckResult:
        """Checks for the presence of a Call to Action."""
        if not primary_cta or not primary_cta.strip():
            return BrandCheckResult("Call to Action", "PASS", "No CTA configured in brand profile.")

        combined_text = f"{draft.primary_content} {draft.cta_text or ''}".lower()
        cta_words = [w for w in re.findall(r"\w+", primary_cta.lower()) if len(w) > 3]

        if not cta_words:
            return BrandCheckResult("Call to Action", "PASS", "CTA configured.")

        matched = [w for w in cta_words if w in combined_text]
        if len(matched) / len(cta_words) >= 0.5 or (draft.cta_text and len(draft.cta_text.strip()) > 5):
            return BrandCheckResult("Call to Action", "PASS", "Call to Action is included.")
        else:
            return BrandCheckResult(
                rule_name="Call to Action",
                status="WARNING",
                explanation="Primary CTA is absent or significantly modified.",
                suggested_correction=f"Include CTA: '{primary_cta}'"
            )

    @classmethod
    def check_length(cls, draft: ContentDraftSchema, length_prefs: Dict[str, Any]) -> BrandCheckResult:
        """Validates draft length against platform-specific targets."""
        words = draft.primary_content.split()
        word_count = len(words)
        platform = draft.platform.lower()

        if platform == "linkedin":
            min_w = length_prefs.get("linkedin_min", 80)
            max_w = length_prefs.get("linkedin_max", 350)
            if word_count < min_w:
                return BrandCheckResult(
                    "Content Length",
                    "WARNING",
                    f"LinkedIn draft is {word_count} words (recommended minimum: {min_w} words).",
                    "Add supporting context or breakdown of the findings."
                )
            elif word_count > max_w:
                return BrandCheckResult(
                    "Content Length",
                    "WARNING",
                    f"LinkedIn draft is {word_count} words (recommended maximum: {max_w} words).",
                    "Trim secondary elaboration to keep readers engaged."
                )
            return BrandCheckResult("Content Length", "PASS", f"Optimal length ({word_count} words).")

        elif platform == "instagram":
            min_w = length_prefs.get("instagram_min", 40)
            max_w = length_prefs.get("instagram_max", 250)
            if word_count < min_w:
                return BrandCheckResult(
                    "Content Length",
                    "WARNING",
                    f"Instagram caption is {word_count} words (recommended minimum: {min_w} words).",
                    "Provide a bit more context before the hashtags."
                )
            elif word_count > max_w:
                return BrandCheckResult(
                    "Content Length",
                    "WARNING",
                    f"Instagram caption is {word_count} words (recommended maximum: {max_w} words).",
                    "Shorten caption for better mobile readability."
                )
            return BrandCheckResult("Content Length", "PASS", f"Optimal length ({word_count} words).")

        elif platform == "video_script":
            # 130 words per minute ~ 2.16 words per second
            target_sec = length_prefs.get("video_seconds", 60)
            target_words = int(target_sec * 2.2)
            script_words = len((draft.video_script or draft.primary_content).split())
            diff = abs(script_words - target_words)
            if diff > 40:
                est_sec = int(script_words / 2.2)
                return BrandCheckResult(
                    "Video Duration",
                    "WARNING",
                    f"Script is {script_words} words (~{est_sec} seconds). Target is {target_sec} seconds.",
                    f"Adjust pacing or script volume toward {target_words} words."
                )
            return BrandCheckResult("Video Duration", "PASS", f"Good speaking length ({script_words} words, ~{target_sec}s).")

        return BrandCheckResult("Content Length", "PASS", f"Length: {word_count} words.")

    @classmethod
    def evaluate_draft(cls, draft: ContentDraftSchema, profile: BrandProfileSchema) -> Tuple[int, List[BrandCheckResult]]:
        """
        Runs comprehensive brand audit on draft.
        Returns compliance score (0-100) and list of detailed check results.
        """
        checks: List[BrandCheckResult] = []
        combined_text = f"{draft.hook_title}\n{draft.primary_content}\n{draft.cta_text or ''}\n{draft.hashtags or ''}"

        # 1. Forbidden terms
        checks.extend(cls.check_forbidden_terms(combined_text, profile.forbidden_terminology))

        # 2. Preferred terms
        checks.extend(cls.check_preferred_terms(combined_text, profile.preferred_terminology))

        # 3. Disclaimer
        if profile.required_disclaimer:
            checks.append(cls.check_disclaimer(combined_text, profile.required_disclaimer))

        # 4. CTA
        if profile.primary_cta:
            checks.append(cls.check_cta(draft, profile.primary_cta))

        # 5. Length
        checks.append(cls.check_length(draft, profile.content_length_prefs or {}))

        # Calculate compliance score
        score = 100
        for c in checks:
            if c.status == "FAIL":
                score -= 30
            elif c.status == "WARNING":
                score -= 10
        score = max(0, min(100, score))

        return score, checks

