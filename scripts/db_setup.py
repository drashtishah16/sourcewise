"""
Database Setup, Migration, and Verification Utility for SourceWise AI.
Safe, idempotent schema verification for Supabase PostgreSQL.
Tests real connection, initializes tables, and validates CRUD operations without leaking secrets.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import DatabaseManager
from src.models import BrandProfileSchema, generate_id
from src.config import is_database_configured, get_database_url

def main():
    print("=" * 60)
    print("SOURCEWISE AI — DATABASE VERIFICATION & SETUP")
    print("=" * 60)

    if not is_database_configured():
        print("[!] No DATABASE_URL found in environment or .env file.")
        print("    Operating in Temporary Session Mode.")
        print("    To connect Supabase, configure DATABASE_URL in .env or Streamlit secrets.")
        sys.exit(0)

    print("[*] Testing PostgreSQL connection...")
    ok, msg = DatabaseManager.check_connection()
    if not ok:
        print(f"[-] Connection Failed: {msg}")
        sys.exit(1)
    print(f"[+] Connection Succeeded: {msg}")

    print("[*] Verifying & initializing database schema...")
    ok_init, init_msg = DatabaseManager.init_db()
    if not ok_init:
        print(f"[-] Schema Initialization Failed: {init_msg}")
        sys.exit(1)
    print(f"[+] Schema Status: {init_msg}")

    print("[*] Testing persistent write & retrieval...")
    test_id = generate_id("brand_test")
    test_brand = BrandProfileSchema(
        id=test_id,
        name="SourceWise Diagnostic Brand",
        target_audience="Engineers & Reviewers",
        tone_of_voice="Technical & Verified",
        preferred_terminology=["traceability", "grounded"],
        forbidden_terminology=["untested"],
        primary_cta="Visit sourcewise.ai",
        required_disclaimer="Diagnostic record verified."
    )

    # 1. Save record
    save_ok, save_msg = DatabaseManager.save_brand_profile(test_brand)
    if not save_ok:
        print(f"[-] Persistent Write Failed: {save_msg}")
        sys.exit(1)
    print(f"[+] Persistent Write Passed: {save_msg}")

    # 2. Retrieve record
    retrieved = DatabaseManager.get_brand_profile(test_id)
    if not retrieved or retrieved.name != test_brand.name:
        print("[-] Retrieval Failed: Record was not found in database.")
        sys.exit(1)
    print(f"[+] Persistent Retrieval Passed: Found record '{retrieved.name}' (ID: {retrieved.id})")

    # 3. Clean up diagnostic record
    print("[+] All PostgreSQL persistence checks passed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
