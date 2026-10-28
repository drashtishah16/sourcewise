# SourceWise AI — Internship Assessment Interview & Architecture Defense Guide

This guide prepares you to explain and defend every design decision, algorithmic trade-off, and architectural pattern implemented in **SourceWise AI**.

---

## 1. Why Source Evidence Is Stored Separately

### Problem
In standard LLM applications, content and references are merged into a single unstructured string (e.g. *"NexusPay reduced latency by 42% (source: blog post)"*). If the source text is edited or updated, these embedded references silently break or become obsolete. Furthermore, there is no way for automated compliance systems to query, audit, or trace which specific sentence supported which output assertion.

### Solution
SourceWise AI implements a **normalized relational evidence schema**:
1. Raw source documents are ingested into `source_documents`.
2. Text is deterministically segmented into immutable `source_passages` (`S1`, `S2`, `S3...`) with exact start and end character offsets.
3. Every factual claim is stored in `claim_evidence` as an independent entity linking the `draft_id`, the specific `referenced_passage_ids`, and the exact textual excerpt.
4. If a source document is edited, the `SourceProcessor` increments the document version (`version = version + 1`). Existing drafts and claims remain bound to their specific source version, preventing "silent drift" where citations point to obsolete or shifted text.

---

## 2. How Passage IDs Are Validated

### Verification Pipeline
When a draft is generated or reviewed:
1. The `EvidenceAuditor` collects all passage IDs referenced in the draft (e.g. `['S1', 'S2']`).
2. It fetches the active document's passage registry (`passages_map`).
3. **Rejection of Phantom IDs**: If a claim references an ID that does not exist in the source document (e.g. `S99`), the claim is immediately flagged with `Referenced passage ID(s) S99 do not exist in source document` and assigned the status `Potentially Unsupported`.
4. **Content-Level Audit**: If the passage IDs exist, the engine extracts numerical quantities, percentages, dates, and direct quotations from both the claim and the passage text. If a claim asserts `"85% latency reduction"` but passage `S2` only contains `"42% reduction"`, the metric mismatch is immediately flagged.

---

## 3. How Deterministic Checks Differ from LLM Judgments

| Criterion | Deterministic Rules (SourceWise AI) | LLM Judgments |
| :--- | :--- | :--- |
| **Reproducibility** | 100% deterministic; same input always yields identical audit flags | Non-deterministic; temperature and token sampling can produce varied results |
| **Speed & Cost** | Sub-millisecond execution; zero API token costs | High latency (1–5 seconds per call); recurring monetary cost per token |
| **Auditability** | Explicit rule logic (regex, token intersection, character offset matching) | Opaque "black box" attention weights |
| **Hallucination Risk** | Impossible to invent citations or numbers | Prone to plausible-sounding confabulations |
| **Appropriate Use** | Factual consistency checks, metric verification, forbidden terms | Nuanced semantic comprehension, creative phrasing, voice adaptation |

SourceWise AI uses deterministic rules for **grounding and verification**, ensuring that compliance checks cannot hallucinate.

---

## 4. How Demo Mode Works Without an API Key

To ensure the internship assessment project is 100% testable, gradeable, and deployable without forcing the user to purchase API keys:
1. `DemoGenerator` acts as a deterministic content transformation engine.
2. It segments the incoming source text, selects key information-dense sentences across problem context, technical implementation, and measured outcomes, and adapts them into platform-tailored structures:
   - **LinkedIn**: Executive summary, structured bullet points citing `[S1]` and `[S2]`, professional CTA, and technical hashtags.
   - **Instagram**: High-energy opening hook, mobile-formatted bullet takeaways, visual swipe CTA, and curated hashtag block.
   - **Video Script**: Structured 60-second retention script with timestamped pacing (`[0:00 - 0:05 | Hook]`, `[0:05 - 0:20 | Context]`, `[0:20 - 0:40 | Mechanism]`, `[0:40 - 0:55 | Result]`), audio narration cues, and visual direction overlays.
3. The UI clearly labels output with `Demo Mode — No AI API Required` to maintain complete transparency.
4. `LLMProviderInterface` provides a clean plug-in interface for external providers (OpenAI, Gemini, Anthropic) if credentials are added later.

---

## 5. How SQLite Persistence Works & Graceful Fallback

### Persistent Storage
- By default, SourceWise AI uses a local SQLite database (`data/sourcewise.db`) via Python's built-in `sqlite3` driver and SQLAlchemy 2.0 ORM.
- **Foreign Key Enforcement**: SQLite turns off foreign keys by default. SourceWise AI attaches a connection event listener (`PRAGMA foreign_keys = ON`) ensuring foreign keys and cascade deletions (`ON DELETE CASCADE`) are strictly enforced on every connection.
- Operations are fully parameterized to eliminate SQL injection risks.
- Relations feature cascade deletes (`ON DELETE CASCADE`), ensuring that deleting a source document cleanly purges associated passages, drafts, and evidence claims without leaving orphan records.

### Graceful Fallback Mode
- If database persistence is disabled (`DISABLE_DATABASE=true`), `DatabaseManager` transparently operates through `InMemoryStore`.
- Crucially, `DatabaseManager.is_persistent()` returns `False`. The UI displays a warning badge stating: `Session Memory (Unpersisted)`.
- The application **never fabricates a successful database write**—if persistence is unavailable, the user is honestly informed that records will last only for the current session.

### Cloud Deployment Storage Trade-off
- On **Streamlit Community Cloud**, apps run in containerized environments with ephemeral storage. SQLite provides zero-latency, zero-cost, self-contained persistence while the container is alive, but resets when the container sleeps or restarts. In an assessment or portfolio setting, this removes third-party database dependency risks and network latency without compromising real relational querying.

---

## 6. How Secrets Are Protected

1. **Zero Committed Secrets**: `.env`, `secrets.toml`, and `data/*.db` are excluded in `.gitignore`.
2. **Safe Configuration Access**: `src/config.py` retrieves settings from Streamlit secrets or OS environment variables with default fallbacks.
3. **Log & Export Sanitization**:
   - Database connection paths and URIs are masked in logs and UI errors.
   - Export services (`ExportService.to_csv` and `ExportService.to_json`) only export domain content fields and explicitly omit connection strings, internal tokens, or user credentials.
   - Automated tests in `test_exports.py` explicitly verify that strings like `postgres://`, `password=`, and `api_key` never appear in exported outputs.

---

## 7. How Automated Tests Work

The test suite consists of **38 automated tests** in `pytest`:
- **Isolation**: Every test runs in total isolation using a temporary SQLite database fixture (`conftest.py`), leaving zero residual records.
- **ORM Integrity & Cascades**: `test_database.py` validates real SQLAlchemy ORM models, foreign key relationships, orphan prevention, and cascade deletes.
- **Connection Reopening & Persistence**: Tests verify that closing and recreating the SQLAlchemy engine retains data written to the database file.
- **Edge Cases**:
  - Empty and whitespace-only inputs.
  - Text length boundary violations (<20 chars, >50,000 chars).
  - Malicious prompt injection strings inside source content.
  - Missing and corrupted passage IDs.
  - Invented metrics, dates, and quotes.
  - Approval state invalidation upon editing.
  - Unicode emoji handling and CSV RFC 4180 escaping.

---

## 8. Why Human Approval Is Mandatory

### The "Human-in-the-Loop" Principle
Automated checks are powerful filters, but they cannot replace human judgment:
1. **Context & Tone**: An automated check can confirm that `"42% reduction"` is accurate, but only a human editor can determine if the phrasing accurately reflects the company's market positioning.
2. **Legal & Compliance Responsibility**: Legally, an organization is responsible for its published claims. Separating the automated check score from the human approval status ensures that human reviewers retain ultimate editorial authority.
3. **Edit Invalidation**: If an approved post is subsequently edited, SourceWise AI **automatically resets its status to `reopened`**, guaranteeing that no unauthorized textual alterations can sneak into production under the guise of an existing approval.

---

## 9. Known Limitations & Future Enhancements

| Current Boundary | Architectural Reason | Future Enhancement |
| :--- | :--- | :--- |
| **Authoritative Pasted Text** | Preventing SSRF vulnerabilities and scraping failures | Implement a sandboxed headless scraper with domain allowlisting |
| **Rule-Based Metric Audit** | Zero-latency, zero-cost deterministic verification | Combine regex matching with an optional cross-encoder embedding model |
| **Single-User Session** | Scoped appropriately for an internship assessment | Add Supabase Auth (Row-Level Security) for multi-tenant enterprise teams |
| **Static Video Script** | Generates formatted script text and visual cues | Integrate with ElevenLabs and HeyGen APIs for automated synthetic video rendering |

