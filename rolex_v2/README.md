# ROLEX AI v2.2.0

Local-first, privacy-first personal AI assistant with a unified CLI/Android facade.

## Highlights

- Original ROLEX gold identity / Horizon HUD — no Autobots theme.
- Wake word: **Hey Guru**.
- Tamil / English / Tanglish language handling.
- Local math and engineering engine.
- Local knowledge base.
- Memory, tasks, planning, reminders and automation.
- Documents, voice and vision modules.
- Security, permissions, audit and diagnostics.
- Optional AI Hub sources: OpenAI, Gemini and Ollama; Rolex owns the final answer.
- Android Kivy UI and desktop text cockpit share the same `RolexAssistant.ask()` facade.

## Run

```bash
python run.py --self-test
python run.py --demo
python -m pytest tests/ -q
python run.py
```

## Android

```bash
buildozer -v android debug
```

See `docs/ANDROID_OPTIMIZATION.md` and `ARCHITECTURE.md` for the complete architecture and build notes.
