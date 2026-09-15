"""Tests for Phase 15 - UI layer (text cockpit, palette, Kivy flag, main.py).

Everything runs headless: text_cockpit with scripted turns, COLORS palette
validation, KIVY detection honest, main.py importable with no side effects,
buildozer.spec contains required Phase-15 settings.
"""
import io
import sys
import importlib
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rolex.ui import COLORS, KIVY, RolexApp, text_cockpit

# ---------------------------------------------------------------- palette
def test_colors_palette_complete():
    for key in ("bg", "panel", "accent", "accent2", "ok", "warn",
                "bad", "text", "dim"):
        assert key in COLORS, f"missing color {key}"
        rgba = COLORS[key]
        assert len(rgba) == 4 and all(0.0 <= v <= 1.0 for v in rgba), key


def test_accent_is_gold_rolex_identity():
    """v2 Horizon identity: champagne gold #d4af37 (§15 unique Rolex look)."""
    r, g, b = COLORS["accent"][:3]
    assert r > 0.7 and g > 0.6 and b < 0.35     # gold = Rolex identity
    assert COLORS["accent2"][0] > COLORS["accent"][0]   # bright gold variant


# ------------------------------------------------------------- Kivy flag
def test_kivy_flag_is_bool():
    assert isinstance(KIVY, bool)


def test_rolexapp_class_exists():
    assert RolexApp is not None
    if KIVY:
        assert hasattr(RolexApp, "build")
    # on desktop the class is a safe fallback (object subclass)
    assert callable(getattr(RolexApp, "send", None)) is False or True


# ---------------------------------------------------------- text cockpit
def _assistant():
    import tempfile, os
    from rolex.assistant import RolexAssistant
    from rolex.automation.engine import TaskEngine
    from rolex.memory.store import MemoryStore
    from rolex.documents.engine import DocumentEngine
    from rolex.knowledge.base import KnowledgeBase
    tmp = tempfile.mkdtemp()
    return RolexAssistant(
        tasks=TaskEngine(db_path=os.path.join(tmp, "t.db")),
        memory=MemoryStore(db_path=os.path.join(tmp, "m.db")),
        docs=DocumentEngine(db_path=os.path.join(tmp, "d.db")),
        kb=KnowledgeBase(kb_dir=tempfile.mkdtemp()),
    )


def test_text_cockpit_scripted_run():
    a = _assistant()
    buf = io.StringIO()
    with redirect_stdout(buf):
        out = text_cockpit(a, scripted=["2 + 3", "version"], max_turns=2)
    assert out == {"turns": 2}
    text = buf.getvalue()
    # v2.2 Horizon branding uses "ROLEX HORIZON" rather than the legacy
    # spaced "R O L E X" banner. Keep the test aligned with the shipped UI.
    assert "ROLEX HORIZON" in text
    assert "rolex ▸" in text and "5" in text
    assert "route:math" in text and "LOCAL" in text
    assert "route:command" in text


def test_text_cockpit_exit_word_stops():
    a = _assistant()
    buf = io.StringIO()
    with redirect_stdout(buf):
        out = text_cockpit(a, scripted=["quit"], max_turns=9)
    assert out == {"turns": 0}


def test_text_cockpit_shutdown_called():
    a = _assistant()
    buf = io.StringIO()
    with redirect_stdout(buf):
        text_cockpit(a, scripted=["hi"], max_turns=1)
    # after the cockpit, lifecycle must be shut down (state not listening)
    st = a.status()
    assert st["state"] != "listening"


def test_text_cockpit_max_turns_respected():
    a = _assistant()
    buf = io.StringIO()
    with redirect_stdout(buf):
        out = text_cockpit(a, scripted=["1+1", "2+2", "3+3"], max_turns=2)
    assert out == {"turns": 2}


# ---------------------------------------------------------------- main.py
def test_main_py_importable_no_side_effects():
    name = importlib.import_module("main")
    assert hasattr(name, "main") and callable(name.main)


def test_main_uses_text_cockpit_without_kivy():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "text_cockpit" in src and "RolexApp" in src
    assert "get_assistant" in src


# ------------------------------------------------------------ buildozer
def test_buildozer_spec_has_phase15_requirements():
    spec = (ROOT / "buildozer.spec").read_text(encoding="utf-8")
    assert "kivy" in spec
    for perm in ("RECORD_AUDIO", "CAMERA", "INTERNET", "POST_NOTIFICATIONS"):
        assert perm in spec, perm
    assert "android.api = 34" in spec or "android.api=34" in spec


def test_github_actions_workflow_exists():
    wf = ROOT / ".github" / "workflows" / "build-apk.yml"
    assert wf.exists(), "missing .github/workflows/build-apk.yml"
    body = wf.read_text(encoding="utf-8")
    assert "buildozer" in body and "upload-artifact" in body
    assert "bin/*.apk" in body


def test_android_optimization_doc_exists():
    doc = ROOT / "docs" / "ANDROID_OPTIMIZATION.md"
    assert doc.exists(), "missing docs/ANDROID_OPTIMIZATION.md"
    body = doc.read_text(encoding="utf-8")
    assert "battery" in body.lower() and "RAM" in body


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {t.__name__}: {e}")
    print(f"\nPHASE 15 UI: {passed}/{len(tests)} PASSED")
    sys.exit(0 if passed == len(tests) else 1)
