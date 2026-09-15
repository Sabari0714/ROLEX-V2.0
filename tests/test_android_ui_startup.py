"""Android UI startup regression tests."""
from __future__ import annotations

import re


def test_kivy_kv_has_single_root_and_required_ids():
    """The Android KV document must contain exactly one root widget.

    CI intentionally does not install desktop Kivy just to run unit tests;
    the Android build itself validates Kivy parsing. This static regression
    test still catches the previous multiple-top-level-widget bug.
    """
    from rolex.ui import android_ui

    kv = android_ui.KV
    lines = []
    for raw in kv.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#:"):
            continue
        lines.append(line)

    # The first non-directive line is the only legal root declaration.
    assert lines[0] == "BoxLayout:", lines[:8]

    # No additional zero-indentation widget declarations are allowed.
    top_level_widgets = [
        line for line in lines[1:]
        if line and not line.startswith(" ")
        and re.match(r"^[A-Za-z_][A-Za-z0-9_]*:$", line)
    ]
    assert top_level_widgets == [], top_level_widgets

    for required_id in ("state", "chat", "chat_scroll", "input"):
        assert f"id: {required_id}" in kv
