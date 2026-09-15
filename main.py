"""ROLEX Android entry point.

Keep Android UI startup independent from the optional/core assistant imports.
The previous entry point constructed RolexAssistant before Kivy created a
window, so any Android-only dependency/import failure could terminate the
process with no visible UI and no useful on-screen diagnostic.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    # Import only the UI first.  This guarantees that a core-module failure
    # cannot prevent Android from creating a visible window.
    from rolex.ui import KIVY, RolexApp, text_cockpit

    if KIVY:
        # Assistant construction is intentionally deferred to RolexApp.build().
        # The UI can then display a startup error instead of silently exiting.
        RolexApp().run()
        return

    from rolex.assistant import get_assistant
    text_cockpit(get_assistant())


if __name__ == "__main__":
    main()
