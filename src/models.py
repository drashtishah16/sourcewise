"""
Data models for SourceWise AI.
Includes Pydantic validation schemas and SQLAlchemy ORM models for Supabase PostgreSQL.
"""
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import json
import uuid

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def generate_id(prefix: str = "") -> str:
    short_uuid = str(uuid.uuid4())[:8]
    return f"{prefix}_{short_uuid}" if prefix else short_uuid


# ==============================================================================
# PYDANTIC VALIDATION SCHEMAS
# ==============================================================================

class BrandProfileSchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("brand"))
    name: str = Field(..., min_length=2, max_length=255)
    target_audience: str = Field(default="Target Audience")
    tone_of_voice: str = Field(default="Professional")
    preferred_terminology: List[str] = Field(default_factory=list)
    forbidden_terminology: List[str] = Field(default_factory=list)
    primary_cta: str = Field(default="")
    required_disclaimer: str = Field(default="")
    hashtag_preferences: str = Field(default="")
    content_length_prefs: Dict[str, Any] = Field(default_factory=lambda: {
        "linkedin_min": 100,
        "linkedin_max": 350,
        "instagram_min": 50,
        "instagram_max": 250,
        "video_seconds": 60
    })
    is_default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SourceInputSchema(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    source_type: str = Field(default="Blog")
    source_url: Optional[str] = Field(default=None)
    raw_text: str = Field(..., min_length=20, max_length=50000)

    @field_validator("raw_text")
    def validate_raw_text(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("Source text cannot be empty or pure whitespace.")
        if len(text) < 20:
            raise ValueError("Source text is too short to extract meaningful passages (minimum 20 characters).")
        return text

    @field_validator("source_type")
    def validate_source_type(cls, v: str) -> str:
        allowed = {"Blog", "Case Study", "Product Page", "Report", "Other"}
        if v not in allowed:
            return "Other"
        return v


class PassageSchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("pass"))
    document_id: str
    passage_label: str  # e.g., 'S1', 'S2'
    passage_order: int
    text: str
    char_start: int = 0
    char_end: int = 0


class SourceDocumentSchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("doc"))
    title: str
    source_type: str
    source_url: Optional[str] = None
    raw_text: str
    word_count: int
    passage_count: int
    version: int = 1
    created_at: Optional[datetime] = None
    passages: List[PassageSchema] = Field(default_factory=list)


class ClaimEvidenceSchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("claim"))
    draft_id: str
    document_id: str
    claim_label: str  # e.g., 'C1', 'C2'
    claim_text: str
    referenced_passage_ids: List[str] = Field(default_factory=list)
    supporting_excerpt: Optional[str] = None
    evidence_status: str = Field(default="Evidence Linked")
    # Allowed statuses: 'Evidence Linked', 'Potentially Unsupported', 'Conflicting or Ambiguous', 'Human Review Required'
    requires_human_review: bool = False
    flag_reasons: List[str] = Field(default_factory=list)
    reviewer_note: Optional[str] = None


class ContentDraftSchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("draft"))
    document_id: str
    brand_profile_id: Optional[str] = None
    platform: str  # 'linkedin', 'instagram', 'video_script'
    hook_title: str
    primary_content: str
    cta_text: Optional[str] = None
    hashtags: Optional[str] = None
    video_hook: Optional[str] = None
    video_script: Optional[str] = None
    review_status: str = Field(default="draft")  # draft, in_review, approved, rejected, reopened
    approval_notes: Optional[str] = None
    approved_at: Optional[datetime] = None
    generation_mode: str = Field(default="demo")  # demo, connected
    compliance_score: int = 100
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    claims: List[ClaimEvidenceSchema] = Field(default_factory=list)


class ReviewEventSchema(BaseModel):
    id: str = Field(default_factory=lambda: generate_id("rev"))
    draft_id: str
    previous_status: Optional[str] = None
    new_status: str
    actor: str = "reviewer"
    notes: Optional[str] = None
    timestamp: Optional[datetime] = None


# ==============================================================================
# SQLALCHEMY ORM MODELS
# ==============================================================================

class BrandProfileModel(Base):
    __tablename__ = "brand_profiles"

    id = Column(String(64), primary_key=True, default=lambda: generate_id("brand"))
    name = Column(String(255), nullable=False)
    target_audience = Column(Text, nullable=True)
    tone_of_voice = Column(String(100), default="Professional")
    preferred_terminology = Column(JSON, default=list)
    forbidden_terminology = Column(JSON, default=list)
    primary_cta = Column(Text, nullable=True)
    required_disclaimer = Column(Text, nullable=True)
    hashtag_preferences = Column(Text, nullable=True)
    content_length_prefs = Column(JSON, default=dict)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SourceDocumentModel(Base):
    __tablename__ = "source_documents"

    id = Column(String(64), primary_key=True, default=lambda: generate_id("doc"))
    title = Column(String(500), nullable=False)
    source_type = Column(String(64), default="Blog", nullable=False)
    source_url = Column(String(1000), nullable=True)
    raw_text = Column(Text, nullable=False)
    word_count = Column(Integer, default=0, nullable=False)
    passage_count = Column(Integer, default=0, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    passages = relationship("SourcePassageModel", back_populates="document", cascade="all, delete-orphan")
    drafts = relationship("ContentDraftModel", back_populates="document", cascade="all, delete-orphan")


class SourcePassageModel(Base):
    __tablename__ = "source_passages"

    id = Column(String(64), primary_key=True, default=lambda: generate_id("pass"))
    document_id = Column(String(64), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    passage_label = Column(String(16), nullable=False)
    passage_order = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    char_start = Column(Integer, default=0)
    char_end = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    document = relationship("SourceDocumentModel", back_populates="passages")


class ContentDraftModel(Base):
    __tablename__ = "content_drafts"

    id = Column(String(64), primary_key=True, default=lambda: generate_id("draft"))
    document_id = Column(String(64), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    brand_profile_id = Column(String(64), ForeignKey("brand_profiles.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(32), nullable=False)
    hook_title = Column(Text, nullable=False)
    primary_content = Column(Text, nullable=False)
    cta_text = Column(Text, nullable=True)
    hashtags = Column(Text, nullable=True)
    video_hook = Column(Text, nullable=True)
    video_script = Column(Text, nullable=True)
    review_status = Column(String(32), default="draft", nullable=False)
    approval_notes = Column(Text, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    generation_mode = Column(String(32), default="demo", nullable=False)
    compliance_score = Column(Integer, default=100)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    document = relationship("SourceDocumentModel", back_populates="drafts")
    claims = relationship("ClaimEvidenceModel", back_populates="draft", cascade="all, delete-orphan")
    review_events = relationship("ReviewEventModel", back_populates="draft", cascade="all, delete-orphan")


class ClaimEvidenceModel(Base):
    __tablename__ = "claim_evidence"

    id = Column(String(64), primary_key=True, default=lambda: generate_id("claim"))
    draft_id = Column(String(64), ForeignKey("content_drafts.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String(64), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    claim_label = Column(String(16), nullable=False)
    claim_text = Column(Text, nullable=False)
    referenced_passage_ids = Column(JSON, default=list, nullable=False)
    supporting_excerpt = Column(Text, nullable=True)
    evidence_status = Column(String(64), default="Evidence Linked", nullable=False)
    requires_human_review = Column(Boolean, default=False)
    flag_reasons = Column(JSON, default=list)
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    draft = relationship("ContentDraftModel", back_populates="claims")


class ReviewEventModel(Base):
    __tablename__ = "review_events"

    id = Column(String(64), primary_key=True, default=lambda: generate_id("rev"))
    draft_id = Column(String(64), ForeignKey("content_drafts.id", ondelete="CASCADE"), nullable=False)
    previous_status = Column(String(32), nullable=True)
    new_status = Column(String(32), nullable=False)
    actor = Column(String(100), default="reviewer")
    notes = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=utc_now)

    draft = relationship("ContentDraftModel", back_populates="review_events")
