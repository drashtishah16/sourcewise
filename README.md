# SourceWise AI — AI-Powered Social Content Repurposing and Evidence Traceability

[![Live Application](https://img.shields.io/badge/Live%20Application-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://sourcewise-966dabijbokkjrawyhg9t.streamlit.app)
[![Test Suite](https://img.shields.io/badge/pytest-41%20passed-success)](tests/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-red)](https://streamlit.io)
[![Database](https://img.shields.io/badge/Database-SQLite%203-blue)](https://sqlite.org)
[![AI Engine](https://img.shields.io/badge/AI%20Engine-Google%20Gemini%20Flash-orange)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

> 🚀 **Live Production Deployment**: [https://sourcewise-966dabijbokkjrawyhg9t.streamlit.app](https://sourcewise-966dabijbokkjrawyhg9t.streamlit.app)

SourceWise AI is an enterprise-grade technical content repurposing system designed to transform long-form whitepapers, architecture case studies, and engineering blog posts into high-performing social drafts for **LinkedIn**, **Instagram**, and **Short-form Video Scripts (TikTok / Reels / Shorts)** using **Google Gemini AI** (`gemini-2.5-flash`).

Unlike typical conversational AI chatbots that fabricate assertions and hallucinate statistics, SourceWise AI is built around a rigorous **Evidence Traceability Engine**. Every factual assertion in an output draft is pinned to immutable, canonical source passages (`[S1]`, `[S2]`, `[S3]...`), validated against the source text, audited for ungrounded numbers/percentages/dates, and subjected to independent human editorial review before approval.

---

## 🌟 Key Differentiators

| Feature | Standard LLM Chatbots | SourceWise AI |
| :--- | :--- | :--- |
| **Factual Grounding** | Plausible hallucinations, fabricated citations | Canonical passage mapping (`S1`, `S2`, `S3...`) with exact character offsets |
| **Metric Verification** | Invented percentages, altered benchmarks | Automated detection of unverified numbers, percentages, dates, and quotes |
| **AI Engine** | Generic prompts with hallucinated citations | **Google Gemini AI (`google-genai` SDK)** with strict JSON schema and evidence constraints |
| **API Key Flexibility** | Fails or blocks without paid API tokens | **100% Functional Demo Mode** fallback when API keys are unconfigured |
| **Brand Governance** | Generic unstructured prompts | Algorithmic enforcement of banned terms, preferred vocabulary, CTAs, and disclaimers |
| **Approval Integrity** | Fleeting session chat history | Audited state machine (`draft` → `in_review` → `approved` → `reopened`) in SQLite |
| **Edit Safety** | Editing retains false verified status | Editing approved content **automatically resets approval status** to `reopened` |
| **UI Experience** | Cluttered status banners and raw debug info | **Clean modern SaaS interface** with quiet inline feedback and zero credential leakage |

---

## 🏗️ Architecture & Module Structure

```text
sourcewise-ai/
├── .env.example               # Sanitized template for environment variables & secrets
├── .gitignore                  # Strict exclusion of virtualenvs, secrets, data/, and logs
├── README.md                   # Comprehensive architectural and operator documentation
├── INTERVIEW_GUIDE.md          # Technical assessment design rationale and defense
├── requirements.txt            # Production dependencies (Streamlit, SQLAlchemy, google-genai)
├── schema.sql                  # SQLite DDL schema with constraints, FKs, and indices
├── app.py                      # Main 6-view Streamlit SaaS web application
├── data/                       # Local SQLite database storage (data/sourcewise.db, gitignored)
├── scripts/
│   └── db_setup.py             # Diagnostic tool: verifies schema, 6 tables, FKs & CRUD lifecycle
├── src/
│   ├── __init__.py             # Package marker
│   ├── config.py               # Safe environment & secrets retrieval (no credential leakage)
│   ├── models.py               # Pydantic validation schemas & SQLAlchemy ORM models
│   ├── source_processor.py     # Source text segmentation, passage labeling, injection defense
│   ├── evidence_engine.py      # Core evidence auditor, metric verification, status labeling
│   ├── brand_engine.py         # Brand voice compliance, forbidden terms, length checks
│   ├── generator.py            # AI Generation coordinator & deterministic DemoGenerator
│   ├── gemini_service.py       # Google Gemini SDK service with structured JSON & citation rules
│   ├── database.py             # SQLite manager with foreign key cascades & session fallback
│   ├── export_service.py       # RFC 4180 CSV & structured JSON export generation
│   └── sample_data.py          # Pre-configured fictional case study & default brand profile
└── tests/
    ├── __init__.py             # Test suite package
    ├── conftest.py             # Shared pytest fixture ensuring isolated test databases
    ├── test_source_processor.py# Tests for segmentation, empty inputs, limits, versioning
    ├── test_evidence_engine.py # Tests for passage IDs, unverified numbers, quotes, dates
    ├── test_brand_engine.py    # Tests for brand rules, CTAs, disclaimers, length limits
    ├── test_generator.py       # Tests for Demo & Gemini AI generation, error masking, live calls
    ├── test_database.py        # Tests for SQLite CRUD, foreign keys, resets, persistence
    ├── test_exports.py         # Tests for CSV/JSON formatting, Unicode, credential safety
    └── test_app_smoke.py       # End-to-end integration pipeline smoke test
```

---

## 🚀 Core Product Workflows

The application interface follows a modern, accessible SaaS aesthetic:

1. **🏠 Workspace**: Executive dashboard with high-level metrics (Total Drafts, Approved Content, Pending Reviews, Verified Claims), honest live system status badges (SQLite Connected vs Session Memory; Demo Mode vs Connected LLM), and quick draft actions.
2. **✨ Create Content**: Multi-channel generation studio. Allows one-click loading of the fictional NexusPay architecture case study, passage segmentation, channel selection (LinkedIn, Instagram, Video), and instant generation with brand compliance scoring.
3. **🔬 Evidence Review**: Deep-dive verification workbench. Inspects source passages side-by-side with extracted claims, flags unverified percentages or quotes, displays supporting excerpts, records reviewer notes, and captures human approval decisions.
4. **📚 Content Library**: Central repository of all drafts with full-text search, platform and review status filters, inline editors (which safely reset approval state upon modification), and batch CSV / JSON export downloads.
5. **🎯 Brand Settings**: Brand profile management for multiple target personas. Configures preferred terminology, banned/forbidden phrases, mandatory disclaimers, default CTAs, and platform length thresholds.
6. **⚙️ System Settings**: Infrastructure diagnostics dashboard. Displays local SQLite file path, table counts, active foreign key cascade status, AI model availability, and Streamlit Community Cloud storage advisory.

---

## 🛡️ AI Safety, Injection Defense, and Brand Governance

### 1. Untrusted Source Text Isolation
Source text is treated strictly as untrusted user payload. The `SourceProcessor` sanitizes input, normalizes whitespace, and scans for instruction-override patterns (e.g. `ignore all previous instructions`, `SYSTEM PROMPT:`, `you are now in developer mode`). These patterns are flagged and neutralized—source content can never alter application logic or brand boundaries.

### 2. Hallucination Prevention
SourceWise AI's deterministic engine and evidence auditor explicitly detect and flag unsupported:
- **Numbers and Percentages**: Detects metrics in claims (e.g., `42%`, `820ms`, `$18,500`) and cross-references them against cited passages.
- **Dates & Quarters**: Detects temporal assertions (e.g., `Q3 2025`, `October 2025`) and validates presence in source text.
- **Direct Quotations**: Verifies that quotes attributed to individuals exist verbatim in the source material.
- **Passage ID Existence**: Rejects hallucinated passage references (e.g. referencing `S99` when only `S1`–`S4` exist).

### 3. Clear Epistemic Scope
A prominent notice in the application clarifies:
> *"Evidence Traceability Notice: SourceWise AI audits whether factual assertions directly reflect the provided source text passages. A 'Evidence Linked' status confirms textual alignment with the provided document; it does not independently certify external real-world truth."*

---

## 💾 SQLite Persistent Storage & Schema

SourceWise AI uses Python's standard library `sqlite3` driver interfaced through SQLAlchemy 2.0. By default, it automatically stores all application data in a local database file: `data/sourcewise.db` (created automatically on startup and gitignored).

Foreign key enforcement is strictly enabled on every connection via `PRAGMA foreign_keys = ON`, guaranteeing cascade deletions and preventing orphan records.

### Database Tables:
- `brand_profiles`: Multi-brand guidelines, banned words, disclaimers, CTAs.
- `source_documents`: Authoritative raw text, word counts, passage counts, version numbers.
- `source_passages`: Immutable numbered passages (`S1`, `S2`...) with character offsets and cascade deletion.
- `content_drafts`: Repurposed drafts, hooks, scripts, approval states, and compliance scores.
- `claim_evidence`: Claim text, cited passage IDs, excerpts, evidence statuses, and flag reasons.
- `review_events`: Complete immutable audit log of status changes (`draft` → `approved`) and notes.

### Transparent Fallback:
If database access is disabled (e.g. `DISABLE_DATABASE=true`), SourceWise AI gracefully falls back to **Temporary Session Mode** using an in-memory repository. It clearly warns the user that records will not persist across browser sessions and **never fabricates a successful database write**.

---

## 💻 Local Installation & Setup

### Prerequisites
- Python 3.11 or compatible version (e.g. 3.14)
- Git

### 1. Clone & Set Up Virtual Environment
```bash
git clone https://github.com/drashtishah16/sourcewise.git
cd sourcewise

# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Or on Linux / macOS:
# source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
*(No external PostgreSQL drivers, binary wheels, or database services required).*

### 3. Verify Database Schema & CRUD
```bash
python scripts/db_setup.py
```
Safely validates the SQLite database, verifies all 6 required tables, and tests the Insert -> Read -> Update -> Cleanup lifecycle.

### 4. Run Automated Tests
```bash
pytest -v
```
All 38 automated tests run locally in seconds without requiring network access, API keys, or pre-existing database tables.

### 5. Start the Streamlit Application
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 🧪 Automated Test Suite Breakdown

SourceWise AI includes 42 comprehensive automated unit and integration tests covering every core capability:

| Test Module | Coverage Scope | Tests |
| :--- | :--- | :---: |
| [`test_source_processor.py`](tests/test_source_processor.py) | Empty/whitespace inputs, minimum/maximum limits, passage splitting, sequential IDs (`S1`, `S2`), version incrementing on change, prompt injection defense | 6 |
| [`test_evidence_engine.py`](tests/test_evidence_engine.py) | Valid passage linking, invalid passage ID rejection, unsupported metrics/percentages, unverified dates, fabricated quotes, missing citations, sentence classifier, disclaimer notice | 8 |
| [`test_brand_engine.py`](tests/test_brand_engine.py) | Forbidden terminology detection, preferred term check, mandatory disclaimer presence, CTA verification, platform length limits, compliance scoring | 6 |
| [`test_generator.py`](tests/test_generator.py) | Demo generation across platforms, formatting rules, deterministic output, safe fallback, Gemini mock generation with JSON schema & claim audit, error sanitation, live API skip guard | 8 |
| [`test_database.py`](tests/test_database.py) | Default SQLite configuration, session fallback, brand CRUD, credential masking, source/passage hierarchy, approval reset on edit, review event auditing, SQLite foreign key cascades, and disk file persistence across engine reconnections | 9 |
| [`test_exports.py`](tests/test_exports.py) | RFC 4180 CSV escaping, structured JSON schema, Unicode/quotes/newlines handling, empty collections, credential leak prevention | 4 |
| [`test_app_smoke.py`](tests/test_app_smoke.py) | End-to-end integration test: Source Input → Passage Extraction → Demo Generation → Evidence Audit → Brand Check → Storage → Approval → CSV/JSON Export | 1 |
| **Total** | **All 41 Automated Tests Passing (1 Live API Skip Guard)** | **42** |

---

## ☁️ Streamlit Community Cloud Deployment

To deploy SourceWise AI to Streamlit Community Cloud:

1. Push this repository to GitHub (e.g., `https://github.com/drashtishah16/sourcewise.git`).
2. Log into [share.streamlit.io](https://share.streamlit.io).
3. Click **New app**, select your repository (`drashtishah16/sourcewise`), branch (`main`), and set the main file path to `app.py`.
4. (Optional) In **Advanced Settings** → **Secrets**, add your Gemini credentials:
   ```toml
   GEMINI_API_KEY = "your-google-ai-studio-api-key"
   GEMINI_MODEL = "gemini-2.5-flash"
   ```
5. Click **Deploy**. The application boots cleanly with zero external database configuration!

> [!WARNING]
> **Cloud Ephemeral Disk Storage Advisory**:
> When running on **Streamlit Community Cloud**, SQLite writes to the cloud container's local disk (`data/sourcewise.db`). Data saved during an active session is persisted across page navigations, but Streamlit Community Cloud containers are ephemeral. If the cloud app reboots, sleeps, or is redeployed, the local SQLite database resets. For an offline, self-contained internship demonstration with zero paid infrastructure, this is the optimal and recommended design.

---

## 📖 Sample Source Material (Fictional)

The application includes pre-loaded sample data clearly marked as fictional:
- **Title**: *Fictional Case Study: How NexusPay Cut PostgreSQL Query Latency by 42% Using Multi-Tier Caching*
- **Context**: Fictional fintech platform processing 12M micro-transactions faced 820ms p99 latency during Q3 2025. Deployed Redis and edge caching in October 2025.
- **Results**: Measured 42% latency reduction (820ms to 475ms), 44% CPU utilization, and $18,500/month infrastructure savings, validated with quoted statements from VP Elena Rostova.

---

## 📄 License

This project is developed as part of the internship assessment requirements. Licensed under the MIT License.

