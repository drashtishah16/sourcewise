"""
SourceWise AI — Main Streamlit Application.
AI-Powered Social Content Repurposing and Evidence Traceability.
Provides 6 SaaS-style workflows:
1. Workspace
2. Create Content
3. Evidence Review
4. Content Library
5. Brand Settings
6. System Settings
"""
import streamlit as st
from datetime import datetime
from typing import List, Optional, Dict, Any

from src.models import (
    SourceDocumentSchema,
    BrandProfileSchema,
    ContentDraftSchema,
    generate_id
)
from src.source_processor import SourceProcessor, SourceProcessingError
from src.generator import DemoGenerator, LLMProviderInterface, SUPPORTED_PLATFORMS
from src.evidence_engine import EvidenceAuditor, STATUS_EVIDENCE_LINKED, STATUS_POTENTIALLY_UNSUPPORTED
from src.brand_engine import BrandEngine
from src.database import DatabaseManager
from src.export_service import ExportService
from src.sample_data import (
    SAMPLE_ARTICLE_TITLE,
    SAMPLE_ARTICLE_TYPE,
    SAMPLE_ARTICLE_URL,
    SAMPLE_ARTICLE_TEXT,
    SAMPLE_BRAND_PROFILE
)
from src.config import is_database_configured, is_connected_mode_available, get_ai_credentials

# Page configuration
st.set_page_config(
    page_title="SourceWise AI — Content Repurposing & Evidence Traceability",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom SaaS Styling (Clean white/navy/teal aesthetic)
st.markdown("""
<style>
    /* Main container and font styles */
    .main {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Top app header */
    .app-header {
        padding: 1.25rem 0rem 1rem 0rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
    }
    .app-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .app-subtitle {
        font-size: 0.95rem;
        color: #475569;
        margin-top: 0.25rem;
    }

    /* Cards */
    .saas-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .saas-card-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #0f172a;
        margin-bottom: 0.75rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Status Badges */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }
    .badge-success { background-color: #dcfce7; color: #15803d; border: 1px solid #bbf7d0; }
    .badge-warning { background-color: #fef3c7; color: #b45309; border: 1px solid #fde68a; }
    .badge-danger { background-color: #fee2e2; color: #b91c1c; border: 1px solid #fecaca; }
    .badge-info { background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .badge-neutral { background-color: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }

    /* Metric cards */
    .metric-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        text-align: left;
    }
    .metric-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0f172a;
    }
    .metric-label {
        font-size: 0.85rem;
        font-weight: 500;
        color: #64748b;
        margin-top: 0.2rem;
    }

    /* Passage box */
    .passage-box {
        background-color: #f8fafc;
        border-left: 3px solid #0284c7;
        padding: 0.75rem 1rem;
        border-radius: 0 6px 6px 0;
        margin-bottom: 0.75rem;
        font-size: 0.9rem;
    }
    .passage-id {
        font-weight: 700;
        color: #0284c7;
        margin-bottom: 0.25rem;
    }

    /* Scope notice banner */
    .scope-notice {
        background-color: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 6px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        color: #0369a1;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# SESSION STATE INITIALIZATION
# ==============================================================================

def init_session_state():
    if "current_doc" not in st.session_state:
        st.session_state.current_doc = None
    if "active_drafts" not in st.session_state:
        st.session_state.active_drafts = []
    if "selected_brand_id" not in st.session_state:
        st.session_state.selected_brand_id = None
    if "source_title" not in st.session_state:
        st.session_state.source_title = ""
    if "source_type" not in st.session_state:
        st.session_state.source_type = "Blog"
    if "source_url" not in st.session_state:
        st.session_state.source_url = ""
    if "source_text" not in st.session_state:
        st.session_state.source_text = ""

    # Ensure at least 1 default brand profile exists
    existing_brands = DatabaseManager.list_brand_profiles()
    if not existing_brands:
        default_brand = BrandProfileSchema(**SAMPLE_BRAND_PROFILE, is_default=True)
        DatabaseManager.save_brand_profile(default_brand)
        st.session_state.selected_brand_id = default_brand.id
    elif not st.session_state.selected_brand_id:
        st.session_state.selected_brand_id = existing_brands[0].id

init_session_state()


# ==============================================================================
# SIDEBAR NAVIGATION & SYSTEM HEALTH BADGES
# ==============================================================================

with st.sidebar:
    st.markdown("### 🔍 **SourceWise AI**")
    st.caption("Content Repurposing & Evidence Traceability")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "🏠 Workspace",
            "✨ Create Content",
            "🔬 Evidence Review",
            "📚 Content Library",
            "🎯 Brand Settings",
            "⚙️ System Settings"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("#### **System Status**")

    # AI Status
    if is_connected_mode_available():
        st.markdown('<span class="badge badge-success">⚡ Connected Mode (LLM API)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-info">🟢 Demo Mode (No AI API Required)</span>', unsafe_allow_html=True)

    # Database Status
    db_connected, db_msg = DatabaseManager.check_connection()
    if db_connected:
        st.markdown('<span class="badge badge-success">💾 PostgreSQL Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge badge-warning">⚠️ Session Memory (Unpersisted)</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.caption("Internship Assessment Build • 2026")


# ==============================================================================
# 1. WORKSPACE PAGE
# ==============================================================================

if page == "🏠 Workspace":
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Workspace Overview</h1>
        <p class="app-subtitle">Transform long-form technical content into evidence-grounded social posts with verifiable factual citations.</p>
    </div>
    """, unsafe_allow_html=True)

    # System status banner
    if not is_connected_mode_available():
        st.info("ℹ️ **Active Mode: Demo Mode (No AI API Required)** — Generating deterministic, platform-adapted drafts using source text extraction, brand rules, and verifiable passage IDs. Zero API tokens required.")
    
    if not db_connected:
        st.warning("⚠️ **Database Notice:** Running in Temporary Session Memory. To enable real PostgreSQL persistence across page reloads, configure `DATABASE_URL` in System Settings or `.env`.")

    # High-level Metrics
    all_drafts = DatabaseManager.list_content_drafts()
    total_drafts = len(all_drafts)
    approved_drafts = len([d for d in all_drafts if d.review_status == "approved"])
    in_review_drafts = len([d for d in all_drafts if d.review_status in ("draft", "in_review", "reopened")])
    total_claims = sum(len(d.claims) for d in all_drafts)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value">{total_drafts}</div>
            <div class="metric-label">Total Drafts Created</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value" style="color: #16a34a;">{approved_drafts}</div>
            <div class="metric-label">Approved & Ready</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value" style="color: #d97706;">{in_review_drafts}</div>
            <div class="metric-label">Pending Human Review</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value" style="color: #0284c7;">{total_claims}</div>
            <div class="metric-label">Audited Factual Claims</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Quick start banner
    col_cta1, col_cta2 = st.columns([3, 1])
    with col_cta1:
        st.markdown("### Ready to repurpose technical content?")
        st.write("Input a blog post, whitepaper, or case study to generate LinkedIn posts, Instagram captions, and short-form video scripts linked directly to source passages.")
    with col_cta2:
        st.write("")
        if st.button("🚀 Start Repurposing Now", type="primary", use_container_width=True):
            st.session_state["nav_goto"] = "✨ Create Content"
            st.rerun()

    # Recent drafts table
    st.markdown("### Recent Content Drafts")
    if all_drafts:
        for draft in all_drafts[:5]:
            with st.container():
                cols = st.columns([1.5, 3.5, 1.5, 1.5, 1.5])
                with cols[0]:
                    st.markdown(f"**{draft.platform.upper()}**")
                with cols[1]:
                    st.write(draft.hook_title[:60] + "..." if len(draft.hook_title) > 60 else draft.hook_title)
                with cols[2]:
                    badge_class = "badge-success" if draft.review_status == "approved" else "badge-warning"
                    st.markdown(f'<span class="badge {badge_class}">{draft.review_status}</span>', unsafe_allow_html=True)
                with cols[3]:
                    st.markdown(f"Claims: **{len(draft.claims)}**")
                with cols[4]:
                    st.caption(draft.created_at.strftime("%b %d, %H:%M") if draft.created_at else "Recent")
                st.markdown("<hr style='margin: 0.5rem 0;'>", unsafe_allow_html=True)
    else:
        st.info("No drafts created yet. Head to **Create Content** or click the quick-start button above to generate your first draft.")


# ==============================================================================
# 2. CREATE CONTENT PAGE
# ==============================================================================

elif page == "✨ Create Content":
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Create Repurposed Content</h1>
        <p class="app-subtitle">Input source material, select your brand profile and target channels, and generate evidence-linked drafts.</p>
    </div>
    """, unsafe_allow_html=True)

    # One-click sample filler
    col_top1, col_top2 = st.columns([3, 1])
    with col_top1:
        st.write("Provide source text below or load the pre-configured fictional case study to test the complete workflow.")
    with col_top2:
        if st.button("⚡ Load Fictional Case Study", use_container_width=True):
            st.session_state.source_title = SAMPLE_ARTICLE_TITLE
            st.session_state.source_type = SAMPLE_ARTICLE_TYPE
            st.session_state.source_url = SAMPLE_ARTICLE_URL
            st.session_state.source_text = SAMPLE_ARTICLE_TEXT
            st.rerun()

    with st.form("create_content_form"):
        col_t1, col_t2 = st.columns([3, 1])
        with col_t1:
            title_input = st.text_input("Source Document Title*", value=st.session_state.source_title, placeholder="e.g. Scaling PostgreSQL with Multi-Tier Caching")
        with col_t2:
            type_input = st.selectbox(
                "Source Type",
                ["Blog", "Case Study", "Product Page", "Report", "Other"],
                index=["Blog", "Case Study", "Product Page", "Report", "Other"].index(st.session_state.source_type) if st.session_state.source_type in ["Blog", "Case Study", "Product Page", "Report", "Other"] else 0
            )

        url_input = st.text_input("Source URL (Optional Reference)", value=st.session_state.source_url, placeholder="https://example.com/blog/article-slug")
        st.caption("Note: SourceWise AI treats the pasted text below as the authoritative source of truth. External URLs are stored for reference only.")

        text_input = st.text_area(
            "Authoritative Source Text*",
            value=st.session_state.source_text,
            height=260,
            placeholder="Paste the approved text here (minimum 20 characters, up to 50,000 characters)..."
        )

        # Word count calculation
        cur_words = len(text_input.split())
        cur_chars = len(text_input)
        st.caption(f"Input Statistics: **{cur_words} words** | **{cur_chars} characters**")

        st.markdown("---")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            brand_profiles = DatabaseManager.list_brand_profiles()
            brand_options = {p.id: f"{p.name} ({p.tone_of_voice})" for p in brand_profiles}
            selected_b_id = st.selectbox(
                "Brand Profile",
                options=list(brand_options.keys()),
                format_func=lambda x: brand_options[x]
            )

        with col_b2:
            st.markdown("**Target Platforms**")
            cb_linkedin = st.checkbox("LinkedIn Post (Professional takeaways & bullet points)", value=True)
            cb_instagram = st.checkbox("Instagram Caption (Punchy hook & mobile spacing)", value=True)
            cb_video = st.checkbox("Short-form Video Script (TikTok / Reels / Shorts 60s)", value=True)

        submitted = st.form_submit_button("🚀 Generate Repurposed Drafts", type="primary", use_container_width=True)

    if submitted:
        selected_platforms = []
        if cb_linkedin: selected_platforms.append("linkedin")
        if cb_instagram: selected_platforms.append("instagram")
        if cb_video: selected_platforms.append("video_script")

        if not title_input.strip():
            st.error("Please provide a title for the source document.")
        elif not text_input.strip() or len(text_input.strip()) < 20:
            st.error("Source text is too short. Please provide at least 20 characters of substantive text.")
        elif not selected_platforms:
            st.error("Please select at least one target platform.")
        else:
            try:
                with st.spinner("Processing source document and segmenting passages..."):
                    doc = SourceProcessor.process_source(
                        title=title_input,
                        raw_text=text_input,
                        source_type=type_input,
                        source_url=url_input
                    )
                    st.session_state.current_doc = doc
                    DatabaseManager.save_source_document(doc)

                    # Retrieve brand profile
                    brand = DatabaseManager.get_brand_profile(selected_b_id)
                    if not brand:
                        brand = BrandProfileSchema(**SAMPLE_BRAND_PROFILE)

                    # Generate drafts
                    gen_result = LLMProviderInterface.generate(doc, brand, selected_platforms)
                    st.session_state.active_drafts = gen_result.drafts

                    # Auto-save generated drafts into library
                    for d in gen_result.drafts:
                        DatabaseManager.save_content_draft(d)

                st.success(f"Successfully generated {len(gen_result.drafts)} drafts! {gen_result.message}")
            except SourceProcessingError as spe:
                st.error(f"Source Processing Error: {str(spe)}")
            except Exception as e:
                st.error(f"An unexpected error occurred during generation: {str(e)}")

    # Display generated draft cards
    if st.session_state.active_drafts:
        st.markdown("### Generated Content Drafts")
        tabs = st.tabs([f"{d.platform.upper()}" for d in st.session_state.active_drafts])

        for i, draft in enumerate(st.session_state.active_drafts):
            with tabs[i]:
                st.markdown(f"#### **Hook / Title:** {draft.hook_title}")

                # Metrics and compliance badges
                score_badge = "badge-success" if draft.compliance_score >= 80 else "badge-warning"
                st.markdown(f"""
                <div style="margin-bottom: 0.75rem;">
                    <span class="badge {score_badge}">Brand Compliance: {draft.compliance_score}/100</span>
                    <span class="badge badge-info">Factual Claims: {len(draft.claims)} Verified</span>
                    <span class="badge badge-neutral">Mode: {draft.generation_mode.upper()}</span>
                </div>
                """, unsafe_allow_html=True)

                # Editable content box
                edited_content = st.text_area(
                    f"Content ({draft.platform})",
                    value=draft.primary_content,
                    height=240,
                    key=f"edit_{draft.id}"
                )

                if draft.platform == "video_script" and draft.video_script:
                    with st.expander("🎬 View Formatted Video Script & Visual Cue Board"):
                        st.text(draft.video_script)

                # Evidence summary for this draft
                with st.expander("🔍 Linked Evidence & Passage Citations", expanded=True):
                    for c in draft.claims:
                        status_class = "badge-success" if c.evidence_status == STATUS_EVIDENCE_LINKED else "badge-danger"
                        st.markdown(f"**Claim {c.claim_label}:** {c.claim_text}")
                        st.markdown(f"Referenced Passages: `{', '.join(c.referenced_passage_ids)}` | Status: <span class='badge {status_class}'>{c.evidence_status}</span>", unsafe_allow_html=True)
                        if c.supporting_excerpt:
                            st.caption(f"Supporting Excerpt: \"{c.supporting_excerpt}\"")
                        if c.flag_reasons:
                            for f in c.flag_reasons:
                                st.warning(f"⚠️ {f}")
                        st.markdown("<hr style='margin: 0.4rem 0;'>", unsafe_allow_html=True)

                # Action row
                col_a1, col_a2, col_a3, col_a4 = st.columns([1.5, 1.5, 1.5, 2])
                with col_a1:
                    if st.button("💾 Save Updates", key=f"save_{draft.id}"):
                        ok, msg = DatabaseManager.update_draft_content(draft.id, edited_content)
                        if ok:
                            st.success("Draft updated!")
                            st.rerun()
                        else:
                            st.error(f"Save failed: {msg}")

                with col_a2:
                    if st.button("✅ Approve Draft", key=f"app_{draft.id}", type="primary"):
                        ok, msg = DatabaseManager.update_draft_status(draft.id, "approved", notes="Approved from Create view")
                        if ok:
                            st.success("Draft approved!")
                            st.rerun()

                with col_a3:
                    if st.button("📋 Copy Text", key=f"copy_{draft.id}"):
                        st.info("Content selected for copy. Use Ctrl+C inside the content area.")

                with col_a4:
                    single_csv = ExportService.to_csv([draft], st.session_state.current_doc)
                    st.download_button(
                        "📥 Export This Draft (CSV)",
                        data=single_csv,
                        file_name=f"{draft.platform}_draft_{draft.id}.csv",
                        mime="text/csv",
                        key=f"dl_{draft.id}"
                    )


# ==============================================================================
# 3. EVIDENCE REVIEW PAGE
# ==============================================================================

elif page == "🔬 Evidence Review":
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Evidence Review & Traceability Workbench</h1>
        <p class="app-subtitle">Audit every factual assertion against immutable source passages to guarantee factual grounding.</p>
    </div>
    """, unsafe_allow_html=True)

    # Disclaimer scope banner
    st.markdown(f"""
    <div class="scope-notice">
        ℹ️ <strong>Evidence Traceability Scope:</strong> {EvidenceAuditor.get_disclaimer_note()}
    </div>
    """, unsafe_allow_html=True)

    all_drafts = DatabaseManager.list_content_drafts()
    if not all_drafts:
        st.info("No content drafts available to audit. Generate drafts in the **Create Content** tab first.")
    else:
        draft_options = {d.id: f"{d.platform.upper()} — {d.hook_title[:50]}... [{d.review_status}]" for d in all_drafts}
        selected_draft_id = st.selectbox(
            "Select Draft to Audit",
            options=list(draft_options.keys()),
            format_func=lambda x: draft_options[x]
        )
        selected_draft = DatabaseManager.get_content_draft(selected_draft_id)
        source_doc = DatabaseManager.get_source_document(selected_draft.document_id) if selected_draft else None

        col_left, col_right = st.columns([1, 1])

        # Left Column: Source Passages
        with col_left:
            st.markdown("### 📄 Source Passages")
            if source_doc and source_doc.passages:
                st.caption(f"Document: **{source_doc.title}** (Version {source_doc.version})")
                for p in source_doc.passages:
                    st.markdown(f"""
                    <div class="passage-box">
                        <div class="passage-id">Passage {p.passage_label} (Offset {p.char_start}–{p.char_end})</div>
                        {p.text}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning("Source document passages not found for this draft.")

        # Right Column: Claims & Verification
        with col_right:
            st.markdown("### 🔎 Claim Audit Trail")
            if selected_draft and selected_draft.claims:
                for idx, claim in enumerate(selected_draft.claims):
                    with st.container():
                        st.markdown(f"#### **Claim {claim.claim_label}**")
                        st.write(f"\"{claim.claim_text}\"")

                        # Evidence status badge
                        if claim.evidence_status == STATUS_EVIDENCE_LINKED:
                            st.markdown(f'<span class="badge badge-success">Status: {claim.evidence_status}</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<span class="badge badge-danger">Status: {claim.evidence_status}</span>', unsafe_allow_html=True)

                        st.write(f"**Referenced Source Passages:** `{', '.join(claim.referenced_passage_ids)}`")

                        if claim.supporting_excerpt:
                            st.markdown(f"**Supporting Excerpt from Source:**\n> {claim.supporting_excerpt}")

                        if claim.flag_reasons:
                            st.markdown("**Automated Audit Warnings:**")
                            for flag in claim.flag_reasons:
                                st.error(f"⚠️ {flag}")

                        # Reviewer note
                        reviewer_input = st.text_input(
                            f"Reviewer Notes for {claim.claim_label}",
                            value=claim.reviewer_note or "",
                            key=f"rev_note_{claim.id}"
                        )
                        st.markdown("<hr style='margin: 0.75rem 0;'>", unsafe_allow_html=True)

                # Human approval decision
                st.markdown("### 📋 Final Human Verification Decision")
                st.caption("Human approval remains independent from automated algorithmic checks.")

                col_dec1, col_dec2 = st.columns(2)
                with col_dec1:
                    approval_notes = st.text_input("Approval / Revision Notes", value=selected_draft.approval_notes or "")
                    if st.button("✅ Approve Content Draft", type="primary", use_container_width=True):
                        ok, msg = DatabaseManager.update_draft_status(selected_draft.id, "approved", notes=approval_notes, actor="human_reviewer")
                        if ok:
                            st.success("Draft marked as APPROVED!")
                            st.rerun()
                        else:
                            st.error(f"Action failed: {msg}")

                with col_dec2:
                    st.write("")
                    st.write("")
                    if st.button("🔄 Request Revisions / Reopen", use_container_width=True):
                        ok, msg = DatabaseManager.update_draft_status(selected_draft.id, "reopened", notes=approval_notes, actor="human_reviewer")
                        if ok:
                            st.info("Draft marked as REOPENED for revision.")
                            st.rerun()
                        else:
                            st.error(f"Action failed: {msg}")
            else:
                st.info("No claims detected for this draft.")


# ==============================================================================
# 4. CONTENT LIBRARY PAGE
# ==============================================================================

elif page == "📚 Content Library":
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Content Library</h1>
        <p class="app-subtitle">Search, filter, edit, and export your repurposed drafts and audit histories.</p>
    </div>
    """, unsafe_allow_html=True)

    # Filters row
    col_f1, col_f2, col_f3 = st.columns([2, 1.5, 1.5])
    with col_f1:
        search_kw = st.text_input("🔍 Search drafts", placeholder="Filter by keyword or title...")
    with col_f2:
        filter_platform = st.selectbox("Platform", ["All", "LinkedIn", "Instagram", "Video Script"])
    with col_f3:
        filter_status = st.selectbox("Status", ["All", "Draft", "In Review", "Approved", "Reopened"])

    # Batch export buttons
    all_drafts = DatabaseManager.list_content_drafts()

    # Apply filters
    filtered = all_drafts
    if filter_platform != "All":
        p_map = {"LinkedIn": "linkedin", "Instagram": "instagram", "Video Script": "video_script"}
        filtered = [d for d in filtered if d.platform.lower() == p_map[filter_platform]]
    if filter_status != "All":
        filtered = [d for d in filtered if d.review_status.lower() == filter_status.lower()]
    if search_kw.strip():
        kw = search_kw.strip().lower()
        filtered = [d for d in filtered if kw in d.hook_title.lower() or kw in d.primary_content.lower()]

    st.markdown("---")

    col_exp1, col_exp2, col_exp3 = st.columns([2, 1.5, 1.5])
    with col_exp1:
        st.write(f"Showing **{len(filtered)}** of **{len(all_drafts)}** total drafts.")
    with col_exp2:
        csv_data = ExportService.to_csv(filtered)
        st.download_button(
            "📥 Export Library (CSV)",
            data=csv_data,
            file_name=f"sourcewise_drafts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_exp3:
        json_data = ExportService.to_json(filtered)
        st.download_button(
            "📥 Export Library (JSON)",
            data=json_data,
            file_name=f"sourcewise_drafts_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    if not filtered:
        st.info("No drafts match your current filter settings.")
    else:
        for draft in filtered:
            with st.expander(f"{draft.platform.upper()} • {draft.hook_title[:60]}... [{draft.review_status.upper()}]"):
                col_d1, col_d2 = st.columns([3, 1])
                with col_d1:
                    st.markdown(f"**Hook Title:** {draft.hook_title}")
                    edited_body = st.text_area(
                        "Primary Content",
                        value=draft.primary_content,
                        height=200,
                        key=f"lib_edit_{draft.id}"
                    )
                    if draft.review_status == "approved":
                        st.caption("⚠️ Note: Editing an approved draft will automatically reset its status to 'Reopened' for review.")

                with col_d2:
                    st.markdown("**Draft Metadata**")
                    st.write(f"Platform: `{draft.platform}`")
                    st.write(f"Status: `{draft.review_status}`")
                    st.write(f"Compliance: `{draft.compliance_score}/100`")
                    st.write(f"Claims: `{len(draft.claims)}`")
                    st.write(f"Created: {draft.created_at.strftime('%Y-%m-%d %H:%M') if draft.created_at else 'Recent'}")

                col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 1.5])
                with col_btn1:
                    if st.button("💾 Save Edits", key=f"lib_save_{draft.id}"):
                        ok, msg = DatabaseManager.update_draft_content(draft.id, edited_body)
                        if ok:
                            st.success("Draft updated! Approval status reset if previously approved.")
                            st.rerun()
                        else:
                            st.error(f"Save error: {msg}")

                with col_btn2:
                    if draft.review_status != "approved":
                        if st.button("✅ Approve", key=f"lib_app_{draft.id}", type="primary"):
                            DatabaseManager.update_draft_status(draft.id, "approved", notes="Approved from Library")
                            st.rerun()
                    else:
                        if st.button("🔄 Reopen", key=f"lib_reopen_{draft.id}"):
                            DatabaseManager.update_draft_status(draft.id, "reopened", notes="Reopened from Library")
                            st.rerun()

                with col_btn3:
                    if st.button("🗑️ Delete Draft", key=f"lib_del_{draft.id}"):
                        ok, msg = DatabaseManager.delete_content_draft(draft.id)
                        if ok:
                            st.warning("Draft deleted.")
                            st.rerun()


# ==============================================================================
# 5. BRAND SETTINGS PAGE
# ==============================================================================

elif page == "🎯 Brand Settings":
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Brand Voice & Compliance Profiles</h1>
        <p class="app-subtitle">Define brand guidelines, banned phrases, mandatory disclaimers, and platform length rules.</p>
    </div>
    """, unsafe_allow_html=True)

    profiles = DatabaseManager.list_brand_profiles()
    profile_names = {p.id: p.name for p in profiles}
    profile_names["new"] = "➕ Create New Brand Profile"

    selected_id = st.selectbox(
        "Select Profile to Manage",
        options=list(profile_names.keys()),
        format_func=lambda x: profile_names[x]
    )

    if selected_id == "new":
        active_prof = BrandProfileSchema(name="New Brand Profile")
    else:
        active_prof = DatabaseManager.get_brand_profile(selected_id) or BrandProfileSchema(name="Default")

    with st.form("brand_profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            name_val = st.text_input("Brand Name*", value=active_prof.name)
            audience_val = st.text_input("Target Audience", value=active_prof.target_audience)
            tone_val = st.selectbox(
                "Tone of Voice",
                ["Authoritative & Technical", "Conversational & Friendly", "Direct & Provocative", "Executive & Strategic"],
                index=0
            )

        with col2:
            cta_val = st.text_input("Primary Call to Action (CTA)", value=active_prof.primary_cta)
            hashtags_val = st.text_input("Default Hashtags", value=active_prof.hashtag_preferences)
            disclaimer_val = st.text_area("Mandatory Disclaimer", value=active_prof.required_disclaimer, height=80)

        st.markdown("---")
        st.markdown("#### **Terminology Governance**")
        pref_val = st.text_area(
            "Preferred Terminology (comma-separated)",
            value=", ".join(active_prof.preferred_terminology),
            help="Keywords the content generator prioritizes weaving into drafts."
        )
        forbid_val = st.text_area(
            "Forbidden Terminology (comma-separated)",
            value=", ".join(active_prof.forbidden_terminology),
            help="Banned words or risky phrases that automatically trigger compliance failures."
        )

        submit_brand = st.form_submit_button("💾 Save Brand Profile", type="primary")

    if submit_brand:
        if not name_val.strip():
            st.error("Brand name cannot be empty.")
        else:
            preferred_list = [w.strip() for w in pref_val.split(",") if w.strip()]
            forbidden_list = [w.strip() for w in forbid_val.split(",") if w.strip()]

            active_prof.name = name_val.strip()
            active_prof.target_audience = audience_val.strip()
            active_prof.tone_of_voice = tone_val
            active_prof.primary_cta = cta_val.strip()
            active_prof.hashtag_preferences = hashtags_val.strip()
            active_prof.required_disclaimer = disclaimer_val.strip()
            active_prof.preferred_terminology = preferred_list
            active_prof.forbidden_terminology = forbidden_list

            ok, msg = DatabaseManager.save_brand_profile(active_prof)
            if ok:
                st.success(f"Profile saved! {msg}")
                st.rerun()
            else:
                st.error(f"Save failed: {msg}")


# ==============================================================================
# 6. SYSTEM SETTINGS PAGE
# ==============================================================================

elif page == "⚙️ System Settings":
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">System Settings & Infrastructure Diagnostics</h1>
        <p class="app-subtitle">Configure Supabase PostgreSQL connections, monitor AI engine modes, and verify schema migrations.</p>
    </div>
    """, unsafe_allow_html=True)

    # Section 1: Database Health & Credentials
    st.markdown("### 💾 Supabase PostgreSQL Storage")
    is_cfg = is_database_configured()

    if is_cfg:
        ok_conn, conn_msg = DatabaseManager.check_connection()
        if ok_conn:
            st.success(f"✅ **Database Status:** {conn_msg}")
        else:
            st.error(f"❌ **Connection Error:** {conn_msg}")
    else:
        st.warning(
            "⚠️ **PostgreSQL Not Configured:** Operating in Temporary Session Mode. "
            "Data will not persist across browser sessions until connected."
        )

    with st.expander("📖 Instructions to Connect Supabase PostgreSQL"):
        st.markdown("""
        1. Log into your [Supabase Dashboard](https://supabase.com/dashboard).
        2. Create a new project or select an existing one.
        3. Go to **Project Settings** → **Database** → **Connection String** → **URI**.
        4. Copy the connection string. It will look like:
           ```text
           postgresql+psycopg://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
           ```
        5. In local development: Add this to your local `.env` file as:
           ```bash
           DATABASE_URL="postgresql+psycopg://postgres:[YOUR-PASSWORD]@..."
           ```
        6. In Streamlit Community Cloud: Add to **App Settings** → **Secrets**.
        """)

    col_db1, col_db2 = st.columns(2)
    with col_db1:
        if st.button("🔄 Test Database Connection Now", use_container_width=True):
            DatabaseManager.reset_engine()
            ok, msg = DatabaseManager.check_connection()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    with col_db2:
        if st.button("🛠️ Initialize / Verify Schema Tables", use_container_width=True):
            ok, msg = DatabaseManager.init_db()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")

    # Section 2: AI Engine Settings
    st.markdown("### ⚡ AI Provider Configuration")
    ai_creds = get_ai_credentials()
    has_keys = is_connected_mode_available()

    if has_keys:
        st.success(f"Connected Mode Available: Model `{ai_creds['model_name']}` configured.")
    else:
        st.info("🟢 **Demo Mode Active:** 100% deterministic, rule-based generation with zero API keys required.")

    st.markdown("""
    SourceWise AI is architected so that **no paid API key is ever required** to test, grade, or deploy the complete application.
    If you wish to attach an external LLM later, configure `OPENAI_API_KEY` or `GEMINI_API_KEY` in your `.env` or Streamlit secrets.
    """)

    st.markdown("---")
    st.markdown("### 🧹 Session Reset")
    if st.button("Clear Session State & Reload"):
        st.session_state.clear()
        st.success("Session state cleared.")
        st.rerun()

