-- ==============================================================================
-- SOURCEWISE AI — POSTGRESQL / SUPABASE DATABASE SCHEMA
-- Compatible with PostgreSQL 13+ / Supabase
-- Provides persistent storage for Source Documents, Passages, Content Drafts,
-- Claim Evidence traceability, Brand Profiles, and Approval Auditing.
-- ==============================================================================

-- 1. Brand Profiles
CREATE TABLE IF NOT EXISTS brand_profiles (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    target_audience TEXT,
    tone_of_voice VARCHAR(100) DEFAULT 'Professional',
    preferred_terminology JSONB DEFAULT '[]'::jsonb,
    forbidden_terminology JSONB DEFAULT '[]'::jsonb,
    primary_cta TEXT,
    required_disclaimer TEXT,
    hashtag_preferences TEXT,
    content_length_prefs JSONB DEFAULT '{}'::jsonb,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Source Documents
CREATE TABLE IF NOT EXISTS source_documents (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    source_type VARCHAR(64) NOT NULL DEFAULT 'Blog',
    source_url VARCHAR(1000),
    raw_text TEXT NOT NULL,
    word_count INT NOT NULL DEFAULT 0,
    passage_count INT NOT NULL DEFAULT 0,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Source Passages (S1, S2, S3...)
CREATE TABLE IF NOT EXISTS source_passages (
    id VARCHAR(64) PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    passage_label VARCHAR(16) NOT NULL,
    passage_order INT NOT NULL,
    text TEXT NOT NULL,
    char_start INT DEFAULT 0,
    char_end INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_source_passages_doc ON source_passages(document_id, passage_label);

-- 4. Content Drafts
CREATE TABLE IF NOT EXISTS content_drafts (
    id VARCHAR(64) PRIMARY KEY,
    document_id VARCHAR(64) NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    brand_profile_id VARCHAR(64) REFERENCES brand_profiles(id) ON DELETE SET NULL,
    platform VARCHAR(32) NOT NULL,
    hook_title TEXT NOT NULL,
    primary_content TEXT NOT NULL,
    cta_text TEXT,
    hashtags TEXT,
    video_hook TEXT,
    video_script TEXT,
    review_status VARCHAR(32) NOT NULL DEFAULT 'draft',
    approval_notes TEXT,
    approved_at TIMESTAMPTZ,
    generation_mode VARCHAR(32) NOT NULL DEFAULT 'demo',
    compliance_score INT DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_content_drafts_doc ON content_drafts(document_id);
CREATE INDEX IF NOT EXISTS idx_content_drafts_status ON content_drafts(review_status);

-- 5. Claim Evidence Traceability (C1, C2...)
CREATE TABLE IF NOT EXISTS claim_evidence (
    id VARCHAR(64) PRIMARY KEY,
    draft_id VARCHAR(64) NOT NULL REFERENCES content_drafts(id) ON DELETE CASCADE,
    document_id VARCHAR(64) NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    claim_label VARCHAR(16) NOT NULL,
    claim_text TEXT NOT NULL,
    referenced_passage_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    supporting_excerpt TEXT,
    evidence_status VARCHAR(64) NOT NULL DEFAULT 'Evidence Linked',
    requires_human_review BOOLEAN DEFAULT FALSE,
    flag_reasons JSONB DEFAULT '[]'::jsonb,
    reviewer_note TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_draft ON claim_evidence(draft_id);

-- 6. Review & Approval Audit Events
CREATE TABLE IF NOT EXISTS review_events (
    id VARCHAR(64) PRIMARY KEY,
    draft_id VARCHAR(64) NOT NULL REFERENCES content_drafts(id) ON DELETE CASCADE,
    previous_status VARCHAR(32),
    new_status VARCHAR(32) NOT NULL,
    actor VARCHAR(100) DEFAULT 'reviewer',
    notes TEXT,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_review_events_draft ON review_events(draft_id);
