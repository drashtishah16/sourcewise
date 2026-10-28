"""
SQLite Database Verification and Safe Setup Utility for SourceWise AI.
Performs idempotent table initialization without dropping or altering existing user data.
Verifies all 6 required tables exist and foreign keys are enforced.
Validates live CRUD lifecycle: Insert -> Read -> Update -> Cleanup in a strict finally block.
Guarantees zero sensitive data leakage in console output and logs.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text
from src.database import DatabaseManager, sanitize_db_error
from src.models import BrandProfileSchema, generate_id
from src.config import is_database_configured, get_database_path, get_database_url

REQUIRED_TABLES = {
    "brand_profiles",
    "source_documents",
    "source_passages",
    "content_drafts",
    "claim_evidence",
    "review_events"
}

def main():
    print("=" * 65)
    print("SOURCEWISE AI — SAFE SQLITE DATABASE SETUP & VERIFICATION")
    print("=" * 65)

    if not is_database_configured():
        print("[!] No active database configuration found.")
        print("    Operating in Temporary Session Mode (Records not persisted).")
        print("    Demo Mode remains 100% functional without an active database.")
        sys.exit(0)

    db_path = get_database_path()
    if db_path:
        print(f"[*] Target SQLite Database File: {db_path}")

    print("[*] Testing SQLite database connection & foreign keys...")
    try:
        ok, msg = DatabaseManager.check_connection()
    except Exception as e:
        ok, msg = False, sanitize_db_error(e)

    if not ok:
        print(f"[-] Connection Failed: {sanitize_db_error(msg)}")
        sys.exit(1)
    print(f"[+] Connection Succeeded: {sanitize_db_error(msg)}")

    print("[*] Verifying & initializing database schema (Safe: No Drop/Overwrite)...")
    try:
        ok_init, init_msg = DatabaseManager.init_db()
    except Exception as e:
        ok_init, init_msg = False, sanitize_db_error(e)

    if not ok_init:
        print(f"[-] Schema Initialization Failed: {sanitize_db_error(init_msg)}")
        sys.exit(1)
    print(f"[+] Schema Status: {sanitize_db_error(init_msg)}")

    # Verify table existence
    engine = DatabaseManager.get_engine()
    if engine is None:
        print("[-] Engine could not be retrieved.")
        sys.exit(1)

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        missing_tables = REQUIRED_TABLES - existing_tables
        if missing_tables:
            print(f"[-] Missing required tables: {sorted(missing_tables)}")
            sys.exit(1)
        print(f"[+] All 6 required tables verified: {sorted(REQUIRED_TABLES)}")

        # Verify foreign keys pragma is active
        with engine.connect() as conn:
            fk_val = conn.execute(text("PRAGMA foreign_keys")).scalar()
            if fk_val != 1:
                print(f"[-] SQLite foreign key enforcement check failed: PRAGMA foreign_keys = {fk_val}")
                sys.exit(1)
        print("[+] SQLite foreign key enforcement verified (PRAGMA foreign_keys = 1).")
    except Exception as inspect_err:
        print(f"[-] Table / Foreign Key verification failed: {sanitize_db_error(inspect_err)}")
        sys.exit(1)

    print("[*] Beginning CRUD verification (Insert -> Read -> Update -> Cleanup)...")
    test_id = generate_id("diag_brand")
    record_created = False
    verification_passed = False

    try:
        # 1. CREATE / INSERT
        diagnostic_brand = BrandProfileSchema(
            id=test_id,
            name="SourceWise Diagnostic Brand (Temporary)",
            target_audience="System Verifier",
            tone_of_voice="Technical & Verified",
            preferred_terminology=["traceability", "grounded"],
            forbidden_terminology=["untested"],
            primary_cta="Visit sourcewise.ai/eval",
            required_disclaimer="Diagnostic record verified."
        )

        save_ok, save_msg = DatabaseManager.save_brand_profile(diagnostic_brand)
        if not save_ok:
            raise RuntimeError(f"Insert failed: {sanitize_db_error(save_msg)}")
        record_created = True
        print(f"[+] 1/4 INSERT Passed: Diagnostic record created (ID: {test_id}).")

        # 2. READ / RETRIEVE
        retrieved = DatabaseManager.get_brand_profile(test_id)
        if not retrieved or retrieved.name != diagnostic_brand.name:
            raise RuntimeError("Read verification failed: Record was not found or data mismatched.")
        print(f"[+] 2/4 READ Passed: Retrieved '{retrieved.name}' matching inserted data.")

        # 3. UPDATE
        retrieved.name = "SourceWise Diagnostic Brand (Updated)"
        retrieved.primary_cta = "Visit sourcewise.ai/updated"
        update_ok, update_msg = DatabaseManager.save_brand_profile(retrieved)
        if not update_ok:
            raise RuntimeError(f"Update failed: {sanitize_db_error(update_msg)}")

        # Verify update persisted
        re_queried = DatabaseManager.get_brand_profile(test_id)
        if not re_queried or re_queried.name != "SourceWise Diagnostic Brand (Updated)":
            raise RuntimeError("Update verification failed: Modified values did not persist.")
        print(f"[+] 3/4 UPDATE Passed: Successfully updated record and verified persistence.")

        verification_passed = True

    except Exception as err:
        safe_msg = sanitize_db_error(err)
        print(f"[-] CRUD Verification Failed: {safe_msg}")
        verification_passed = False

    finally:
        # 4. CLEANUP in finally block (guaranteed execution)
        if record_created:
            print(f"[*] Cleaning up diagnostic record '{test_id}'...")
            try:
                del_ok, del_msg = DatabaseManager.delete_brand_profile(test_id)
                post_cleanup_check = DatabaseManager.get_brand_profile(test_id)
                if del_ok and post_cleanup_check is None:
                    print(f"[+] 4/4 CLEANUP Passed: Diagnostic record '{test_id}' safely deleted.")
                else:
                    print(f"[-] Warning: Record '{test_id}' was not completely removed: {sanitize_db_error(del_msg)}")
                    verification_passed = False
            except Exception as del_err:
                print(f"[-] Cleanup error: {sanitize_db_error(del_err)}")
                verification_passed = False

    print("=" * 65)
    if verification_passed:
        print("[+] All SQLite CRUD lifecycle tests completed successfully!")
        sys.exit(0)
    else:
        print("[-] Database verification failed. See errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
