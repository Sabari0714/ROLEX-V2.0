"""Android UI startup regression tests."""
from __future__ import annotations

import ast
import re
from pathlib import Path


def test_kivy_kv_has_single_root_and_required_ids():
    """The Android KV document must contain exactly one root widget."""
    from rolex.ui import android_ui

    kv = android_ui.KV
    lines = []
    for raw in kv.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#:"):
            continue
        lines.append(line)

    assert lines[0] == "BoxLayout:", lines[:8]

    top_level_widgets = [
        line for line in lines[1:]
        if line and not line.startswith(" ")
        and re.match(r"^[A-Za-z_][A-Za-z0-9_]*:$", line)
    ]
    assert top_level_widgets == [], top_level_widgets

    for required_id in ("state", "chat", "chat_scroll", "input"):
        assert f"id: {required_id}" in kv


def test_android_entrypoint_does_not_construct_core_before_ui():
    """main.py must lazy-load the assistant on Android.

    A core import/constructor failure must not terminate the process before
    Kivy has created a visible window and can show the diagnostic.
    """
    path = Path(__file__).resolve().parents[1] / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    top_level_imports = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            top_level_imports.append((node.module or "", [a.name for a in node.names]))
        elif isinstance(node, ast.Import):
            top_level_imports.extend((a.name, []) for a in node.names)

    assert not any(module == "rolex.assistant" for module, _ in top_level_imports)

    main_fn = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == "main")
    source = ast.get_source_segment(path.read_text(encoding="utf-8"), main_fn) or ""
    assert "from rolex.ui import KIVY, RolexApp, text_cockpit" in source
    assert "from rolex.assistant import get_assistant" in source
