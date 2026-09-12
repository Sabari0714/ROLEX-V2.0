"""ROLEX AI Android/desktop entry point."""
from __future__ import annotations


def main() -> None:
    from rolex.assistant import get_assistant
    assistant = get_assistant()
    try:
        from rolex.ui.android_ui import RolexApp
        app = RolexApp(assistant=assistant)
        app.run()
    except Exception:
        from rolex.ui import text_cockpit
        text_cockpit(assistant)


if __name__ == "__main__":
    main()
