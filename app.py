"""
SourceWise AI — Main Streamlit Application.
AI-Powered Social Content Repurposing and Evidence Traceability.
Provides 6 SaaS workflows:
1. Workspace
2. Create Content
3. Evidence Review
4. Content Library
5. Brand Settings
6. System Settings
"""
import logging
import streamlit as st
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import text

from src.models import (
    SourceDocumentSchema,
    BrandProfileSchema,
    ContentDraftSchema,
    generate_id
)
from src.source_processor import SourceProcessor, SourceProcessingError
from src.generator import DemoGenerator, LLMProviderInterface, SUPPORTED_PLATFORMS
from src.gemini_service import GeminiGenerator, GeminiGenerationError, sanitize_ai_error
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
from src.config import (
    is_database_configured,
    is_connected_mode_available,
    get_ai_credentials,
    get_database_path,
    is_gemini_configured,
    get_gemini_model,
    get_gemini_api_key
)

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="SourceWise AI — Content Repurposing & Evidence Traceability",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom SaaS Styling (Unique Dark Sidebar with Modern High-Contrast Canvas)
st.markdown("""
<style>
    /* Global Layout & Typography */
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
        font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Top Header Bar */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* ==========================================================================
       UNIQUE OBSIDIAN SAAS SIDEBAR
       ========================================================================== */
    section[data-testid="stSidebar"] {
        background-color: #0b0f19 !important;
        border-right: 1px solid #1e293b !important;
    }
    section[data-testid="stSidebar"] * {
        color: #94a3b8;
    }
    
    .sw-sidebar-brand {
        display: flex;
        align-items: center;
        gap: 0.85rem;
        padding: 0.75rem 0.25rem 1.25rem 0.25rem;
        border-bottom: 1px solid #1e293b;
        margin-bottom: 1.25rem;
    }
    .sw-brand-icon {
        width: 38px;
        height: 38px;
        background: linear-gradient(135deg, #3b82f6 0%, #6366f1 50%, #8b5cf6 100%);
        color: #ffffff !important;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 1.15rem;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .sw-brand-text {
        display: flex;
        flex-direction: column;
    }
    .sw-brand-name {
        font-size: 1.15rem;
        font-weight: 700;
        color: #f8fafc !important;
        letter-spacing: -0.025em;
        line-height: 1.2;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .sw-brand-badge {
        font-size: 0.65rem;
        font-weight: 700;
        background: linear-gradient(90deg, #2563eb, #7c3aed);
        color: #ffffff !important;
        padding: 0.15rem 0.45rem;
        border-radius: 4px;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .sw-brand-sub {
        font-size: 0.75rem;
        color: #64748b !important;
        font-weight: 500;
        margin-top: 2px;
    }

    .sw-nav-section-title {
        font-size: 0.7rem;
        font-weight: 700;
        color: #475569 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 0.5rem 0.6rem 0.35rem 0.6rem;
        margin-top: 0.25rem;
    }

    /* Unique Navigation Items */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] > div {
        gap: 0.35rem;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        padding: 0.65rem 0.9rem !important;
        border-radius: 8px !important;
        background-color: transparent !important;
        transition: all 0.15s ease-in-out !important;
        cursor: pointer !important;
        border: 1px solid transparent !important;
    }
    /* Hide the default radio circle */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
        display: none !important;
    }
    /* Navigation typography */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        color: #94a3b8 !important;
        margin: 0 !important;
        transition: color 0.15s ease !important;
    }
    /* Hover State */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border-color: rgba(255, 255, 255, 0.05) !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:hover div[data-testid="stMarkdownContainer"] p {
        color: #f1f5f9 !important;
    }
    /* Active Selected State */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        background: linear-gradient(90deg, rgba(37, 99, 235, 0.18) 0%, rgba(99, 102, 241, 0.08) 100%) !important;
        border: 1px solid rgba(59, 130, 246, 0.3) !important;
        border-left: 3px solid #3b82f6 !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p {
        color: #ffffff !important;
        font-weight: 600 !important;
    }

    /* Sidebar Footer */
    .sw-sidebar-footer {
        margin-top: 2.5rem;
        padding-top: 1rem;
        border-top: 1px solid #1e293b;
    }
    .sw-footer-card {
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
        display: flex;
        align-items: center;
        gap: 0.65rem;
    }
    .sw-footer-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10b981;
        box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
    }
    .sw-footer-text {
        font-size: 0.75rem;
        color: #94a3b8 !important;
        line-height: 1.3;
    }
    .sw-footer-title {
        font-weight: 600;
        color: #f1f5f9 !important;
    }

    /* Top Page Header */
    .app-header {
        padding: 0.5rem 0rem 1.25rem 0rem;
        border-bottom: 1px solid #e2e8f0;
        margin-bottom: 1.5rem;
    }
    .app-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
        letter-spacing: -0.025em;
    }
    .app-subtitle {
        font-size: 0.95rem;
        color: #475569;
        margin-top: 0.35rem;
        line-height: 1.4;
    }

    /* Card Containers */
    .saas-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
    }
    .saas-card-header {
        font-size: 1.05rem;
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

    /* Metric Cards */
    .metric-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.1rem 1.25rem;
        text-align: left;
        box-shadow: 0 1px 2px rgba(0,0,0,0.02);
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 700;
        color: #0f172a;
        line-height: 1.1;
    }
    .metric-label {
        font-size: 0.825rem;
        font-weight: 600;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 0.4rem;
    }

    /* Canonical Passage Box */
    .passage-box {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-left: 3px solid #0284c7;
        padding: 0.85rem 1rem;
        border-radius: 0 6px 6px 0;
        margin-bottom: 0.75rem;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .passage-id {
        font-weight: 700;
        color: #0284c7;
        margin-bottom: 0.25rem;
        font-size: 0.85rem;
    }

    /* Traceability Scope Notice */
    .scope-notice {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 3px solid #64748b;
        border-radius: 4px;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        color: #475569;
        margin-bottom: 1.25rem;
        line-height: 1.5;
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
# SIDEBAR NAVIGATION (UNIQUE OBSIDIAN SAAS INTERFACE)
# ==============================================================================

with st.sidebar:
    st.markdown("""
    <div class="sw-sidebar-brand">
        <div class="sw-brand-icon">
            <span>S</span>
        </div>
        <div class="sw-brand-text">
            <div class="sw-brand-name">SourceWise <span class="sw-brand-badge">AI</span></div>
            <div class="sw-brand-sub">Traceable Repurposing</div>
        </div>
    </div>
    <div class="sw-nav-section-title">PLATFORM NAVIGATION</div>
    """, unsafe_allow_html=True)

    nav_options = [
        "⊞  Workspace",
        "✦  Create Content",
        "⚲  Evidence Review",
        "▤  Content Library",
        "◎  Brand Settings",
        "⚙  Engine & Settings"
    ]

    selected_nav = st.radio(
        "Navigation",
        nav_options,
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("""
    <div class="sw-sidebar-footer">
        <div class="sw-footer-card">
            <div class="sw-footer-dot"></div>
            <div class="sw-footer-text">
                <div class="sw-footer-title">Workspace Active</div>
                <div>SourceWise Studio • Ready</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 1. WORKSPACE PAGE
# ==============================================================================

if "Workspace" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Workspace Overview</h1>
        <p class="app-subtitle">Transform long-form technical content into evidence-grounded social posts with verifiable factual citations.</p>
    </div>
    """, unsafe_allow_html=True)

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
            <div class="metric-value">{approved_drafts}</div>
            <div class="metric-label">Approved Content</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value">{in_review_drafts}</div>
            <div class="metric-label">Pending Reviews</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-box">
            <div class="metric-value">{total_claims}</div>
            <div class="metric-label">Verified Claims</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # Quick Start Actions
    col_act1, col_act2 = st.columns([2, 1])
    with col_act1:
        st.markdown("### Quick Start Workflow")
        st.markdown("""
        1. **Create Repurposed Content**: Ingest whitepapers or blogs, segment into numbered passages (`S1`, `S2`...), and generate platform-optimized social posts.
        2. **Audit Evidence & Grounding**: Review citations side-by-side with source text. Ensure all statistics, benchmarks, and quotes match.
        3. **Approve & Export**: Confirm brand compliance scores and export verified drafts to RFC 4180 CSV or structured JSON.
        """)

    with col_act2:
        st.markdown("### Actions")
        if st.button("✨ Repurpose Fictional Case Study", use_container_width=True, type="primary"):
            st.session_state.source_title = SAMPLE_ARTICLE_TITLE
            st.session_state.source_type = SAMPLE_ARTICLE_TYPE
            st.session_state.source_url = SAMPLE_ARTICLE_URL
            st.session_state.source_text = SAMPLE_ARTICLE_TEXT
            st.success("Loaded NexusPay case study! Navigate to 'Create Content' to generate.")

    st.markdown("---")

    # Recent drafts table
    st.markdown("### Recent Repurposed Drafts")
    if all_drafts:
        for draft in all_drafts[:5]:
            with st.container():
                c_d1, c_d2, c_d3, c_d4 = st.columns([3, 1, 1, 1])
                with c_d1:
                    st.markdown(f"**{draft.hook_title}**")
                    st.caption(f"Platform: `{draft.platform.upper()}` • Mode: `{draft.generation_mode.upper()}`")
                with c_d2:
                    badge_class = "badge-success" if draft.review_status == "approved" else "badge-warning"
                    st.markdown(f'<span class="badge {badge_class}">{draft.review_status}</span>', unsafe_allow_html=True)
                with c_d3:
                    st.write(f"Claims: **{len(draft.claims)}**")
                with c_d4:
                    st.write(f"Score: **{draft.compliance_score}/100**")
                st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #f1f5f9;'/>", unsafe_allow_html=True)
    else:
        st.info("No drafts created yet. Head to **Create Content** to repurpose your first source document.")


# ==============================================================================
# 2. CREATE CONTENT PAGE
# ==============================================================================

elif "Create Content" in selected_nav:
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
            title_input = st.text_input("Source Document Title*", value=st.session_state.source_title, placeholder="e.g. Scaling Technical Architecture with Multi-Tier Caching")
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

        # Subtle helper line beside action
        gemini_ready = is_gemini_configured()
        if gemini_ready:
            btn_label = f"✨ Generate Repurposed Drafts (Gemini AI: {get_gemini_model()})"
        else:
            btn_label = "🚀 Generate Repurposed Drafts"
            st.caption("ℹ️ Configure `GEMINI_API_KEY` to enable real Gemini AI generation. Running with deterministic rules.")

        submitted = st.form_submit_button(btn_label, type="primary", use_container_width=True)

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
                with st.spinner("Processing source document and generating evidence-grounded drafts..."):
                    doc = SourceProcessor.process_source(
                        title=title_input,
                        raw_text=text_input,
                        source_type=type_input,
                        source_url=url_input
                    )
                    st.session_state.current_doc = doc
                    save_doc_ok, _ = DatabaseManager.save_source_document(doc)

                    # Retrieve brand profile
                    brand = DatabaseManager.get_brand_profile(selected_b_id)
                    if not brand:
                        brand = BrandProfileSchema(**SAMPLE_BRAND_PROFILE)

                    # Generate drafts via LLMProviderInterface (Gemini when configured, Demo otherwise)
                    gen_result = LLMProviderInterface.generate(doc, brand, selected_platforms)
                    st.session_state.active_drafts = gen_result.drafts

                    # Auto-save generated drafts into database
                    saved_count = 0
                    for d in gen_result.drafts:
                        save_draft_ok, _ = DatabaseManager.save_content_draft(d)
                        if save_draft_ok:
                            saved_count += 1

                if saved_count == len(gen_result.drafts):
                    st.success(f"Generated and saved {len(gen_result.drafts)} drafts successfully. ({gen_result.message})")
                else:
                    st.success(f"Generated {len(gen_result.drafts)} drafts. ({gen_result.message})")

            except GeminiGenerationError as ge:
                logger.error("Gemini generation failed: %s", str(ge))
                st.error("Content generation is temporarily unavailable. Please try again.")
            except SourceProcessingError as spe:
                st.error(f"Source Document Issue: {str(spe)}")
            except Exception as e:
                logger.error("Unexpected generation error: %s", sanitize_ai_error(str(e)))
                st.error("Content generation is temporarily unavailable. Please try again.")

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
                    key=f"edit_draft_{draft.id}"
                )

                if st.button(f"Save Content Changes ({draft.platform.upper()})", key=f"save_btn_{draft.id}"):
                    if edited_content != draft.primary_content:
                        DatabaseManager.update_draft_content(draft.id, edited_content, reset_approval=True)
                        draft.primary_content = edited_content
                        draft.review_status = "reopened"
                        st.info("Content updated. Review status reset to REOPENED for compliance safety.")
                    else:
                        st.success("No modifications detected.")

                # Evidence & Claim Traceability Summary
                st.markdown("##### Grounded Claims & Citations")
                for c in draft.claims:
                    status_class = "badge-success" if c.evidence_status == STATUS_EVIDENCE_LINKED else "badge-warning"
                    with st.expander(f"{c.claim_label}: {c.claim_text[:90]}..."):
                        st.markdown(f"Referenced Passages: `{', '.join(c.referenced_passage_ids)}` | Status: <span class='badge {status_class}'>{c.evidence_status}</span>", unsafe_allow_html=True)
                        if c.supporting_excerpt:
                            st.caption(f"Supporting Excerpt: \"{c.supporting_excerpt}\"")
                        if c.flag_reasons:
                            for f in c.flag_reasons:
                                st.warning(f"⚠️ {f}")

                # Quick action buttons
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"✅ Approve Draft for {draft.platform.upper()}", key=f"app_{draft.id}", use_container_width=True):
                        DatabaseManager.update_draft_status(draft.id, "approved", notes="Directly approved from Creator view.")
                        draft.review_status = "approved"
                        st.success(f"{draft.platform.upper()} draft approved!")
                        st.rerun()
                with col_btn2:
                    if st.button(f"📋 Copy to Clipboard", key=f"copy_{draft.id}", use_container_width=True):
                        st.info("Content selected for copy. Use Ctrl+C inside the content area.")


# ==============================================================================
# 3. EVIDENCE REVIEW PAGE
# ==============================================================================

elif "Evidence Review" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Evidence Review & Traceability Workbench</h1>
        <p class="app-subtitle">Inspect source passages side-by-side with generated claims to verify metrics, quotes, and citations before publication.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="scope-notice">
        <strong>Traceability Notice:</strong> SourceWise AI audits whether factual assertions directly reflect the provided source text passages. An 'Evidence Linked' status confirms textual alignment with the provided document; it does not independently certify external real-world truth.
    </div>
    """, unsafe_allow_html=True)

    all_drafts = DatabaseManager.list_content_drafts()
    if not all_drafts:
        st.info("No content drafts available to audit. Generate drafts in the **Create Content** tab first.")
    else:
        draft_options = {d.id: f"{d.platform.upper()} — {d.hook_title[:60]}... ({d.review_status})" for d in all_drafts}
        selected_draft_id = st.selectbox(
            "Select Draft to Audit",
            options=list(draft_options.keys()),
            format_func=lambda x: draft_options[x]
        )

        selected_draft = DatabaseManager.get_content_draft(selected_draft_id)
        if selected_draft:
            col_rev_l, col_rev_r = st.columns([1, 1])

            # Left Column: Canonical Passages
            with col_rev_l:
                st.markdown("### 📄 Canonical Source Passages")
                doc = DatabaseManager.get_source_document(selected_draft.document_id)
                if doc and doc.passages:
                    st.caption(f"Document: **{doc.title}** (Version {doc.version})")
                    for p in doc.passages:
                        st.markdown(f"""
                        <div class="passage-box">
                            <div class="passage-id">[{p.passage_label}] Passage {p.passage_order}</div>
                            {p.text}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("Source document passages not found for this draft.")

            # Right Column: Claims & Evidence
            with col_rev_r:
                st.markdown(f"### 🔍 Factual Claims ({selected_draft.platform.upper()})")
                st.markdown(f"Current Review Status: **{selected_draft.review_status.upper()}**")

                if selected_draft.claims:
                    for claim in selected_draft.claims:
                        with st.container():
                            st.markdown(f"**Claim {claim.claim_label}:** \"{claim.claim_text}\"")
                            
                            # Evidence status badge
                            if claim.evidence_status == STATUS_EVIDENCE_LINKED:
                                st.markdown(f'<span class="badge badge-success">Status: {claim.evidence_status}</span>', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<span class="badge badge-danger">Status: {claim.evidence_status}</span>', unsafe_allow_html=True)

                            st.write(f"Referenced Passages: `{', '.join(claim.referenced_passage_ids)}`")
                            if claim.supporting_excerpt:
                                st.caption(f"Matched Excerpt: \"{claim.supporting_excerpt}\"")
                            
                            if claim.flag_reasons:
                                for f in claim.flag_reasons:
                                    st.error(f"Flagged: {f}")

                            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #f1f5f9;'/>", unsafe_allow_html=True)

                    st.markdown("### Human Editorial Decision")
                    rev_notes = st.text_input("Reviewer Notes / Justification", placeholder="e.g. Verified metrics match Q3 financial results.")
                    
                    c_app1, c_app2 = st.columns(2)
                    with c_app1:
                        if st.button("✅ Approve Content Draft", type="primary", use_container_width=True):
                            ok, msg = DatabaseManager.update_draft_status(
                                selected_draft.id,
                                "approved",
                                notes=rev_notes or "Approved by editor.",
                                actor="editor"
                            )
                            if ok:
                                st.success("Draft approved and logged to audit trail.")
                                st.rerun()
                    with c_app2:
                        if st.button("↩️ Reopen for Revision", use_container_width=True):
                            ok, msg = DatabaseManager.update_draft_status(
                                selected_draft.id,
                                "reopened",
                                notes=rev_notes or "Reopened for revision.",
                                actor="editor"
                            )
                            if ok:
                                st.info("Draft marked as REOPENED for revision.")
                                st.rerun()
                else:
                    st.info("No claims detected for this draft.")


# ==============================================================================
# 4. CONTENT LIBRARY PAGE
# ==============================================================================

elif "Content Library" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Content Library & Exports</h1>
        <p class="app-subtitle">Filter, edit, manage, and batch-export approved repurposed content assets.</p>
    </div>
    """, unsafe_allow_html=True)

    all_drafts = DatabaseManager.list_content_drafts()

    # Filter Bar
    c_f1, c_f2, c_f3 = st.columns(3)
    with c_f1:
        search_query = st.text_input("Search Drafts", placeholder="Search by hook or content...")
    with c_f2:
        platform_filter = st.selectbox("Filter Platform", ["All Platforms", "linkedin", "instagram", "video_script"])
    with c_f3:
        status_filter = st.selectbox("Filter Review Status", ["All Statuses", "draft", "in_review", "approved", "reopened"])

    # Apply filters
    filtered_drafts = all_drafts
    if platform_filter != "All Platforms":
        filtered_drafts = [d for d in filtered_drafts if d.platform == platform_filter]
    if status_filter != "All Statuses":
        filtered_drafts = [d for d in filtered_drafts if d.review_status == status_filter]
    if search_query.strip():
        q = search_query.strip().lower()
        filtered_drafts = [d for d in filtered_drafts if q in d.hook_title.lower() or q in d.primary_content.lower()]

    st.markdown(f"**Showing {len(filtered_drafts)} of {len(all_drafts)} drafts**")

    # Export Bar
    st.markdown("### Batch Export")
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        csv_data = ExportService.to_csv(filtered_drafts)
        st.download_button(
            label="📥 Export Filtered Drafts (CSV)",
            data=csv_data,
            file_name=f"sourcewise_drafts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_exp2:
        json_data = ExportService.to_json(filtered_drafts)
        st.download_button(
            label="📥 Export Filtered Drafts (JSON)",
            data=json_data,
            file_name=f"sourcewise_drafts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )

    st.markdown("---")

    # Render Draft Cards
    if not filtered_drafts:
        st.info("No drafts match your current filter settings.")
    else:
        for draft in filtered_drafts:
            with st.expander(f"{draft.platform.upper()} | {draft.hook_title} ({draft.review_status.upper()})"):
                st.markdown(f"**Status:** `{draft.review_status.upper()}` | **Mode:** `{draft.generation_mode.upper()}` | **Score:** `{draft.compliance_score}/100`")
                
                # Content editor with safe approval invalidation
                edited_text = st.text_area(
                    "Edit Draft Content",
                    value=draft.primary_content,
                    height=200,
                    key=f"lib_edit_{draft.id}"
                )

                col_lib1, col_lib2 = st.columns(2)
                with col_lib1:
                    if st.button("Save & Safe Re-Audit", key=f"lib_save_{draft.id}"):
                        if edited_text != draft.primary_content:
                            DatabaseManager.update_draft_content(draft.id, edited_text, reset_approval=True)
                            st.info("Draft content updated. Status reset to REOPENED for compliance safety.")
                            st.rerun()
                        else:
                            st.success("No changes made.")

                with col_lib2:
                    if st.button("🗑️ Delete Draft", key=f"lib_del_{draft.id}"):
                        DatabaseManager.delete_content_draft(draft.id)
                        st.warning("Draft deleted.")
                        st.rerun()


# ==============================================================================
# 5. BRAND SETTINGS PAGE
# ==============================================================================

elif "Brand Settings" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Brand Voice & Governance Settings</h1>
        <p class="app-subtitle">Configure multi-brand guidelines, forbidden terminology, mandatory disclaimers, and platform constraints.</p>
    </div>
    """, unsafe_allow_html=True)

    brands = DatabaseManager.list_brand_profiles()
    brand_map = {b.id: b.name for b in brands}
    
    selected_b_id = st.selectbox(
        "Select Brand Profile to Edit",
        options=list(brand_map.keys()),
        format_func=lambda x: brand_map[x]
    )

    current_b = DatabaseManager.get_brand_profile(selected_b_id) if selected_b_id else None
    if not current_b:
        current_b = BrandProfileSchema(**SAMPLE_BRAND_PROFILE)

    with st.form("brand_profile_form"):
        b_name = st.text_input("Brand Name*", value=current_b.name)
        b_audience = st.text_input("Target Audience", value=current_b.target_audience)
        b_tone = st.selectbox(
            "Tone of Voice",
            ["Professional", "Technical", "Authoritative", "Casual & Witty", "Direct & Concise"],
            index=["Professional", "Technical", "Authoritative", "Casual & Witty", "Direct & Concise"].index(current_b.tone_of_voice) if current_b.tone_of_voice in ["Professional", "Technical", "Authoritative", "Casual & Witty", "Direct & Concise"] else 0
        )

        b_pref = st.text_area(
            "Preferred Terminology (Comma-separated)",
            value=", ".join(current_b.preferred_terminology),
            help="Terms and phrases that the AI engine should prioritize using."
        )

        b_forbid = st.text_area(
            "Forbidden Terminology (Comma-separated)",
            value=", ".join(current_b.forbidden_terminology),
            help="Banned words, competitor names, or buzzwords that must NEVER appear in output."
        )

        b_cta = st.text_input("Default Call to Action (CTA)", value=current_b.primary_cta or "")
        b_disclaimer = st.text_area("Required Disclaimer", value=current_b.required_disclaimer or "")
        b_hashtags = st.text_input("Default Hashtags", value=current_b.hashtag_preferences or "")

        save_brand_btn = st.form_submit_button("💾 Save Brand Profile Settings", type="primary")

    if save_brand_btn:
        pref_list = [p.strip() for p in b_pref.split(",") if p.strip()]
        forbid_list = [f.strip() for f in b_forbid.split(",") if f.strip()]

        updated_brand = BrandProfileSchema(
            id=current_b.id,
            name=b_name,
            target_audience=b_audience,
            tone_of_voice=b_tone,
            preferred_terminology=pref_list,
            forbidden_terminology=forbid_list,
            primary_cta=b_cta,
            required_disclaimer=b_disclaimer,
            hashtag_preferences=b_hashtags,
            is_default=current_b.is_default
        )

        ok, msg = DatabaseManager.save_brand_profile(updated_brand)
        if ok:
            st.success("Brand profile saved successfully!")
            st.rerun()
        else:
            st.error(f"Failed to save brand profile: {msg}")


# ==============================================================================
# 6. ENGINE & SETTINGS PAGE
# ==============================================================================

elif "Engine & Settings" in selected_nav or "System" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <h1 class="app-title">Engine & Application Settings</h1>
        <p class="app-subtitle">Configure AI model credentials, inspect local SQLite database tables, and manage application preferences.</p>
    </div>
    """, unsafe_allow_html=True)

    # Section 1: Database Health & Diagnostics
    st.markdown("### 💾 Local Database Storage")
    is_cfg = is_database_configured()
    db_path = get_database_path()

    if is_cfg:
        ok_conn, conn_msg = DatabaseManager.check_connection()
        if ok_conn:
            st.success(f"**Database Status:** {conn_msg}")
        else:
            st.error(f"**Connection Error:** {conn_msg}")
    else:
        st.warning("Database persistence is disabled. Operating in Temporary Session Mode.")

    # SQLite Diagnostics
    st.markdown("#### Storage Diagnostics")
    c_diag1, c_diag2, c_diag3 = st.columns(3)
    engine = DatabaseManager.get_engine()
    table_count = 0
    fk_status_label = "Unknown"
    if engine:
        try:
            from sqlalchemy import inspect as sa_inspect
            inspector = sa_inspect(engine)
            tables = inspector.get_table_names()
            table_count = len(tables)
            with engine.connect() as conn:
                fk_val = conn.execute(text("PRAGMA foreign_keys")).scalar()
                fk_status_label = "Active (Enforced)" if fk_val == 1 else "Disabled"
        except Exception:
            pass

    with c_diag1:
        st.metric("Database Engine", "SQLite 3")
    with c_diag2:
        st.metric("Tables Initialized", f"{table_count} / 6")
    with c_diag3:
        st.metric("Foreign Key Cascades", fk_status_label)

    st.caption(f"📁 **Database File Path:** `{db_path if db_path else ':memory:'}`")

    # Cloud Ephemeral Storage Advisory Note
    st.info(
        "ℹ️ **Cloud Deployment Advisory (Streamlit Community Cloud):**\n\n"
        "SQLite writes to local disk (`data/sourcewise.db`). When deployed on **Streamlit Community Cloud**, "
        "the local filesystem is container-based. Any data saved to SQLite will persist during "
        "active user sessions, but will reset if the cloud container reboots, sleeps, or redeploys. "
        "For an offline, self-contained internship demonstration with zero paid infrastructure, SQLite provides complete reliability with no external network latency."
    )

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

    # Section 2: AI Provider Settings
    st.markdown("### ⚡ Google Gemini AI Configuration")
    gemini_active = is_gemini_configured()
    current_model = get_gemini_model()

    c_ai1, c_ai2 = st.columns(2)
    with c_ai1:
        st.metric("Configured Model", current_model)
    with c_ai2:
        key_status = "Configured (Protected)" if gemini_active else "Not Configured"
        st.metric("Gemini API Key", key_status)

    if gemini_active:
        st.success(f"Google Gemini AI is active using model `{current_model}`.")
    else:
        st.info("Operating in Demo Mode (deterministic rule-based generation).")

    with st.expander("📖 Instructions to Configure Gemini API"):
        st.markdown("""
        To enable real Gemini AI generation:
        1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/).
        2. In local development: Add to your local `.env` file:
           ```bash
           GEMINI_API_KEY="your-api-key-here"
           GEMINI_MODEL="gemini-2.5-flash"
           ```
        3. In Streamlit Community Cloud: Go to **App Settings** → **Secrets**, and add:
           ```toml
           GEMINI_API_KEY = "your-api-key-here"
           GEMINI_MODEL = "gemini-2.5-flash"
           ```
        """)

    st.markdown("---")
    st.markdown("### 🧹 Session Reset")
    if st.button("Clear Session State & Reload"):
        st.session_state.clear()
        st.success("Session state cleared.")
        st.rerun()
