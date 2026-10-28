"""
Unit tests validating the bespoke editorial UI/UX, navigation structure,
and absence of unwanted status banners in SourceWise AI.
"""
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app.py"

def test_app_file_exists_and_parses():
    assert APP_PATH.exists(), "app.py must exist in the project root."
    content = APP_PATH.read_text(encoding="utf-8")
    assert len(content) > 1000

    # Ensure python syntax compiles without error
    compile(content, str(APP_PATH), "exec")

def test_no_unwanted_system_status_or_banners():
    content = APP_PATH.read_text(encoding="utf-8").lower()

    unwanted_phrases = [
        "system status",
        "demo mode (no ai api required)",
        "session memory (unpersisted)",
        "database notice: running in temporary session memory",
        "active mode: demo mode",
    ]

    for phrase in unwanted_phrases:
        assert phrase not in content, f"Unwanted phrase '{phrase}' must not be present in app.py"

def test_navigation_destinations_and_no_emoji():
    content = APP_PATH.read_text(encoding="utf-8")

    expected_nav_items = [
        "01  Workspace",
        "02  Create Content",
        "03  Evidence Review",
        "04  Content Library",
        "05  Brand Settings",
        "06  System Settings"
    ]

    for item in expected_nav_items:
        assert item in content, f"Navigation item '{item}' must be present in app.py"

    # Ensure no emoji characters are present in the navigation list
    nav_match = re.search(r'nav_options\s*=\s*\[(.*?)\]', content, re.DOTALL)
    assert nav_match is not None, "nav_options list must be defined in app.py"
    nav_block = nav_match.group(1)
    emojis = re.findall(r'[\U00010000-\U0010ffff]', nav_block)
    assert len(emojis) == 0, f"No emojis allowed in nav_options, found: {emojis}"

def test_editorial_masthead_and_palette():
    content = APP_PATH.read_text(encoding="utf-8")
    assert "SOURCEWISE" in content
    assert "Editorial Evidence Engine" in content or "Editorial Traceability Engine" in content
    assert "#faf8f5" in content  # Warm paper canvas
    assert "#1b4332" in content  # Forest green accent
    assert "#c25e46" in content  # Muted terracotta accent

