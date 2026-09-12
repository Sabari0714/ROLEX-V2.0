"""ROLEX Android entry point (Phase 15).

This is the file buildozer packages (see buildozer.spec:
source.dir = ., main file = main.py). On Android it launches the
Kivy cockpit; on desktop it falls back to the text cockpit.
"""
import sys
from pathlib import Path

# make `rolex` importable when running from the project root
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rolex.ui import KIVY                      # noqa: E402
from rolex.assistant import get_assistant      # noqa: E402


def main() -> None:
    assistant = get_assistant()
    if KIVY:
        from rolex.ui import RolexApp
        app = RolexApp(assistant=assistant)
        app.run()
    else:
        from rolex.ui import text_cockpit
        text_cockpit(assistant)


if __name__ == "__main__":
    main()
