#!/usr/bin/env python3
"""ROLEX AI - desktop CLI entry point."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from rolex.ui import text_cockpit
from rolex.assistant import get_assistant

def self_test() -> int:
    from rolex.security import run_self_test, DIAGNOSTICS
    rep = run_self_test()
    print("=" * 58)
    print("ROLEX SELF-TEST")
    print("=" * 58)
    for chk in DIAGNOSTICS.health_checks():
        mark = "OK" if chk["ok"] else "FAIL"
        print(f" {mark:<4} {chk['check']:<24} {chk.get('detail', '')}")
    print("-" * 58)
    print(f" score: {rep['score']}/100 - verdict: {rep['verdict']}")
    print("=" * 58)
    return 0 if rep["verdict"] in ("HEALTHY", "DEGRADED") else 1

def demo() -> int:
    a = get_assistant(); a.startup()
    scripted = ["hey guru", "what is 12 * 8 + 4", "ohms law 12V 2A", "convert 5 km to meters", "tell me about ohms law", "remind me in 5 minutes to check demo motor", "who are you", "help"]
    for q in scripted:
        res = a.ask(q)
        print(f"USER: {q}\nROLEX: {res}\n")
    for t in list(a.tasks.upcoming(50)):
        if "demo motor" in t.title: a.tasks.cancel(t.id)
    a.shutdown(); return 0

def one_shot(question: str) -> int:
    a = get_assistant(); a.startup(); print(a.ask(question)); a.shutdown(); return 0

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in argv: return self_test()
    if "--demo" in argv: return demo()
    if "--ask" in argv:
        i = argv.index("--ask")
        return one_shot(argv[i + 1]) if i + 1 < len(argv) else 2
    a = get_assistant(); return 0 if text_cockpit(a).get("turns", 0) >= 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
