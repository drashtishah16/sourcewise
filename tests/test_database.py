import pytest
from sqlalchemy import create_engine, text
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
from src.database import DatabaseManager, _MEMORY_STORE

@pytest.fixture(autouse=True)
def clean_memory_store():
    _MEMORY_STORE.clear()
    yield
    _MEMORY_STORE.clear()

@pytest.fixture
def sqlite_engine():
    """Disposable in-memory SQLite engine to test real SQLAlchemy models & cascades."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_fallback_when_db_not_configured():
    # Database is not configured by default in local tests
    persistent = DatabaseManager.is_persistent()
    assert persistent is False

    ok, msg = DatabaseManager.check_connection()
    assert ok is False
    assert "Temporary Session Mode" in msg or "not configured" in msg


def test_brand_profile_crud_in_memory():
    profile = BrandProfileSchema(
        name="Test Brand",
        target_audience="DevOps Engineers",
        tone_of_voice="Technical",
        preferred_terminology=["k8s", "observability"],
        forbidden_terminology=["trivial"],
        primary_cta="Visit testbrand.io"
    )

    # Save
    ok, msg = DatabaseManager.save_brand_profile(profile)
    assert ok is True

    # Retrieve
    retrieved = DatabaseManager.get_brand_profile(profile.id)
    assert retrieved is not None
    assert retrieved.name == "Test Brand"
    assert "k8s" in retrieved.preferred_terminology

    # List
    all_profiles = DatabaseManager.list_brand_profiles()
    assert len(all_profiles) >= 1
    assert any(p.id == profile.id for p in all_profiles)

    # Delete
    del_ok, del_msg = DatabaseManager.delete_brand_profile(profile.id)
    assert del_ok is True
    assert DatabaseManager.get_brand_profile(profile.id) is None


def test_sanitize_db_error_masks_credentials():
    from src.database import sanitize_db_error

    raw_err = "psycopg.OperationalError: connection to server at 'db.supabase.co', port 5432 failed: password='super_secret_password_123' authentication failed for user 'postgres'"
    safe_err = sanitize_db_error(raw_err)
    assert "super_secret_password_123" not in safe_err
    assert "password=***" in safe_err

    raw_uri_err = "could not connect to postgresql+psycopg://postgres:secretPass123@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    safe_uri_err = sanitize_db_error(raw_uri_err)
    assert "secretPass123" not in safe_uri_err
    assert "[PROTECTED_DATABASE_URL]" in safe_uri_err or "***@" in safe_uri_err


def test_source_and_passages_crud_in_memory():
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
    draft_id = generate_id("draft")
    draft = ContentDraftSchema(
        id=draft_id,
        document_id="doc_test",
        platform="linkedin",
        hook_title="Initial Hook",
        primary_content="Initial content text.",
        review_status="approved"
    )
    DatabaseManager.save_content_draft(draft)

    # Verify initial approved status
    saved = DatabaseManager.get_content_draft(draft_id)
    assert saved.review_status == "approved"

    # Edit content -> must reset to 'reopened'
    DatabaseManager.update_draft_content(draft_id, "Updated new content text.", reset_approval=True)

    updated = DatabaseManager.get_content_draft(draft_id)
    assert updated.primary_content == "Updated new content text."
    assert updated.review_status == "reopened"
    assert "reopened for review" in updated.approval_notes


def test_draft_status_transition_and_audit():
    draft_id = generate_id("draft")
    draft = ContentDraftSchema(
        id=draft_id,
        document_id="doc_test",
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
    events = [e for e in _MEMORY_STORE.review_events if e.draft_id == draft_id]
    assert len(events) >= 1
    assert events[-1].new_status == "approved"
    assert events[-1].actor == "senior_reviewer"


def test_sqlalchemy_orm_relationships_in_sqlite(sqlite_engine):
    """Verifies table schema, foreign keys, and cascade deletes using real SQLAlchemy session."""
    with Session(sqlite_engine) as session:
        # Create Document
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

        # Create Passage
        pass1 = SourcePassageModel(
            id="pass_sql_1",
            document_id="doc_sql_1",
            passage_label="S1",
            passage_order=1,
            text="Test passage content"
        )
        session.add(pass1)

        # Create Draft
        draft = ContentDraftModel(
            id="draft_sql_1",
            document_id="doc_sql_1",
            platform="linkedin",
            hook_title="Hook",
            primary_content="Content",
            review_status="draft"
        )
        session.add(draft)

        # Create Claim
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

        # Test cascade delete: deleting document should delete passages and drafts
        session.delete(d_check)
        session.commit()

        assert session.get(SourceDocumentModel, "doc_sql_1") is None
        assert session.get(SourcePassageModel, "pass_sql_1") is None
        assert session.get(ContentDraftModel, "draft_sql_1") is None
        assert session.get(ClaimEvidenceModel, "claim_sql_1") is None

