import os
import pytest
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from src.models import (
    Base,
    BrandProfileModel,
    SourceDocumentModel,
    SourcePassageModel,
    ContentDraftModel,
    ClaimEvidenceModel,
    BrandProfileSchema,
    SourceDocumentSchema,
    PassageSchema,
    ContentDraftSchema,
    ClaimEvidenceSchema,
    generate_id
)
from src.database import DatabaseManager, _MEMORY_STORE, sanitize_db_error


@pytest.fixture(autouse=True)
def clean_memory_store():
    _MEMORY_STORE.clear()
    yield
    _MEMORY_STORE.clear()


@pytest.fixture
def sqlite_engine_with_fk():
    """In-memory SQLite engine with PRAGMA foreign_keys=ON explicitly verified."""
    engine = create_engine("sqlite:///:memory:")
    
    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_default_sqlite_is_configured_and_connected():
    """Verifies that SourceWise AI connects to local SQLite by default."""
    DatabaseManager.reset_engine()
    persistent = DatabaseManager.is_persistent()
    assert persistent is True

    ok, msg = DatabaseManager.check_connection()
    assert ok is True
    assert "local SQLite database" in msg
    assert "Foreign keys ON" in msg


def test_fallback_when_db_disabled(monkeypatch):
    """Verifies honest fallback to session memory when database is explicitly disabled."""
    monkeypatch.setenv("DISABLE_DATABASE", "true")
    DatabaseManager.reset_engine()
    try:
        persistent = DatabaseManager.is_persistent()
        assert persistent is False

        ok, msg = DatabaseManager.check_connection()
        assert ok is False
        assert "Operating in Temporary Session Mode" in msg
    finally:
        monkeypatch.delenv("DISABLE_DATABASE", raising=False)
        DatabaseManager.reset_engine()


def test_brand_profile_crud():
    """Verifies Brand Profile Create, Read, Update, List, and Delete."""
    profile_id = generate_id("test_brand")
    profile = BrandProfileSchema(
        id=profile_id,
        name="Test Brand",
        target_audience="DevOps Engineers",
        tone_of_voice="Technical",
        preferred_terminology=["k8s", "observability"],
        forbidden_terminology=["trivial"],
        primary_cta="Visit testbrand.io"
    )

    # Save / Create
    ok, msg = DatabaseManager.save_brand_profile(profile)
    assert ok is True

    # Retrieve / Read
    retrieved = DatabaseManager.get_brand_profile(profile.id)
    assert retrieved is not None
    assert retrieved.name == "Test Brand"
    assert "k8s" in retrieved.preferred_terminology

    # Update
    retrieved.name = "Test Brand (Updated)"
    update_ok, _ = DatabaseManager.save_brand_profile(retrieved)
    assert update_ok is True
    re_read = DatabaseManager.get_brand_profile(profile.id)
    assert re_read.name == "Test Brand (Updated)"

    # List
    all_profiles = DatabaseManager.list_brand_profiles()
    assert len(all_profiles) >= 1
    assert any(p.id == profile.id for p in all_profiles)

    # Delete
    del_ok, _ = DatabaseManager.delete_brand_profile(profile.id)
    assert del_ok is True
    assert DatabaseManager.get_brand_profile(profile.id) is None


def test_sanitize_db_error_masks_credentials():
    """Verifies sensitive credentials and full connection strings are never leaked."""
    raw_err = "OperationalError: password='super_secret_password_123' authentication failed for user 'postgres'"
    safe_err = sanitize_db_error(raw_err)
    assert "super_secret_password_123" not in safe_err
    assert "password=***" in safe_err

    raw_uri_err = "could not connect to postgresql+psycopg://postgres:secretPass123@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    safe_uri_err = sanitize_db_error(raw_uri_err)
    assert "secretPass123" not in safe_uri_err
    assert "[PROTECTED_DATABASE_URL]" in safe_uri_err or "***@" in safe_uri_err


def test_source_and_passages_crud():
    """Verifies source document and passage hierarchy persistence."""
    doc_id = generate_id("doc")
    p1 = PassageSchema(document_id=doc_id, passage_label="S1", passage_order=1, text="Passage one content.")
    p2 = PassageSchema(document_id=doc_id, passage_label="S2", passage_order=2, text="Passage two content.")
    doc = SourceDocumentSchema(
        id=doc_id,
        title="Scaling Cache",
        source_type="Blog",
        raw_text="Passage one content.\n\nPassage two content.",
        word_count=6,
        passage_count=2,
        version=1,
        passages=[p1, p2]
    )

    ok, msg = DatabaseManager.save_source_document(doc)
    assert ok is True

    fetched = DatabaseManager.get_source_document(doc_id)
    assert fetched is not None
    assert fetched.title == "Scaling Cache"
    assert len(fetched.passages) == 2
    assert fetched.passages[0].passage_label == "S1"


def test_draft_approval_reset_on_edit():
    """Verifies that editing content resets an approved draft back to reopened."""
    doc_id = generate_id("doc")
    doc = SourceDocumentSchema(
        id=doc_id,
        title="Test Parent Document",
        source_type="Blog",
        raw_text="Test source content.",
        word_count=3,
        passage_count=1
    )
    DatabaseManager.save_source_document(doc)

    draft_id = generate_id("draft")
    draft = ContentDraftSchema(
        id=draft_id,
        document_id=doc_id,
        platform="linkedin",
        hook_title="Initial Hook",
        primary_content="Initial content text.",
        review_status="approved"
    )
    save_ok, save_msg = DatabaseManager.save_content_draft(draft)
    assert save_ok is True, save_msg

    # Verify initial approved status
    saved = DatabaseManager.get_content_draft(draft_id)
    assert saved is not None
    assert saved.review_status == "approved"

    # Edit content -> must reset to 'reopened'
    DatabaseManager.update_draft_content(draft_id, "Updated new content text.", reset_approval=True)

    updated = DatabaseManager.get_content_draft(draft_id)
    assert updated.primary_content == "Updated new content text."
    assert updated.review_status == "reopened"
    assert "reopened for review" in updated.approval_notes


def test_draft_status_transition_and_audit():
    """Verifies review status transitions and review event creation."""
    doc_id = generate_id("doc")
    doc = SourceDocumentSchema(
        id=doc_id,
        title="Test Parent Document 2",
        source_type="Blog",
        raw_text="Test source content 2.",
        word_count=4,
        passage_count=1
    )
    DatabaseManager.save_source_document(doc)

    draft_id = generate_id("draft")
    draft = ContentDraftSchema(
        id=draft_id,
        document_id=doc_id,
        platform="instagram",
        hook_title="Hook",
        primary_content="Caption",
        review_status="draft"
    )
    DatabaseManager.save_content_draft(draft)

    # Approve
    ok, _ = DatabaseManager.update_draft_status(draft_id, "approved", notes="Looks solid.", actor="senior_reviewer")
    assert ok is True

    draft_approved = DatabaseManager.get_content_draft(draft_id)
    assert draft_approved.review_status == "approved"
    assert draft_approved.approved_at is not None
    assert draft_approved.approval_notes == "Looks solid."

    # Audit events
    events = DatabaseManager.list_review_events(draft_id)
    assert len(events) >= 1
    assert events[-1].new_status == "approved"
    assert events[-1].actor == "senior_reviewer"


def test_sqlite_foreign_key_enforcement_and_cascade(sqlite_engine_with_fk):
    """Verifies foreign key constraints and cascade deletion in SQLite."""
    with Session(sqlite_engine_with_fk) as session:
        # 1. Foreign key constraint prevents orphan drafts
        orphan_draft = ContentDraftModel(
            id="draft_orphan",
            document_id="non_existent_doc_id",
            platform="linkedin",
            hook_title="Orphan Hook",
            primary_content="Content",
            review_status="draft"
        )
        session.add(orphan_draft)
        with pytest.raises(Exception):
            session.commit()
        session.rollback()

        # 2. Add valid hierarchy
        doc = SourceDocumentModel(
            id="doc_sql_1",
            title="Postgres Indexing",
            source_type="Blog",
            raw_text="Test raw text",
            word_count=3,
            passage_count=1,
            version=1
        )
        session.add(doc)

        pass1 = SourcePassageModel(
            id="pass_sql_1",
            document_id="doc_sql_1",
            passage_label="S1",
            passage_order=1,
            text="Test passage content"
        )
        session.add(pass1)

        draft = ContentDraftModel(
            id="draft_sql_1",
            document_id="doc_sql_1",
            platform="linkedin",
            hook_title="Hook",
            primary_content="Content",
            review_status="draft"
        )
        session.add(draft)

        claim = ClaimEvidenceModel(
            id="claim_sql_1",
            draft_id="draft_sql_1",
            document_id="doc_sql_1",
            claim_label="C1",
            claim_text="Test claim",
            referenced_passage_ids=["S1"],
            evidence_status="Evidence Linked"
        )
        session.add(claim)
        session.commit()

        # Verify retrieval
        d_check = session.get(SourceDocumentModel, "doc_sql_1")
        assert len(d_check.passages) == 1
        assert len(d_check.drafts) == 1
        assert len(d_check.drafts[0].claims) == 1

        # Test cascade delete: deleting document must cascade delete passages, drafts, and claims
        session.delete(d_check)
        session.commit()

        assert session.get(SourceDocumentModel, "doc_sql_1") is None
        assert session.get(SourcePassageModel, "pass_sql_1") is None
        assert session.get(ContentDraftModel, "draft_sql_1") is None
        assert session.get(ClaimEvidenceModel, "claim_sql_1") is None


def test_sqlite_persistence_across_connection_reopening(tmp_path, monkeypatch):
    """
    Verifies that SQLite writes to a physical file and data persists
    when the database engine is closed, disposed, and reopened.
    """
    test_db_file = str(tmp_path / "persist_test.db")
    monkeypatch.setenv("DATABASE_PATH", test_db_file)
    DatabaseManager.reset_engine()

    try:
        # Initialize schema in new file
        init_ok, init_msg = DatabaseManager.init_db()
        assert init_ok is True

        # Save document & draft
        doc_id = "doc_persist_test"
        doc = SourceDocumentSchema(
            id=doc_id,
            title="File Persistence Document",
            source_type="Case Study",
            raw_text="Content for persistence testing.",
            word_count=4,
            passage_count=1
        )
        save_ok, _ = DatabaseManager.save_source_document(doc)
        assert save_ok is True

        draft_id = "draft_persist_test"
        draft = ContentDraftSchema(
            id=draft_id,
            document_id=doc_id,
            platform="twitter",
            hook_title="Persistence Hook",
            primary_content="Persistent tweet content.",
            review_status="approved"
        )
        draft_ok, _ = DatabaseManager.save_content_draft(draft)
        assert draft_ok is True

        # Disconnect and dispose engine completely
        DatabaseManager.reset_engine()

        # Reopen and reconnect using the same physical database file
        reopened_doc = DatabaseManager.get_source_document(doc_id)
        assert reopened_doc is not None
        assert reopened_doc.title == "File Persistence Document"

        reopened_draft = DatabaseManager.get_content_draft(draft_id)
        assert reopened_draft is not None
        assert reopened_draft.primary_content == "Persistent tweet content."
        assert reopened_draft.review_status == "approved"

    finally:
        monkeypatch.delenv("DATABASE_PATH", raising=False)
        DatabaseManager.reset_engine()
