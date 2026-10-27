"""
Export Service for SourceWise AI.
Generates robust, Unicode-compliant CSV and JSON exports for content drafts,
evidence citations, review statuses, and source document metadata.
Ensures zero leakage of credentials or internal system configuration.
"""
import io
import csv
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from src.models import ContentDraftSchema, SourceDocumentSchema

class ExportService:
    """Handles structured data exports to CSV and JSON formats."""

    @classmethod
    def to_csv(
        cls,
        drafts: List[ContentDraftSchema],
        document: Optional[SourceDocumentSchema] = None
    ) -> str:
        """
        Converts drafts and their evidence links into RFC 4180 compliant CSV string.
        Properly escapes commas, quotes, newlines, and Unicode emojis.
        """
        output = io.StringIO()
        fieldnames = [
            "draft_id",
            "platform",
            "hook_title",
            "primary_content",
            "cta_text",
            "hashtags",
            "video_hook",
            "video_script",
            "source_title",
            "source_url",
            "claim_ids",
            "referenced_passages",
            "evidence_statuses",
            "flag_reasons",
            "review_status",
            "compliance_score",
            "generation_mode",
            "created_at",
            "approved_at"
        ]

        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            quoting=csv.QUOTE_ALL,
            lineterminator="\r\n"
        )
        writer.writeheader()

        doc_title = document.title if document else ""
        doc_url = document.source_url if document else ""

        for draft in drafts:
            # Aggregate claim metrics
            claim_ids = ", ".join([c.claim_label for c in draft.claims])
            passages = ", ".join(list(dict.fromkeys([
                p for c in draft.claims for p in c.referenced_passage_ids
            ])))
            statuses = ", ".join(list(dict.fromkeys([c.evidence_status for c in draft.claims])))
            flags = "; ".join([r for c in draft.claims for r in c.flag_reasons if r])

            row = {
                "draft_id": draft.id,
                "platform": draft.platform,
                "hook_title": draft.hook_title,
                "primary_content": draft.primary_content,
                "cta_text": draft.cta_text or "",
                "hashtags": draft.hashtags or "",
                "video_hook": draft.video_hook or "",
                "video_script": draft.video_script or "",
                "source_title": doc_title,
                "source_url": doc_url or "",
                "claim_ids": claim_ids,
                "referenced_passages": passages,
                "evidence_statuses": statuses,
                "flag_reasons": flags,
                "review_status": draft.review_status,
                "compliance_score": draft.compliance_score,
                "generation_mode": draft.generation_mode,
                "created_at": draft.created_at.isoformat() if draft.created_at else "",
                "approved_at": draft.approved_at.isoformat() if draft.approved_at else ""
            }
            writer.writerow(row)

        return output.getvalue()

    @classmethod
    def to_json(
        cls,
        drafts: List[ContentDraftSchema],
        document: Optional[SourceDocumentSchema] = None
    ) -> str:
        """
        Converts drafts and evidence traceability metadata into structured JSON.
        Handles nested claims, timestamps, and UTF-8 characters.
        """
        payload: Dict[str, Any] = {
            "metadata": {
                "export_version": "1.0",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_drafts": len(drafts),
                "source_document": {
                    "id": document.id if document else None,
                    "title": document.title if document else None,
                    "source_type": document.source_type if document else None,
                    "source_url": document.source_url if document else None,
                    "version": document.version if document else None,
                    "word_count": document.word_count if document else 0,
                    "passage_count": document.passage_count if document else 0
                } if document else None
            },
            "drafts": []
        }

        for draft in drafts:
            draft_dict = {
                "id": draft.id,
                "document_id": draft.document_id,
                "brand_profile_id": draft.brand_profile_id,
                "platform": draft.platform,
                "hook_title": draft.hook_title,
                "primary_content": draft.primary_content,
                "cta_text": draft.cta_text,
                "hashtags": draft.hashtags,
                "video_hook": draft.video_hook,
                "video_script": draft.video_script,
                "review_status": draft.review_status,
                "approval_notes": draft.approval_notes,
                "approved_at": draft.approved_at.isoformat() if draft.approved_at else None,
                "generation_mode": draft.generation_mode,
                "compliance_score": draft.compliance_score,
                "created_at": draft.created_at.isoformat() if draft.created_at else None,
                "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
                "claims": [
                    {
                        "id": c.id,
                        "claim_label": c.claim_label,
                        "claim_text": c.claim_text,
                        "referenced_passage_ids": c.referenced_passage_ids,
                        "supporting_excerpt": c.supporting_excerpt,
                        "evidence_status": c.evidence_status,
                        "requires_human_review": c.requires_human_review,
                        "flag_reasons": c.flag_reasons,
                        "reviewer_note": c.reviewer_note
                    }
                    for c in draft.claims
                ]
            }
            payload["drafts"].append(draft_dict)

        return json.dumps(payload, indent=2, ensure_ascii=False)
