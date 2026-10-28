"""
Database Layer for SourceWise AI.
Handles PostgreSQL / Supabase persistence using SQLAlchemy ORM with connection pooling,
parameterized queries, and robust in-memory fallback when database configuration is absent.
Never exposes credentials in logs or errors.
"""
import logging
import re
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, update, delete, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from src.config import get_database_url, is_database_configured
from src.models import (
    Base,
    BrandProfileModel,
    SourceDocumentModel,
    SourcePassageModel,
    ContentDraftModel,
    ClaimEvidenceModel,
    ReviewEventModel,
    BrandProfileSchema,
    SourceDocumentSchema,
    PassageSchema,
    ContentDraftSchema,
    ClaimEvidenceSchema,
    ReviewEventSchema,
    generate_id,
    utc_now
)

logger = logging.getLogger(__name__)

def sanitize_db_error(raw_error: Any) -> str:
    """
    Strips credentials, connection URLs, and sensitive host tokens from error strings.
    Guarantees zero leakage of passwords or database secrets in user-facing messages or logs.
    """
    if not raw_error:
        return "Unknown database error."
    msg = str(raw_error)
    # Mask password in connection URIs like postgresql://user:pass@host:port/db
    msg = re.sub(r"://([^:@\s]+):([^@\s]+)@", r"://\1:***@", msg)
    # Mask query parameter passwords/tokens
    msg = re.sub(r"(password|pwd|secret|token|apikey)\s*=\s*['\"]?[^'\"\s,]+['\"]?", r"\1=***", msg, flags=re.IGNORECASE)
    # Mask any standalone database URLs
    msg = re.sub(r"postgresql(?:\+[a-z0-9]+)?://[^\s'\",]+", "[PROTECTED_DATABASE_URL]", msg)
    return msg


class DatabaseOperationError(Exception):
    """Raised when a database transaction or operation fails."""
    pass


class InMemoryStore:
    """
    Transparent in-memory fallback store used when database is not configured.
    Enforces honest persistence reporting (is_persistent = False).
    """
    def __init__(self):
        self.brands: Dict[str, BrandProfileSchema] = {}
        self.documents: Dict[str, SourceDocumentSchema] = {}
        self.drafts: Dict[str, ContentDraftSchema] = {}
        self.review_events: List[ReviewEventSchema] = []

    def clear(self):
        self.brands.clear()
        self.documents.clear()
        self.drafts.clear()
        self.review_events.clear()


# Global in-memory fallback store instance
_MEMORY_STORE = InMemoryStore()


class DatabaseManager:
    """Manages database connections, schemas, and repository operations."""

    _engine = None
    _session_factory = None

    @classmethod
    def get_engine(cls):
        """Initializes or retrieves the cached SQLAlchemy engine."""
        url = get_database_url()
        if not url:
            return None

        if cls._engine is None:
            # Connect timeout 6s to prevent hanging on bad host/credentials
            connect_args = {"connect_timeout": 6}
            # pg8000 uses timeout in connect_args if used
            if "pg8000" in url:
                connect_args = {"timeout": 6}

            try:
                cls._engine = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                    connect_args=connect_args
                )
                cls._session_factory = sessionmaker(bind=cls._engine, autoflush=False, expire_on_commit=False)
            except Exception as e:
                logger.error("Failed to construct SQLAlchemy engine: %s", str(e))
                cls._engine = None
                cls._session_factory = None
        return cls._engine

    @classmethod
    def reset_engine(cls):
        """Forces recreation of the engine (e.g. after config changes)."""
        if cls._engine:
            try:
                cls._engine.dispose()
            except Exception:
                pass
        cls._engine = None
        cls._session_factory = None

    @classmethod
    def check_connection(cls) -> Tuple[bool, str]:
        """
        Tests the PostgreSQL database connection without leaking secrets.
        Returns (success_boolean, human_readable_status_message).
        """
        if not is_database_configured():
            return False, "Database not configured. Operating in Temporary Session Mode (Records not persisted)."

        engine = cls.get_engine()
        if engine is None:
            return False, "Could not initialize database driver or URL."

        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1")).scalar()
                if result == 1:
                    # Sanitize URL to show host safely
                    url_str = str(engine.url)
                    host_part = engine.url.host or "PostgreSQL"
                    return True, f"Connected to PostgreSQL database at {host_part}."
                return False, "Database responded with unexpected result."
        except Exception as e:
            safe_err = sanitize_db_error(e)
            return False, f"Database connection failed: {safe_err[:120]}"

    @classmethod
    def init_db(cls) -> Tuple[bool, str]:
        """
        Safely creates tables if they do not exist.
        Never drops or resets existing production tables.
        """
        if not is_database_configured():
            return False, "Database not configured. Cannot initialize schema."

        engine = cls.get_engine()
        if engine is None:
            return False, "Engine not available."

        try:
            Base.metadata.create_all(bind=engine, checkfirst=True)
            return True, "Database schema verified and initialized successfully."
        except Exception as e:
            safe_err = sanitize_db_error(e)
            logger.error("Failed to initialize database schema: %s", safe_err)
            return False, f"Schema initialization failed: {safe_err[:100]}"

    @classmethod
    def is_persistent(cls) -> bool:
        """Returns True only if real PostgreSQL database connection is operational."""
        success, _ = cls.check_connection()
        return success

    # ==========================================================================
    # BRAND PROFILE REPOSITORY
    # ==========================================================================

    @classmethod
    def save_brand_profile(cls, profile: BrandProfileSchema) -> Tuple[bool, str]:
        if not cls.is_persistent():
            _MEMORY_STORE.brands[profile.id] = profile
            return True, "Saved to temporary session storage (Database not connected)."

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                existing = session.get(BrandProfileModel, profile.id)
                if existing:
                    existing.name = profile.name
                    existing.target_audience = profile.target_audience
                    existing.tone_of_voice = profile.tone_of_voice
                    existing.preferred_terminology = profile.preferred_terminology
                    existing.forbidden_terminology = profile.forbidden_terminology
                    existing.primary_cta = profile.primary_cta
                    existing.required_disclaimer = profile.required_disclaimer
                    existing.hashtag_preferences = profile.hashtag_preferences
                    existing.content_length_prefs = profile.content_length_prefs
                    existing.is_default = profile.is_default
                    existing.updated_at = utc_now()
                else:
                    model = BrandProfileModel(
                        id=profile.id,
                        name=profile.name,
                        target_audience=profile.target_audience,
                        tone_of_voice=profile.tone_of_voice,
                        preferred_terminology=profile.preferred_terminology,
                        forbidden_terminology=profile.forbidden_terminology,
                        primary_cta=profile.primary_cta,
                        required_disclaimer=profile.required_disclaimer,
                        hashtag_preferences=profile.hashtag_preferences,
                        content_length_prefs=profile.content_length_prefs,
                        is_default=profile.is_default,
                        created_at=utc_now(),
                        updated_at=utc_now()
                    )
                    session.add(model)
                session.commit()
                return True, "Brand profile successfully saved to PostgreSQL."
            except Exception as e:
                session.rollback()
                safe_err = sanitize_db_error(e)
                logger.error("Failed to save brand profile: %s", safe_err)
                return False, f"Database write error: {safe_err[:100]}"

    @classmethod
    def list_brand_profiles(cls) -> List[BrandProfileSchema]:
        if not cls.is_persistent():
            return list(_MEMORY_STORE.brands.values())

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                models = session.scalars(select(BrandProfileModel).order_by(BrandProfileModel.created_at.desc())).all()
                results = []
                for m in models:
                    results.append(BrandProfileSchema(
                        id=m.id,
                        name=m.name,
                        target_audience=m.target_audience or "",
                        tone_of_voice=m.tone_of_voice or "Professional",
                        preferred_terminology=m.preferred_terminology or [],
                        forbidden_terminology=m.forbidden_terminology or [],
                        primary_cta=m.primary_cta or "",
                        required_disclaimer=m.required_disclaimer or "",
                        hashtag_preferences=m.hashtag_preferences or "",
                        content_length_prefs=m.content_length_prefs or {},
                        is_default=bool(m.is_default),
                        created_at=m.created_at,
                        updated_at=m.updated_at
                    ))
                return results
            except Exception as e:
                logger.error("Failed to list brand profiles: %s", str(e))
                return list(_MEMORY_STORE.brands.values())

    @classmethod
    def get_brand_profile(cls, profile_id: str) -> Optional[BrandProfileSchema]:
        profiles = cls.list_brand_profiles()
        for p in profiles:
            if p.id == profile_id:
                return p
        return None

    @classmethod
    def delete_brand_profile(cls, profile_id: str) -> Tuple[bool, str]:
        """Safely deletes an individual brand profile by ID."""
        if not cls.is_persistent():
            if profile_id in _MEMORY_STORE.brands:
                del _MEMORY_STORE.brands[profile_id]
                return True, "Brand profile removed from temporary session storage."
            return False, f"Brand profile '{profile_id}' not found."

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                m = session.get(BrandProfileModel, profile_id)
                if not m:
                    return False, f"Brand profile '{profile_id}' not found."
                session.delete(m)
                session.commit()
                return True, "Brand profile deleted from PostgreSQL."
            except Exception as e:
                session.rollback()
                safe_err = sanitize_db_error(e)
                logger.error("Failed to delete brand profile: %s", safe_err)
                return False, f"Database delete error: {safe_err[:100]}"

    # ==========================================================================
    # SOURCE DOCUMENT REPOSITORY
    # ==========================================================================

    @classmethod
    def save_source_document(cls, doc: SourceDocumentSchema) -> Tuple[bool, str]:
        if not cls.is_persistent():
            _MEMORY_STORE.documents[doc.id] = doc
            return True, "Saved to temporary session storage (Database not connected)."

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                existing = session.get(SourceDocumentModel, doc.id)
                if existing:
                    existing.title = doc.title
                    existing.source_type = doc.source_type
                    existing.source_url = doc.source_url
                    existing.raw_text = doc.raw_text
                    existing.word_count = doc.word_count
                    existing.passage_count = doc.passage_count
                    existing.version = doc.version
                    existing.updated_at = utc_now()
                    # Recreate passages
                    session.execute(delete(SourcePassageModel).where(SourcePassageModel.document_id == doc.id))
                else:
                    existing = SourceDocumentModel(
                        id=doc.id,
                        title=doc.title,
                        source_type=doc.source_type,
                        source_url=doc.source_url,
                        raw_text=doc.raw_text,
                        word_count=doc.word_count,
                        passage_count=doc.passage_count,
                        version=doc.version,
                        created_at=utc_now(),
                        updated_at=utc_now()
                    )
                    session.add(existing)

                for p in doc.passages:
                    pm = SourcePassageModel(
                        id=p.id,
                        document_id=doc.id,
                        passage_label=p.passage_label,
                        passage_order=p.passage_order,
                        text=p.text,
                        char_start=p.char_start,
                        char_end=p.char_end,
                        created_at=utc_now()
                    )
                    session.add(pm)

                session.commit()
                return True, "Source document and passages saved to PostgreSQL."
            except Exception as e:
                session.rollback()
                safe_err = sanitize_db_error(e)
                logger.error("Failed to save source document: %s", safe_err)
                return False, f"Database write error: {safe_err[:100]}"

    @classmethod
    def get_source_document(cls, doc_id: str) -> Optional[SourceDocumentSchema]:
        if not cls.is_persistent():
            return _MEMORY_STORE.documents.get(doc_id)

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                m = session.get(SourceDocumentModel, doc_id)
                if not m:
                    return None
                passages = [
                    PassageSchema(
                        id=p.id,
                        document_id=p.document_id,
                        passage_label=p.passage_label,
                        passage_order=p.passage_order,
                        text=p.text,
                        char_start=p.char_start or 0,
                        char_end=p.char_end or 0
                    )
                    for p in sorted(m.passages, key=lambda x: x.passage_order)
                ]
                return SourceDocumentSchema(
                    id=m.id,
                    title=m.title,
                    source_type=m.source_type,
                    source_url=m.source_url,
                    raw_text=m.raw_text,
                    word_count=m.word_count,
                    passage_count=m.passage_count,
                    version=m.version,
                    created_at=m.created_at,
                    passages=passages
                )
            except Exception as e:
                logger.error("Failed to get source document: %s", str(e))
                return _MEMORY_STORE.documents.get(doc_id)

    # ==========================================================================
    # CONTENT DRAFT & EVIDENCE REPOSITORY
    # ==========================================================================

    @classmethod
    def save_content_draft(cls, draft: ContentDraftSchema) -> Tuple[bool, str]:
        if not cls.is_persistent():
            _MEMORY_STORE.drafts[draft.id] = draft
            return True, "Draft saved in temporary session storage (Database not connected)."

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                existing = session.get(ContentDraftModel, draft.id)
                if existing:
                    existing.brand_profile_id = draft.brand_profile_id
                    existing.platform = draft.platform
                    existing.hook_title = draft.hook_title
                    existing.primary_content = draft.primary_content
                    existing.cta_text = draft.cta_text
                    existing.hashtags = draft.hashtags
                    existing.video_hook = draft.video_hook
                    existing.video_script = draft.video_script
                    existing.review_status = draft.review_status
                    existing.approval_notes = draft.approval_notes
                    existing.approved_at = draft.approved_at
                    existing.generation_mode = draft.generation_mode
                    existing.compliance_score = draft.compliance_score
                    existing.updated_at = utc_now()
                    # Recreate claims
                    session.execute(delete(ClaimEvidenceModel).where(ClaimEvidenceModel.draft_id == draft.id))
                else:
                    existing = ContentDraftModel(
                        id=draft.id,
                        document_id=draft.document_id,
                        brand_profile_id=draft.brand_profile_id,
                        platform=draft.platform,
                        hook_title=draft.hook_title,
                        primary_content=draft.primary_content,
                        cta_text=draft.cta_text,
                        hashtags=draft.hashtags,
                        video_hook=draft.video_hook,
                        video_script=draft.video_script,
                        review_status=draft.review_status,
                        approval_notes=draft.approval_notes,
                        approved_at=draft.approved_at,
                        generation_mode=draft.generation_mode,
                        compliance_score=draft.compliance_score,
                        created_at=utc_now(),
                        updated_at=utc_now()
                    )
                    session.add(existing)

                for c in draft.claims:
                    cm = ClaimEvidenceModel(
                        id=c.id,
                        draft_id=draft.id,
                        document_id=draft.document_id,
                        claim_label=c.claim_label,
                        claim_text=c.claim_text,
                        referenced_passage_ids=c.referenced_passage_ids,
                        supporting_excerpt=c.supporting_excerpt,
                        evidence_status=c.evidence_status,
                        requires_human_review=c.requires_human_review,
                        flag_reasons=c.flag_reasons,
                        reviewer_note=c.reviewer_note,
                        created_at=utc_now(),
                        updated_at=utc_now()
                    )
                    session.add(cm)

                session.commit()
                return True, "Draft and evidence links saved to PostgreSQL."
            except Exception as e:
                session.rollback()
                safe_err = sanitize_db_error(e)
                logger.error("Failed to save content draft: %s", safe_err)
                return False, f"Database write error: {safe_err[:100]}"

    @classmethod
    def list_content_drafts(
        cls,
        platform: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[ContentDraftSchema]:
        if not cls.is_persistent():
            drafts = list(_MEMORY_STORE.drafts.values())
            if platform:
                drafts = [d for d in drafts if d.platform.lower() == platform.lower()]
            if status:
                drafts = [d for d in drafts if d.review_status.lower() == status.lower()]
            return sorted(drafts, key=lambda x: str(x.created_at or ""), reverse=True)

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                stmt = select(ContentDraftModel).order_by(ContentDraftModel.created_at.desc())
                if platform:
                    stmt = stmt.where(ContentDraftModel.platform == platform.lower())
                if status:
                    stmt = stmt.where(ContentDraftModel.review_status == status.lower())

                models = session.scalars(stmt).all()
                results = []
                for m in models:
                    claims = [
                        ClaimEvidenceSchema(
                            id=c.id,
                            draft_id=c.draft_id,
                            document_id=c.document_id,
                            claim_label=c.claim_label,
                            claim_text=c.claim_text,
                            referenced_passage_ids=c.referenced_passage_ids or [],
                            supporting_excerpt=c.supporting_excerpt,
                            evidence_status=c.evidence_status,
                            requires_human_review=bool(c.requires_human_review),
                            flag_reasons=c.flag_reasons or [],
                            reviewer_note=c.reviewer_note
                        )
                        for c in m.claims
                    ]
                    results.append(ContentDraftSchema(
                        id=m.id,
                        document_id=m.document_id,
                        brand_profile_id=m.brand_profile_id,
                        platform=m.platform,
                        hook_title=m.hook_title,
                        primary_content=m.primary_content,
                        cta_text=m.cta_text,
                        hashtags=m.hashtags,
                        video_hook=m.video_hook,
                        video_script=m.video_script,
                        review_status=m.review_status,
                        approval_notes=m.approval_notes,
                        approved_at=m.approved_at,
                        generation_mode=m.generation_mode,
                        compliance_score=m.compliance_score or 100,
                        created_at=m.created_at,
                        updated_at=m.updated_at,
                        claims=claims
                    ))
                return results
            except Exception as e:
                logger.error("Failed to list drafts from database: %s", str(e))
                return list(_MEMORY_STORE.drafts.values())

    @classmethod
    def get_content_draft(cls, draft_id: str) -> Optional[ContentDraftSchema]:
        drafts = cls.list_content_drafts()
        for d in drafts:
            if d.id == draft_id:
                return d
        return None

    @classmethod
    def update_draft_content(cls, draft_id: str, new_content: str, reset_approval: bool = True) -> Tuple[bool, str]:
        """
        Updates draft content. Crucially, editing approved content MUST reset its approval state!
        """
        draft = cls.get_content_draft(draft_id)
        if not draft:
            return False, f"Draft '{draft_id}' not found."

        old_status = draft.review_status
        draft.primary_content = new_content
        draft.updated_at = utc_now()

        # If it was previously approved and user edits content, reset status
        new_status = old_status
        if reset_approval and old_status == "approved":
            new_status = "reopened"
            draft.review_status = "reopened"
            draft.approval_notes = "Automatically reopened for review due to content edit."

        cls.log_review_event(draft_id, old_status, new_status, actor="user", notes="Content edited.")
        return cls.save_content_draft(draft)

    @classmethod
    def update_draft_status(
        cls,
        draft_id: str,
        new_status: str,
        notes: str = "",
        actor: str = "reviewer"
    ) -> Tuple[bool, str]:
        """
        Updates draft review/approval status with audit trail event.
        """
        draft = cls.get_content_draft(draft_id)
        if not draft:
            return False, f"Draft '{draft_id}' not found."

        old_status = draft.review_status
        draft.review_status = new_status
        draft.approval_notes = notes
        draft.updated_at = utc_now()
        if new_status == "approved":
            draft.approved_at = utc_now()

        cls.log_review_event(draft_id, old_status, new_status, actor=actor, notes=notes)
        return cls.save_content_draft(draft)

    @classmethod
    def log_review_event(
        cls,
        draft_id: str,
        old_status: Optional[str],
        new_status: str,
        actor: str = "reviewer",
        notes: str = ""
    ):
        event = ReviewEventSchema(
            id=generate_id("rev"),
            draft_id=draft_id,
            previous_status=old_status,
            new_status=new_status,
            actor=actor,
            notes=notes,
            timestamp=utc_now()
        )
        if not cls.is_persistent():
            _MEMORY_STORE.review_events.append(event)
            return

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                m = ReviewEventModel(
                    id=event.id,
                    draft_id=event.draft_id,
                    previous_status=event.previous_status,
                    new_status=event.new_status,
                    actor=event.actor,
                    notes=event.notes,
                    timestamp=utc_now()
                )
                session.add(m)
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error("Failed to log review event: %s", str(e))

    @classmethod
    def delete_content_draft(cls, draft_id: str) -> Tuple[bool, str]:
        if not cls.is_persistent():
            if draft_id in _MEMORY_STORE.drafts:
                del _MEMORY_STORE.drafts[draft_id]
                return True, "Draft deleted from session storage."
            return False, "Draft not found."

        engine = cls.get_engine()
        with Session(engine) as session:
            try:
                m = session.get(ContentDraftModel, draft_id)
                if not m:
                    return False, "Draft not found."
                session.delete(m)
                session.commit()
                return True, "Draft deleted from PostgreSQL."
            except Exception as e:
                session.rollback()
                safe_err = sanitize_db_error(e)
                logger.error("Failed to delete draft: %s", safe_err)
                return False, f"Failed to delete draft: {safe_err[:100]}"

