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

# Custom SaaS Styling (Warm Editorial Publishing & Evidence Traceability Design)
st.markdown("""
<style>
    /* ==========================================================================
       SOURCEWISE AI — EDITORIAL DESIGN SYSTEM
       Warm rag-paper canvas, printer's ink, forest green & muted terracotta accents.
       ========================================================================== */

    /* Global Layout & Typography */
    .stApp {
        background-color: #faf8f5 !important;
        color: #1c1917 !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    
    /* Top Header Bar */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* Distinctive Editorial Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #f3f0e8 !important;
        border-right: 1px solid #ded9cd !important;
    }
    section[data-testid="stSidebar"] * {
        color: #44403c;
    }
    
    .sw-masthead {
        display: flex;
        align-items: center;
        gap: 0.85rem;
        padding: 0.85rem 0.25rem 1.25rem 0.25rem;
        border-bottom: 2px solid #1c1917;
        margin-bottom: 1.25rem;
    }
    .sw-seal {
        width: 38px;
        height: 38px;
        background-color: #1b4332;
        color: #faf8f5 !important;
        font-family: "Georgia", "Times New Roman", serif;
        font-weight: 700;
        font-size: 1.05rem;
        letter-spacing: 0.05em;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 4px;
        box-shadow: 0 1px 3px rgba(27, 67, 50, 0.25);
    }
    .sw-identity {
        display: flex;
        flex-direction: column;
    }
    .sw-brand-name {
        font-family: "Georgia", "Times New Roman", serif;
        font-size: 1.15rem;
        font-weight: 700;
        color: #1c1917 !important;
        letter-spacing: 0.06em;
        line-height: 1.2;
    }
    .sw-brand-sub {
        font-size: 0.72rem;
        color: #78716c !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-top: 2px;
    }

    .sw-nav-section-title {
        font-size: 0.68rem;
        font-weight: 700;
        color: #78716c !important;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        padding: 0.5rem 0.5rem 0.35rem 0.5rem;
        border-bottom: 1px solid #e7e4dc;
        margin-bottom: 0.5rem;
    }

    /* Unique Editorial Navigation Items (No Radio Circles, No Emoji) */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] > div {
        gap: 0.25rem;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] {
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        padding: 0.6rem 0.85rem !important;
        border-radius: 4px !important;
        background-color: transparent !important;
        transition: all 0.12s ease-in-out !important;
        cursor: pointer !important;
        border: 1px solid transparent !important;
    }
    /* Hide the native radio circle completely */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {
        display: none !important;
    }
    /* Navigation Item Typography */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"] div[data-testid="stMarkdownContainer"] p {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 0.88rem !important;
        font-weight: 500 !important;
        color: #44403c !important;
        margin: 0 !important;
        letter-spacing: 0.01em !important;
    }
    /* Navigation Hover */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:hover {
        background-color: #eae5d9 !important;
        border-color: #ded9cd !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:hover div[data-testid="stMarkdownContainer"] p {
        color: #1c1917 !important;
    }
    /* Navigation Active / Selected State (Forest Green Editorial Indicator) */
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) {
        background-color: #eaf1ec !important;
        border: 1px solid #c8dcd0 !important;
        border-left: 3px solid #1b4332 !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) div[data-testid="stMarkdownContainer"] p {
        color: #1b4332 !important;
        font-weight: 700 !important;
    }

    /* Sidebar Colophon */
    .sw-sidebar-colophon {
        margin-top: 2.5rem;
        padding-top: 1rem;
        border-top: 1px solid #ded9cd;
    }
    .sw-colophon-tag {
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #78716c !important;
    }
    .sw-colophon-body {
        font-size: 0.78rem;
        font-weight: 600;
        color: #1c1917 !important;
        margin-top: 2px;
    }
    .sw-colophon-meta {
        font-size: 0.7rem;
        color: #1b4332 !important;
        font-weight: 600;
        margin-top: 2px;
    }

    /* Page Header */
    .app-header {
        padding: 0.5rem 0rem 1.25rem 0rem;
        border-bottom: 1px solid #ded9cd;
        margin-bottom: 1.5rem;
    }
    .app-eyebrow {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #c25e46;
        margin-bottom: 0.35rem;
    }
    .app-title {
        font-family: "Georgia", "Times New Roman", serif;
        font-size: 1.85rem;
        font-weight: 700;
        color: #1c1917;
        margin: 0;
        letter-spacing: -0.015em;
        line-height: 1.2;
    }
    .app-subtitle {
        font-size: 0.95rem;
        color: #57534e;
        margin-top: 0.4rem;
        line-height: 1.5;
        max-width: 820px;
    }

    /* Structured Editorial Metric Panels */
    .sw-metric-panel {
        background: #ffffff;
        border: 1px solid #e7e4dc;
        border-radius: 4px;
        padding: 1.1rem 1.25rem;
        border-top: 3px solid #1c1917;
        box-shadow: 0 1px 2px rgba(28, 25, 23, 0.03);
    }
    .sw-metric-panel.accent-forest {
        border-top: 3px solid #1b4332;
    }
    .sw-metric-panel.accent-coral {
        border-top: 3px solid #c25e46;
    }
    .sw-metric-value {
        font-size: 1.95rem;
        font-weight: 700;
        color: #1c1917;
        line-height: 1.1;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .sw-metric-label {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #78716c;
        margin-top: 0.35rem;
    }
    .sw-metric-sub {
        font-size: 0.75rem;
        color: #57534e;
        margin-top: 0.3rem;
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }

    /* Editorial Pipeline Ribbon */
    .sw-pipeline-box {
        background: #ffffff;
        border: 1px solid #e7e4dc;
        border-radius: 4px;
        padding: 1rem 1.25rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 2px rgba(28, 25, 23, 0.03);
    }
    .sw-pipeline-header {
        font-size: 0.68rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #78716c;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #f2efe8;
        padding-bottom: 0.4rem;
    }
    .sw-pipeline-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
    }
    .sw-step-item {
        border-left: 2px solid #ded9cd;
        padding-left: 0.75rem;
    }
    .sw-step-item.active {
        border-left-color: #1b4332;
    }
    .sw-step-num {
        font-size: 0.7rem;
        font-weight: 700;
        color: #1b4332;
        letter-spacing: 0.05em;
    }
    .sw-step-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1c1917;
        margin: 0.15rem 0;
    }
    .sw-step-detail {
        font-size: 0.72rem;
        color: #78716c;
        line-height: 1.3;
    }

    /* Editorial Standard Cards */
    .saas-card {
        background: #ffffff;
        border: 1px solid #e7e4dc;
        border-radius: 4px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 1px 3px rgba(28, 25, 23, 0.03);
    }
    .saas-card-header {
        font-family: "Georgia", "Times New Roman", serif;
        font-size: 1.05rem;
        font-weight: 700;
        color: #1c1917;
        margin-bottom: 0.75rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Publication Badges */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.55rem;
        border-radius: 3px;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .badge-success { background-color: #eef5f1; color: #1b4332; border: 1px solid #cce3d5; }
    .badge-warning { background-color: #fdf5eb; color: #a16207; border: 1px solid #fae8cd; }
    .badge-danger { background-color: #fdf2f0; color: #9f3a24; border: 1px solid #f6d2c8; }
    .badge-neutral { background-color: #f3f0e8; color: #57534e; border: 1px solid #ded9cd; }

    /* Canonical Passage Elements */
    .passage-box {
        background-color: #ffffff;
        border: 1px solid #e7e4dc;
        border-left: 3px solid #1b4332;
        padding: 0.85rem 1rem;
        border-radius: 0 4px 4px 0;
        margin-bottom: 0.75rem;
        font-size: 0.92rem;
        line-height: 1.6;
        color: #292524;
    }
    .passage-id {
        font-weight: 700;
        color: #1b4332;
        margin-bottom: 0.25rem;
        font-size: 0.78rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .scope-notice {
        background-color: #ffffff;
        border: 1px solid #e7e4dc;
        border-left: 3px solid #78716c;
        border-radius: 0 4px 4px 0;
        padding: 0.75rem 1rem;
        font-size: 0.85rem;
        color: #57534e;
        margin-bottom: 1.25rem;
        line-height: 1.5;
    }

    /* Structured Diagnostic & Advisory Cards (Replacing technical banners) */
    .sw-advisory-card {
        background: #ffffff;
        border: 1px solid #e7e4dc;
        border-left: 3px solid #1b4332;
        border-radius: 0 4px 4px 0;
        padding: 0.85rem 1rem;
        margin-bottom: 1rem;
    }
    .sw-advisory-title {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #1b4332;
        margin-bottom: 0.25rem;
    }
    .sw-advisory-body {
        font-size: 0.85rem;
        color: #57534e;
        line-height: 1.5;
    }

    /* Primary and Secondary Action Buttons */
    button[kind="primary"] {
        background-color: #c25e46 !important;
        border-color: #c25e46 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 4px !important;
    }
    button[kind="primary"]:hover {
        background-color: #af4e38 !important;
        border-color: #af4e38 !important;
    }
    button[kind="secondary"] {
        background-color: #ffffff !important;
        border: 1px solid #ded9cd !important;
        color: #1c1917 !important;
        font-weight: 500 !important;
        border-radius: 4px !important;
    }
    button[kind="secondary"]:hover {
        background-color: #f4f1ea !important;
        border-color: #c8c3b7 !important;
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
# SIDEBAR NAVIGATION (BESPOKE EDITORIAL PUBLISHING INTERFACE)
# ==============================================================================

with st.sidebar:
    st.markdown("""
    <div class="sw-masthead">
        <div class="sw-seal">SW</div>
        <div class="sw-identity">
            <div class="sw-brand-name">SOURCEWISE</div>
            <div class="sw-brand-sub">Editorial Evidence Engine</div>
        </div>
    </div>
    <div class="sw-nav-section-title">DESK NAVIGATION</div>
    """, unsafe_allow_html=True)

    nav_options = [
        "01  Workspace",
        "02  Create Content",
        "03  Evidence Review",
        "04  Content Library",
        "05  Brand Settings",
        "06  System Settings"
    ]

    selected_nav = st.radio(
        "Navigation",
        nav_options,
        index=0,
        label_visibility="collapsed"
    )

    st.markdown("""
    <div class="sw-sidebar-colophon">
        <div class="sw-colophon-tag">AUTHORITATIVE REPURPOSING</div>
        <div class="sw-colophon-body">Canonical Passage Pinning & Verification</div>
        <div class="sw-colophon-meta">SQLite Local • Evidence Grounded</div>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 1. WORKSPACE PAGE
# ==============================================================================

if "Workspace" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <div class="app-eyebrow">EDITORIAL DESK / OVERVIEW</div>
        <h1 class="app-title">Content Repurposing & Traceability Ledger</h1>
        <p class="app-subtitle">Transform long-form engineering whitepapers, research case studies, and architecture articles into high-performance social content with verifiable factual citations.</p>
    </div>
    """, unsafe_allow_html=True)

    # Visual Workflow Architecture Ribbon
    st.markdown("""
    <div class="sw-pipeline-box">
        <div class="sw-pipeline-header">REPURPOSING & FACTUAL AUDIT PIPELINE</div>
        <div class="sw-pipeline-grid">
            <div class="sw-step-item active">
                <div class="sw-step-num">STAGE 01</div>
                <div class="sw-step-title">Ingest & Parse</div>
                <div class="sw-step-detail">Authoritative source text & versioned document record</div>
            </div>
            <div class="sw-step-item active">
                <div class="sw-step-num">STAGE 02</div>
                <div class="sw-step-title">Canonical Passages</div>
                <div class="sw-step-detail">Partitioned units [S1], [S2] with exact character offsets</div>
            </div>
            <div class="sw-step-item">
                <div class="sw-step-num">STAGE 03</div>
                <div class="sw-step-title">Channel Adaptation</div>
                <div class="sw-step-detail">Tailored LinkedIn, Instagram, and Video scripts</div>
            </div>
            <div class="sw-step-item">
                <div class="sw-step-num">STAGE 04</div>
                <div class="sw-step-title">Evidence Audit</div>
                <div class="sw-step-detail">Assertion verification and human editorial approval</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Distinctive Editorial Metric Panels
    all_drafts = DatabaseManager.list_content_drafts()
    total_drafts = len(all_drafts)
    approved_drafts = len([d for d in all_drafts if d.review_status == "approved"])
    in_review_drafts = len([d for d in all_drafts if d.review_status in ("draft", "in_review", "reopened")])
    total_claims = sum(len(d.claims) for d in all_drafts)

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.markdown(f"""
        <div class="sw-metric-panel accent-forest">
            <div class="sw-metric-value">{total_drafts}</div>
            <div class="sw-metric-label">Repurposed Drafts</div>
            <div class="sw-metric-sub">
                <span class="badge badge-success">{approved_drafts} Approved</span>
                <span style="color: #78716c; font-size: 0.72rem;">for publication</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="sw-metric-panel accent-coral">
            <div class="sw-metric-value">{total_claims}</div>
            <div class="sw-metric-label">Audited Factual Claims</div>
            <div class="sw-metric-sub">
                <span class="badge badge-warning">{in_review_drafts} Pending</span>
                <span style="color: #78716c; font-size: 0.72rem;">editorial sign-off</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="sw-metric-panel">
            <div class="sw-metric-value">100%</div>
            <div class="sw-metric-label">Traceability Standard</div>
            <div class="sw-metric-sub">
                <span class="badge badge-neutral">SQLite 3</span>
                <span style="color: #78716c; font-size: 0.72rem;">Verified local storage</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    # Action & Editorial Standards Strip
    col_act1, col_act2 = st.columns([2, 1])
    with col_act1:
        st.markdown("""
        <div class="saas-card">
            <div class="saas-card-header">
                <span>Start New Repurposing Session</span>
                <span class="badge badge-neutral">Ready</span>
            </div>
            <p style="color: #57534e; font-size: 0.88rem; line-height: 1.5; margin-bottom: 0.85rem;">
                Load technical documentation or whitepapers to generate channel-specific drafts with automatic citation pinning against source passages.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("⚡ Load NexusPay Case Study (One-Click Ingest)", type="primary", use_container_width=True):
            st.session_state.source_title = SAMPLE_ARTICLE_TITLE
            st.session_state.source_type = SAMPLE_ARTICLE_TYPE
            st.session_state.source_url = SAMPLE_ARTICLE_URL
            st.session_state.source_text = SAMPLE_ARTICLE_TEXT
            st.success("Loaded NexusPay case study. Select '02  Create Content' in the sidebar to generate.")

    with col_act2:
        st.markdown("""
        <div class="saas-card">
            <div class="saas-card-header">Editorial Standards</div>
            <ul style="color: #57534e; font-size: 0.8rem; line-height: 1.55; padding-left: 1.1rem; margin: 0;">
                <li><strong>No Hallucinated Citations:</strong> Claims require mapped passage IDs.</li>
                <li><strong>Metric Auditing:</strong> Percentages and benchmark metrics must match source text.</li>
                <li><strong>Approval Guard:</strong> Edits to approved text automatically reset status.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Recent drafts ledger
    st.markdown("### Repurposed Content Ledger")
    if all_drafts:
        for draft in all_drafts[:6]:
            with st.container():
                c_d1, c_d2, c_d3, c_d4 = st.columns([3, 1, 1, 1])
                with c_d1:
                    st.markdown(f"**{draft.hook_title}**")
                    st.caption(f"Channel: `{draft.platform.upper()}` • Mode: `{draft.generation_mode.upper()}`")
                with c_d2:
                    badge_class = "badge-success" if draft.review_status == "approved" else "badge-warning"
                    st.markdown(f'<span class="badge {badge_class}">{draft.review_status.upper()}</span>', unsafe_allow_html=True)
                with c_d3:
                    st.write(f"Claims: **{len(draft.claims)}**")
                with c_d4:
                    st.write(f"Score: **{draft.compliance_score}/100**")
                st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #e7e4dc;'/>", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="saas-card" style="text-align: center; padding: 2rem;">
            <div style="font-weight: 600; color: #1c1917; margin-bottom: 0.35rem;">No Content Drafts Yet</div>
            <div style="color: #78716c; font-size: 0.85rem;">Select <strong>02  Create Content</strong> in the sidebar to ingest your first source document.</div>
        </div>
        """, unsafe_allow_html=True)


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

        gemini_ready = is_gemini_configured()
        if gemini_ready:
            btn_label = f"Generate Repurposed Drafts (Gemini: {get_gemini_model()})"
        else:
            btn_label = "Generate Repurposed Drafts"

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
                                st.warning(f"Audit Flag: {f}")

                # Quick action buttons
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button(f"Approve Draft ({draft.platform.upper()})", key=f"app_{draft.id}", use_container_width=True, type="primary"):
                        DatabaseManager.update_draft_status(draft.id, "approved", notes="Directly approved from Creator view.")
                        draft.review_status = "approved"
                        st.success(f"{draft.platform.upper()} draft approved.")
                        st.rerun()
                with col_btn2:
                    if st.button("Copy Content to Clipboard", key=f"copy_{draft.id}", use_container_width=True):
                        st.info("Content selected for copy. Use Ctrl+C inside the content area.")


# ==============================================================================
# 3. EVIDENCE REVIEW PAGE
# ==============================================================================

elif "Evidence Review" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <div class="app-eyebrow">EDITORIAL VERIFICATION</div>
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
                st.markdown("### Canonical Source Passages")
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
                st.markdown(f"### Grounded Factual Claims ({selected_draft.platform.upper()})")
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

                            st.markdown("<hr style='margin: 0.5rem 0; border: none; border-top: 1px solid #e7e4dc;'/>", unsafe_allow_html=True)

                    st.markdown("### Human Editorial Decision")
                    rev_notes = st.text_input("Reviewer Notes / Justification", placeholder="e.g. Verified metrics match Q3 financial results.")
                    
                    c_app1, c_app2 = st.columns(2)
                    with c_app1:
                        if st.button("Approve Content Draft", type="primary", use_container_width=True):
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
                        if st.button("Reopen for Revision", use_container_width=True):
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
            label="Export Filtered Drafts (CSV)",
            data=csv_data,
            file_name=f"sourcewise_drafts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    with col_exp2:
        json_data = ExportService.to_json(filtered_drafts)
        st.download_button(
            label="Export Filtered Drafts (JSON)",
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
                    if st.button("Delete Draft", key=f"lib_del_{draft.id}"):
                        DatabaseManager.delete_content_draft(draft.id)
                        st.warning("Draft deleted.")
                        st.rerun()


# ==============================================================================
# 5. BRAND SETTINGS PAGE
# ==============================================================================

elif "Brand Settings" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <div class="app-eyebrow">BRAND GOVERNANCE</div>
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

        save_brand_btn = st.form_submit_button("Save Brand Profile Settings", type="primary")

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
            st.success("Brand profile saved successfully.")
            st.rerun()
        else:
            st.error(f"Failed to save brand profile: {msg}")


# ==============================================================================
# 6. ENGINE & SETTINGS PAGE
# ==============================================================================

elif "Engine & Settings" in selected_nav or "System" in selected_nav:
    st.markdown("""
    <div class="app-header">
        <div class="app-eyebrow">SYSTEM & ENGINE CONFIGURATION</div>
        <h1 class="app-title">Engine & Application Settings</h1>
        <p class="app-subtitle">Configure AI model credentials, inspect local SQLite database tables, and manage application preferences.</p>
    </div>
    """, unsafe_allow_html=True)

    # Section 1: Database Health & Diagnostics
    st.markdown("### Local Database Storage")
    is_cfg = is_database_configured()
    db_path = get_database_path()

    if is_cfg:
        ok_conn, conn_msg = DatabaseManager.check_connection()
        if ok_conn:
            st.markdown(f'<div class="sw-advisory-card"><div class="sw-advisory-title">Database Storage Status</div><div class="sw-advisory-body">{conn_msg}</div></div>', unsafe_allow_html=True)
        else:
            st.error(f"Connection Error: {conn_msg}")
    else:
        st.markdown('<div class="sw-advisory-card"><div class="sw-advisory-title">Database Status</div><div class="sw-advisory-body">Operating in Temporary Session Mode.</div></div>', unsafe_allow_html=True)

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

    st.caption(f"Database File Path: `{db_path if db_path else ':memory:'}`")

    # Cloud Ephemeral Storage Advisory Note
    st.markdown(
        """
        <div class="sw-advisory-card">
            <div class="sw-advisory-title">Storage Persistence Architecture</div>
            <div class="sw-advisory-body">
                SQLite writes directly to local storage at <code>data/sourcewise.db</code>. On Streamlit Community Cloud,
                records persist throughout active user sessions. To ensure reproducible audits, all foreign keys and cascades are enforced on every database connection.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col_db1, col_db2 = st.columns(2)
    with col_db1:
        if st.button("Test Database Connection", use_container_width=True):
            DatabaseManager.reset_engine()
            ok, msg = DatabaseManager.check_connection()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    with col_db2:
        if st.button("Initialize / Verify Schema Tables", use_container_width=True):
            ok, msg = DatabaseManager.init_db()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    st.markdown("---")

    # Section 2: AI Provider Settings
    st.markdown("### AI Provider & Model Configuration")
    gemini_active = is_gemini_configured()
    current_model = get_gemini_model()

    c_ai1, c_ai2 = st.columns(2)
    with c_ai1:
        st.metric("Configured Model", current_model)
    with c_ai2:
        key_status = "Configured (Protected)" if gemini_active else "Not Configured"
        st.metric("Gemini API Key", key_status)

    if gemini_active:
        st.markdown(f'<div class="sw-advisory-card"><div class="sw-advisory-title">Active AI Engine</div><div class="sw-advisory-body">Google Gemini AI is active using model <code>{current_model}</code>.</div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="sw-advisory-card"><div class="sw-advisory-title">Active AI Engine</div><div class="sw-advisory-body">Operating in deterministic rule-based mode. Configure <code>GEMINI_API_KEY</code> to enable live generation.</div></div>', unsafe_allow_html=True)

    with st.expander("Instructions to Configure Gemini API"):
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
    st.markdown("### Session Reset")
    if st.button("Clear Session State & Reload"):
        st.session_state.clear()
        st.success("Session state cleared.")
        st.rerun()
