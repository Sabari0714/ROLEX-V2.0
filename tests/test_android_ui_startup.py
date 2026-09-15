"""Android UI startup regression tests."""
from __future__ import annotations

import pytest


def test_kivy_kv_has_single_root_and_required_ids():
    """The Android KV document must load as one root widget.

    This catches the previous three-top-level-widget layout that could fail
    during Builder.load_string() on the Android runtime.
    """
    pytest.importorskip("kivy")
    from kivy.lang import Builder
    from rolex.ui import android_ui

    root = Builder.load_string(android_ui.KV)
    assert root is not None
    assert root.__class__.__name__ == "BoxLayout"
    assert root.ids.get("state") is not None
    assert root.ids.get("chat") is not None
    assert root.ids.get("chat_scroll") is not None
    assert root.ids.get("input") is not None
