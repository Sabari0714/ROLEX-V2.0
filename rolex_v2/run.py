"""ROLEX AI v2.2.0 desktop runner and self-test entry point."""
from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="ROLEX AI v2.2.0")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    from rolex.assistant import get_assistant
    assistant = get_assistant()

    if args.self_test:
        from rolex.security import run_self_test
        report = run_self_test()
        print("SELF-TEST:", report)
        return

    if args.demo:
        for text in ("version", "calculate 25*4", "what is 12V 2A power"):
            print("YOU:", text)
            print("ROLEX:", assistant.ask(text).text)
        return

    from rolex.ui import text_cockpit
    text_cockpit(assistant)


if __name__ == "__main__":
    main()
