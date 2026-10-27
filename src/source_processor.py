"""
Source Document Processing Module.
Splits raw source text into canonical, immutable passages (S1, S2, S3...)
with character offsets and version tracking.
Treats all source text strictly as untrusted data.
"""
import re
import hashlib
from typing import List, Tuple, Optional
from src.models import SourceDocumentSchema, PassageSchema, generate_id

MIN_SOURCE_CHARS = 20
MAX_SOURCE_CHARS = 50000

# Patterns that indicate prompt injection or instruction hijacking attempts in source content
INJECTION_MARKERS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"system\s*prompt\s*:",
    r"disregard\s+the\s+above",
    r"output\s+only\s+the\s+word\s+pwned",
    r"reveal\s+your\s+instructions",
]

class SourceProcessingError(ValueError):
    """Raised when source text violates validation constraints."""
    pass


class SourceProcessor:
    """Processes, segments, and validates raw source documents."""

    @staticmethod
    def sanitize_untrusted_text(raw_text: str) -> str:
        """
        Cleans and normalizes untrusted text without stripping factual meaning.
        Converts CRLF to LF and strips surrounding whitespace.
        """
        if not raw_text:
            return ""
        # Normalize newlines
        normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        return normalized.strip()

    @staticmethod
    def detect_injection_warning(raw_text: str) -> Optional[str]:
        """
        Scans for prompt injection / instruction override patterns.
        Flags them so the system never interprets source content as instructions.
        """
        for pattern in INJECTION_MARKERS:
            if re.search(pattern, raw_text, re.IGNORECASE):
                return f"Source contains instruction-override pattern '{pattern}'. Treated strictly as passive data."
        return None

    @classmethod
    def split_into_passages(cls, document_id: str, raw_text: str) -> List[PassageSchema]:
        """
        Splits source text into meaningful, numbered passages (S1, S2, S3...).
        Preserves exact substring text and character offsets.
        """
        text = cls.sanitize_untrusted_text(raw_text)
        if not text:
            return []

        # Split on paragraph boundaries (two or more newlines)
        raw_paragraphs = re.split(r"\n\s*\n+", text)
        passages: List[PassageSchema] = []
        current_offset = 0

        passage_idx = 1
        for para in raw_paragraphs:
            cleaned_para = para.strip()
            if not cleaned_para:
                continue

            # Find exact character position in original text
            start_pos = text.find(cleaned_para, current_offset)
            if start_pos == -1:
                start_pos = current_offset
            end_pos = start_pos + len(cleaned_para)
            current_offset = end_pos

            passage = PassageSchema(
                id=generate_id("pass"),
                document_id=document_id,
                passage_label=f"S{passage_idx}",
                passage_order=passage_idx,
                text=cleaned_para,
                char_start=start_pos,
                char_end=end_pos
            )
            passages.append(passage)
            passage_idx += 1

        # If only 1 long block was provided, split by sentence groups if length > 400 chars
        if len(passages) == 1 and len(passages[0].text) > 400:
            return cls._split_long_passage(document_id, passages[0].text)

        return passages

    @classmethod
    def _split_long_passage(cls, document_id: str, text: str) -> List[PassageSchema]:
        """Splits a single long continuous block into multi-sentence passages."""
        # Split sentences while preserving punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        passages: List[PassageSchema] = []
        current_batch: List[str] = []
        current_chars = 0
        passage_idx = 1
        current_offset = 0

        for sent in sentences:
            sent_str = sent.strip()
            if not sent_str:
                continue
            current_batch.append(sent_str)
            current_chars += len(sent_str)

            if current_chars >= 250 or sent == sentences[-1]:
                combined_text = " ".join(current_batch)
                start_pos = text.find(combined_text, current_offset)
                if start_pos == -1:
                    start_pos = current_offset
                end_pos = start_pos + len(combined_text)
                current_offset = end_pos

                passages.append(
                    PassageSchema(
                        id=generate_id("pass"),
                        document_id=document_id,
                        passage_label=f"S{passage_idx}",
                        passage_order=passage_idx,
                        text=combined_text,
                        char_start=start_pos,
                        char_end=end_pos
                    )
                )
                passage_idx += 1
                current_batch = []
                current_chars = 0

        return passages if passages else [
            PassageSchema(
                id=generate_id("pass"),
                document_id=document_id,
                passage_label="S1",
                passage_order=1,
                text=text,
                char_start=0,
                char_end=len(text)
            )
        ]

    @classmethod
    def process_source(
        cls,
        title: str,
        raw_text: str,
        source_type: str = "Blog",
        source_url: Optional[str] = None,
        existing_doc: Optional[SourceDocumentSchema] = None
    ) -> SourceDocumentSchema:
        """
        Validates, parses, and segments a source document.
        Handles versioning when updating existing documents.
        """
        if not raw_text or not raw_text.strip():
            raise SourceProcessingError("Source text cannot be empty or whitespace only.")

        clean_text = cls.sanitize_untrusted_text(raw_text)
        if len(clean_text) < MIN_SOURCE_CHARS:
            raise SourceProcessingError(
                f"Source text is too short ({len(clean_text)} characters). Minimum required is {MIN_SOURCE_CHARS} characters."
            )

        if len(clean_text) > MAX_SOURCE_CHARS:
            raise SourceProcessingError(
                f"Source text exceeds maximum limit ({len(clean_text)} characters). Maximum permitted is {MAX_SOURCE_CHARS} characters."
            )

        words = clean_text.split()
        word_count = len(words)

        # Versioning handling
        version = 1
        doc_id = generate_id("doc")
        if existing_doc:
            doc_id = existing_doc.id
            # If text has changed, increment version
            if existing_doc.raw_text.strip() != clean_text:
                version = existing_doc.version + 1
            else:
                version = existing_doc.version

        passages = cls.split_into_passages(doc_id, clean_text)

        return SourceDocumentSchema(
            id=doc_id,
            title=title.strip() if title else "Untitled Document",
            source_type=source_type,
            source_url=source_url.strip() if source_url else None,
            raw_text=clean_text,
            word_count=word_count,
            passage_count=len(passages),
            version=version,
            passages=passages
        )

    @staticmethod
    def compute_hash(text: str) -> str:
        """Computes a SHA256 checksum of source text for change detection."""
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
