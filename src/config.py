"""
Configuration management for SourceWise AI.
Reads settings from environment variables (.env) or Streamlit secrets with safe fallbacks.
Configures local persistent SQLite database by default at 'data/sourcewise.db'
relative to project root.
"""
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

# Project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "sourcewise.db"

def get_secret_or_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safely retrieve a configuration value checking Streamlit secrets first,
    then environment variables, and finally falling back to the default.
    """
    # Try streamlit secrets if Streamlit is available and running
    try:
        import streamlit as st
        if hasattr(st, "secrets") and st.secrets is not None and key in st.secrets:
            val = st.secrets[key]
            if val is not None and str(val).strip():
                clean_val = str(val).strip()
                if (clean_val.startswith('"') and clean_val.endswith('"')) or (clean_val.startswith("'") and clean_val.endswith("'")):
                    clean_val = clean_val[1:-1].strip()
                return clean_val
    except Exception:
        pass

    env_val = os.getenv(key)
    if env_val is not None and env_val.strip():
        clean_env = env_val.strip()
        if (clean_env.startswith('"') and clean_env.endswith('"')) or (clean_env.startswith("'") and clean_env.endswith("'")):
            clean_env = clean_env[1:-1].strip()
        return clean_env

    return default

def get_database_path() -> Optional[Path]:
    """
    Returns the resolved Path to the SQLite database file,
    ensuring its parent directory exists.
    Returns None if an in-memory database (:memory:) is configured.
    """
    # 1. Check custom DATABASE_PATH
    custom_path_str = get_secret_or_env("DATABASE_PATH")
    if custom_path_str:
        p = Path(custom_path_str.strip())
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p.resolve()

    # 2. Check DATABASE_URL for sqlite://
    raw_url = get_secret_or_env("DATABASE_URL")
    if raw_url:
        url = raw_url.strip()
        # Strip wrapping quotes
        if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
            url = url[1:-1].strip()

        if ":memory:" in url:
            return None

        if url.startswith("sqlite:///"):
            path_part = url[len("sqlite:///"):]
            p = Path(path_part)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            p.parent.mkdir(parents=True, exist_ok=True)
            return p.resolve()

    # 3. Default to project_root/data/sourcewise.db
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_DB_PATH.resolve()

def get_database_url() -> str:
    """
    Returns the sanitized SQLite database URL for SQLAlchemy.
    Defaults to 'sqlite:///<project_root>/data/sourcewise.db'.
    """
    raw_url = get_secret_or_env("DATABASE_URL")
    if raw_url:
        url = raw_url.strip()
        if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
            url = url[1:-1].strip()
        if url.startswith("sqlite://"):
            if ":memory:" in url:
                return "sqlite:///:memory:"
            # Resolve relative file path if provided
            path_part = url[len("sqlite:///"):] if url.startswith("sqlite:///") else url[len("sqlite://"):]
            p = Path(path_part)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            p.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{p.resolve().as_posix()}"

    db_path = get_database_path()
    if db_path is None:
        return "sqlite:///:memory:"

    return f"sqlite:///{db_path.as_posix()}"

def is_database_configured() -> bool:
    """
    Returns True if the persistent SQLite database is available and enabled.
    Returns False only if explicitly disabled via DISABLE_DATABASE or FORCE_SESSION_MODE.
    """
    force_session = get_secret_or_env("FORCE_SESSION_MODE", "false").lower() in ("true", "1", "yes")
    disable_db = get_secret_or_env("DISABLE_DATABASE", "false").lower() in ("true", "1", "yes")
    if force_session or disable_db:
        return False
    return True

def get_gemini_api_key() -> Optional[str]:
    """Returns the Gemini API key from Streamlit secrets or environment variables."""
    return get_secret_or_env("GEMINI_API_KEY")

def get_gemini_model() -> str:
    """
    Returns the configured Gemini model name.
    Defaults to the verified stable Flash model 'gemini-2.5-flash'.
    Can be overridden via GEMINI_MODEL or AI_MODEL_NAME.
    """
    return get_secret_or_env("GEMINI_MODEL") or get_secret_or_env("AI_MODEL_NAME") or "gemini-2.0-flash"

def is_gemini_configured() -> bool:
    """Returns True only if a plausible GEMINI_API_KEY is configured and FORCE_DEMO_MODE is not true."""
    key = get_gemini_api_key()
    if not key:
        return False
    clean = key.strip().strip("'\"").lower()
    if clean.startswith("your-") or clean.startswith("your_") or clean in ("placeholder", "todo", "none", "dummy"):
        return False
    force_demo = get_secret_or_env("FORCE_DEMO_MODE", "false").lower() in ("true", "1", "yes")
    return not force_demo

def get_ai_credentials() -> Dict[str, Optional[str]]:
    """Returns configured AI provider API keys. Never fabricates keys."""
    return {
        "gemini": get_gemini_api_key(),
        "gemini_model": get_gemini_model(),
        "openai": get_secret_or_env("OPENAI_API_KEY"),
        "anthropic": get_secret_or_env("ANTHROPIC_API_KEY"),
        "model_name": get_gemini_model()
    }

def is_connected_mode_available() -> bool:
    """
    Connected mode requires at least one genuine AI provider API key.
    If none is found, returns False.
    """
    force_demo = get_secret_or_env("FORCE_DEMO_MODE", "false").lower() in ("true", "1", "yes")
    if force_demo:
        return False
    return is_gemini_configured() or bool(get_secret_or_env("OPENAI_API_KEY")) or bool(get_secret_or_env("ANTHROPIC_API_KEY"))

def get_app_env() -> str:
    """Returns current environment ('development' or 'production')."""
    return get_secret_or_env("APP_ENV", "development").lower()
