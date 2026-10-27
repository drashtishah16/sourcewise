"""
Configuration management for SourceWise AI.
Reads settings from environment variables (.env) or Streamlit secrets with safe fallbacks.
"""
import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

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
                return str(val).strip()
    except Exception:
        pass

    env_val = os.getenv(key)
    if env_val is not None and env_val.strip():
        return env_val.strip()

    return default

def get_database_url() -> Optional[str]:
    """
    Returns the sanitized PostgreSQL database URL.
    Ensures modern SQLAlchemy compatibility (replaces 'postgres://' with 'postgresql://'
    or 'postgresql+psycopg://' if applicable).
    """
    raw_url = get_secret_or_env("DATABASE_URL")
    if not raw_url:
        return None

    url = raw_url.strip()
    # Normalize legacy prefix
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]

    # If it's a generic postgresql:// URL and psycopg is installed, prefer postgresql+psycopg://
    # unless already specified with a driver
    if url.startswith("postgresql://") and "+" not in url.split("://")[0]:
        # Leave as postgresql:// or let SQLAlchemy pick the installed driver
        pass

    return url

def is_database_configured() -> bool:
    """Returns True if a valid DATABASE_URL is present in the configuration."""
    url = get_database_url()
    return bool(url and len(url) > 10 and "postgres" in url.lower() and "[YOUR-PASSWORD]" not in url)

def get_ai_credentials() -> Dict[str, Optional[str]]:
    """Returns configured AI provider API keys. Never fabricates keys."""
    return {
        "openai": get_secret_or_env("OPENAI_API_KEY"),
        "gemini": get_secret_or_env("GEMINI_API_KEY"),
        "anthropic": get_secret_or_env("ANTHROPIC_API_KEY"),
        "model_name": get_secret_or_env("AI_MODEL_NAME", "gpt-4o-mini")
    }

def is_connected_mode_available() -> bool:
    """
    Connected mode requires at least one genuine AI provider API key.
    If none is found, returns False.
    """
    creds = get_ai_credentials()
    force_demo = get_secret_or_env("FORCE_DEMO_MODE", "false").lower() in ("true", "1", "yes")
    if force_demo:
        return False
    return bool(creds["openai"] or creds["gemini"] or creds["anthropic"])

def get_app_env() -> str:
    """Returns current environment ('development' or 'production')."""
    return get_secret_or_env("APP_ENV", "development").lower()

