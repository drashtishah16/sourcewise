-- ==============================================================================
-- SOURCEWISE AI — SQLITE DATABASE SCHEMA
-- Compatible with SQLite 3+ and SQLAlchemy
-- Enforces foreign keys (PRAGMA foreign_keys = ON)
-- Provides persistent storage for Source Documents, Passages, Content Drafts,
-- Claim Evidence traceability, Brand Profiles, and Approval Auditing.
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- 1. Brand Profiles
CREATE TABLE IF NOT EXISTS brand_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    target_audience TEXT,
    tone_of_voice TEXT DEFAULT 'Professional',
    preferred_terminology TEXT DEFAULT '[]',
    forbidden_terminology TEXT DEFAULT '[]',
    primary_cta TEXT,
    required_disclaimer TEXT,
    hashtag_preferences TEXT,
    content_length_prefs TEXT DEFAULT '{}',
    is_default BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Source Documents
CREATE TABLE IF NOT EXISTS source_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'Blog',
    source_url TEXT,
    raw_text TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0,
    passage_count INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Source Passages (S1, S2, S3...)
CREATE TABLE IF NOT EXISTS source_passages (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    passage_label TEXT NOT NULL,
    passage_order INTEGER NOT NULL,
    text TEXT NOT NULL,
    char_start INTEGER DEFAULT 0,
    char_end INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_passages_doc ON source_passages(document_id, passage_label);

-- 4. Content Drafts
CREATE TABLE IF NOT EXISTS content_drafts (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    brand_profile_id TEXT REFERENCES brand_profiles(id) ON DELETE SET NULL,
    platform TEXT NOT NULL,
    hook_title TEXT NOT NULL,
    primary_content TEXT NOT NULL,
    cta_text TEXT,
    hashtags TEXT,
    video_hook TEXT,
    video_script TEXT,
    review_status TEXT NOT NULL DEFAULT 'draft',
    approval_notes TEXT,
    approved_at TIMESTAMP,
    generation_mode TEXT NOT NULL DEFAULT 'demo',
    compliance_score INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_content_drafts_doc ON content_drafts(document_id);
CREATE INDEX IF NOT EXISTS idx_content_drafts_status ON content_drafts(review_status);

-- 5. Claim Evidence Traceability (C1, C2...)
CREATE TABLE IF NOT EXISTS claim_evidence (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL REFERENCES content_drafts(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    claim_label TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    referenced_passage_ids TEXT NOT NULL DEFAULT '[]',
    supporting_excerpt TEXT,
    evidence_status TEXT NOT NULL DEFAULT 'Evidence Linked',
    requires_human_review BOOLEAN DEFAULT 0,
    flag_reasons TEXT DEFAULT '[]',
    reviewer_note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_draft ON claim_evidence(draft_id);

-- 6. Review & Approval Audit Events
CREATE TABLE IF NOT EXISTS review_events (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL REFERENCES content_drafts(id) ON DELETE CASCADE,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    actor TEXT DEFAULT 'reviewer',
    notes TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_review_events_draft ON review_events(draft_id);
