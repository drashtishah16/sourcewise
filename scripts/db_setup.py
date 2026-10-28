"""
Database Verification and Safe Setup Utility for SourceWise AI.
Performs idempotent table initialization without dropping or altering existing user data.
Validates live CRUD lifecycle: Insert -> Read -> Update -> Cleanup in a strict finally block.
Guarantees zero credential leakage in console output and logs.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager, sanitize_db_error
from src.models import BrandProfileSchema, generate_id
from src.config import is_database_configured

def main():
    print("=" * 65)
    print("SOURCEWISE AI — SAFE DATABASE SETUP & CRUD VERIFICATION")
    print("=" * 65)

    if not is_database_configured():
        print("[!] No valid DATABASE_URL found in environment, secrets, or .env.")
        print("    Operating in Temporary Session Mode (Records not persisted).")
        print("    Demo Mode remains 100% functional without an active database.")
        print("    To connect Supabase, configure DATABASE_URL in .env or secrets.")
        sys.exit(0)

    print("[*] Testing PostgreSQL connection...")
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
                    print(f"[!] Warning: Record '{test_id}' delete status: {sanitize_db_error(del_msg)}")
            except Exception as del_err:
                print(f"[!] Cleanup error: {sanitize_db_error(del_err)}")

    print("=" * 65)
    if verification_passed:
        print("[+] All PostgreSQL CRUD lifecycle tests completed successfully!")
        sys.exit(0)
    else:
        print("[-] Database verification failed. See errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
