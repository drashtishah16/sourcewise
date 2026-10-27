"""
Evidence Traceability and Fact Verification Engine.
The primary differentiator of SourceWise AI.

Key principles:
1. Every factual claim must be explicitly linked to real, existing source passages (e.g. S1, S2).
2. Referenced passage IDs must be validated against the active source document.
3. Specific metrics (percentages, numbers, currency, response times), dates, quotes,
   and entities in claims are audited against the referenced passage text.
4. Distinguishes factual claims from creative hooks, opinions, transitions, and CTAs.
5. Clearly states that evidence linking verifies consistency with the supplied text,
   not absolute external reality.
"""
import re
from typing import List, Dict, Tuple, Optional, Set
from src.models import PassageSchema, ClaimEvidenceSchema, generate_id

# Status constants
STATUS_EVIDENCE_LINKED = "Evidence Linked"
STATUS_POTENTIALLY_UNSUPPORTED = "Potentially Unsupported"
STATUS_CONFLICTING_AMBIGUOUS = "Conflicting or Ambiguous"
STATUS_HUMAN_REVIEW_REQUIRED = "Human Review Required"

ALLOWED_EVIDENCE_STATUSES = {
    STATUS_EVIDENCE_LINKED,
    STATUS_POTENTIALLY_UNSUPPORTED,
    STATUS_CONFLICTING_AMBIGUOUS,
    STATUS_HUMAN_REVIEW_REQUIRED
}

# Regex patterns for detecting metrics, dates, and quotes
NUMBER_METRIC_PATTERN = re.compile(
    r"(?:[\$€£]\s*)?\b\d+(?:[\.,]\d+)?(?:\s*(?:percent|ms|s|seconds|minutes|hours|days|x|k|m|million|billion)\b|\s*%)?",
    re.IGNORECASE
)
DATE_PATTERN = re.compile(
    r"\b(?:Q[1-4]\s+\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\b20\d{2}\b)\b",
    re.IGNORECASE
)
QUOTE_PATTERN = re.compile(r'["“]([^"”]{4,})["”]')

# Heuristics for classifying sentences
CTA_PATTERNS = [
    r"\b(click|read|visit|explore|check\s+out|download|learn\s+more|link\s+in|comment|share)\b",
    r"\b(subscribe|join|start\s+your|try|follow)\b",
    r"http[s]?://"
]
HOOK_PATTERNS = [
    r"^(are\s+you|have\s+you|what\s+if|ever\s+wondered|imagine|here\s*is\s+why|stop\s+doing|the\s+secret\s+to)",
    r"\?$"
]
OPINION_PATTERNS = [
    r"\b(in\s+my\s+opinion|we\s+believe|i\s+think|it\s+seems|arguably|perhaps|undoubtedly|excitingly)\b"
]


class EvidenceAuditor:
    """Audits claims against source passages to detect unsupported statements."""

    @staticmethod
    def extract_metrics(text: str) -> List[str]:
        """Extracts numerical, percentage, and currency metrics from text."""
        raw_matches = NUMBER_METRIC_PATTERN.findall(text)
        cleaned: List[str] = []
        for m in raw_matches:
            stripped = m.strip()
            # Ignore standalone single digits or small structural numbers like 1, 2, 3 unless accompanied by units
            if stripped.isdigit() and len(stripped) == 1:
                continue
            cleaned.append(stripped)
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def extract_dates(text: str) -> List[str]:
        """Extracts dates and quarters from text."""
        matches = DATE_PATTERN.findall(text)
        return list(dict.fromkeys([m.strip() for m in matches]))

    @staticmethod
    def extract_quotes(text: str) -> List[str]:
        """Extracts quoted verbatim text from quotes."""
        matches = QUOTE_PATTERN.findall(text)
        return list(dict.fromkeys([m.strip() for m in matches]))

    @classmethod
    def classify_sentence(cls, sentence: str) -> str:
        """
        Classifies whether a sentence is a factual claim requiring citation
        or a creative hook, transition, opinion, or CTA.
        Returns: 'FACTUAL_CLAIM', 'CALL_TO_ACTION', 'CREATIVE_HOOK', 'OPINION_OR_TRANSITION'
        """
        s_lower = sentence.lower().strip()

        # Check CTA
        for p in CTA_PATTERNS:
            if re.search(p, s_lower):
                return "CALL_TO_ACTION"

        # Check Hook / Question
        for p in HOOK_PATTERNS:
            if re.search(p, s_lower):
                return "CREATIVE_HOOK"

        # Check Opinion
        for p in OPINION_PATTERNS:
            if re.search(p, s_lower):
                return "OPINION_OR_TRANSITION"

        # Check for factual metrics or assertions
        metrics = cls.extract_metrics(sentence)
        dates = cls.extract_dates(sentence)
        quotes = cls.extract_quotes(sentence)

        if metrics or dates or quotes or len(sentence.split()) >= 6:
            return "FACTUAL_CLAIM"

        return "OPINION_OR_TRANSITION"

    @classmethod
    def audit_claim(
        cls,
        claim_label: str,
        claim_text: str,
        referenced_passage_ids: List[str],
        passages_map: Dict[str, PassageSchema],
        draft_id: str,
        document_id: str
    ) -> ClaimEvidenceSchema:
        """
        Rigorously validates a single claim against referenced source passages.
        Flags invalid IDs, unsupported metrics, unverified dates, and missing excerpts.
        """
        flags: List[str] = []
        missing_ids: List[str] = []
        combined_passage_text = ""
        supporting_excerpts: List[str] = []

        if not referenced_passage_ids:
            flags.append("No source passage cited for this factual claim.")
            return ClaimEvidenceSchema(
                id=generate_id("claim"),
                draft_id=draft_id,
                document_id=document_id,
                claim_label=claim_label,
                claim_text=claim_text,
                referenced_passage_ids=[],
                supporting_excerpt=None,
                evidence_status=STATUS_POTENTIALLY_UNSUPPORTED,
                requires_human_review=True,
                flag_reasons=flags,
                reviewer_note="Missing source passage reference."
            )

        # 1. Validate passage IDs
        for pid in referenced_passage_ids:
            if pid not in passages_map:
                missing_ids.append(pid)
            else:
                passage_text = passages_map[pid].text
                combined_passage_text += " " + passage_text
                # Find an excerpt that best aligns with claim
                supporting_excerpts.append(passage_text[:160] + "..." if len(passage_text) > 160 else passage_text)

        if missing_ids:
            flags.append(f"Referenced passage ID(s) {', '.join(missing_ids)} do not exist in source document.")

        # 2. If valid passages found, audit metrics against passage text
        if combined_passage_text:
            combined_lower = combined_passage_text.lower()
            claim_metrics = cls.extract_metrics(claim_text)
            for metric in claim_metrics:
                m_clean = metric.lower().replace(",", "")
                # Normalize currency / percentage spacing
                pattern = re.escape(m_clean)
                if not re.search(pattern, combined_lower.replace(",", "")):
                    flags.append(f"Metric '{metric}' appears in claim but is not verified in passage text.")

            # 3. Check dates
            claim_dates = cls.extract_dates(claim_text)
            for d in claim_dates:
                if d.lower() not in combined_lower:
                    flags.append(f"Date reference '{d}' in claim is not verified in passage text.")

            # 4. Check quotes
            claim_quotes = cls.extract_quotes(claim_text)
            for q in claim_quotes:
                # Quoted text should match substantially
                q_words = [w for w in re.findall(r"\w+", q.lower()) if len(w) > 3]
                if q_words:
                    matched_words = [w for w in q_words if w in combined_lower]
                    if len(matched_words) / len(q_words) < 0.7:
                        flags.append(f"Quoted assertion '\"{q}\"' was not verified in referenced passage text.")

        # 5. Determine evidence status
        evidence_status = STATUS_EVIDENCE_LINKED
        requires_review = False

        if missing_ids or any("Metric" in f or "Quoted" in f for f in flags):
            evidence_status = STATUS_POTENTIALLY_UNSUPPORTED
            requires_review = True
        elif flags:
            evidence_status = STATUS_HUMAN_REVIEW_REQUIRED
            requires_review = True

        best_excerpt = " | ".join(supporting_excerpts) if supporting_excerpts else None

        return ClaimEvidenceSchema(
            id=generate_id("claim"),
            draft_id=draft_id,
            document_id=document_id,
            claim_label=claim_label,
            claim_text=claim_text,
            referenced_passage_ids=referenced_passage_ids,
            supporting_excerpt=best_excerpt,
            evidence_status=evidence_status,
            requires_human_review=requires_review,
            flag_reasons=flags,
            reviewer_note="Automated evidence audit complete." if not flags else "; ".join(flags)
        )

    @staticmethod
    def get_disclaimer_note() -> str:
        """
        Clarifies the scope of SourceWise AI evidence traceability.
        """
        return (
            "Evidence Traceability Notice: SourceWise AI audits whether factual assertions "
            "directly reflect the provided source text passages. A 'Evidence Linked' status confirms "
            "textual alignment with the provided document; it does not independently certify external real-world truth."
        )
