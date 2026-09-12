# ROLEX AI - Roadmap: 15 Phases + v2.0 Horizon (Complete)

**`இந்த roadmap 100% complete. Scratch-la irundhu, stable core-la irundhu, final APK varaikkum — ஒன்றும் விடமாட்டோம்.`**

Legend: OK = built & tested. v1.0 delivered 15 phases; v2.0 (Horizon) adds the 47-section master-blueprint modules. Full suite: **267 tests / 17 files, all passing**.

---

## Phase 1 — Foundation ✅
Clean folder structure (`rolex/` package tree), central config (`config.py` with
data/log/memory/KB paths), `.env` + `.env.example` support, rotating file logging
(`logging_setup.py`), typed error hierarchy (`errors.py`), version pinning
(`v1.0.0`), git + `.gitignore`, and a no-dependency test framework pattern.
**Tests**: `tests/test_foundation.py`

## Phase 2 — Rolex Core ✅
Identity (`core/identity.py` — ROLEX, wake word "Hey Guru"), strict system state
machine (OFFLINE→BOOTING→LISTENING→THINKING→ACTING→LEARNING→DEGRADED→STOPPED),
lifecycle startup/shutdown in dependency order, command processor
(`/status /help /whoami /version /uptime /state /stop /restart`, whole-utterance
matching so normal chat is never hijacked), response pipeline, and a core event
bus (publish/subscribe). **Tests**: `tests/test_core.py`

## Phase 3 — Local Brain ✅
NLU for **Tamil / English / Tanglish**: intent detection (greeting, identity,
math, engineering, unit_convert, time_now, date_now, reminder, task, knowledge,
thanks, capability, confirmation, denial), context tracking, basic reasoning,
and conversation flow. Script/Tanglish math words ("perukku", "vaagai",
"சதவீதம்") are understood. **Tests**: `tests/test_brain.py`

## Phase 4 — Math & Engineering Engine ✅ ⚡
Everything local, zero AI: `+ − × ÷ %`, powers/roots/factorial, algebra
(equations), geometry (area/perimeter/volume), trigonometry, **unit conversion**
(length/mass/temp/speed/energy), **Ohm's law** (V/I/R/P), power & energy, RPM,
torque, motors, gears/pulleys, electronics (LED resistor, series/parallel,
capacitors), and mechanical formulas. AST-based safe evaluator — **no `eval()`,
no injection**. Conversational prefixes ("what is", "calculate", "metha",
"ethana") are stripped before solving.
**Rule enforced**: calculation → Rolex locally; AI/internet only if external
info truly required. **Tests**: `tests/test_math.py`

## Phase 5 — Knowledge Engine ✅
Local knowledge base, 51 entries across 7 topics (Electrical, Electronics,
Mechanical, Civil, Computer/IT, Science, General), searchable with scoring
(`best(query, min_score)`), snippets, formulas, related entries. Learning can
add entries safely. **Tests**: `tests/test_knowledge.py`

## Phase 6 — AI Intelligence Hub ✅
OpenAI + Gemini + Ollama providers (pure `urllib`, no SDKs). Provider health
checks, timeouts, retries with backoff, **parallel asks** (`ask_multi`),
priority-based selection, and a **circuit breaker** (failing providers are
skipped during cool-down). Providers are intelligence *sources* only — the
final user-facing answer always belongs to Rolex. **Tests**: `tests/test_ai_hub.py`

## Phase 7 — Rolex Answer Engine ✅
Compares provider outputs, checks fact consistency across sources, computes
confidence, runs hallucination checks (hedge/disclaimer stripping, source
agreement), validates, and composes **ONE final Rolex response**. Handles
uncertainty honestly ("uncertain" flag + confidence label) and falls back to
the local KB when no provider is reachable (offline mode is explicit, never
silent). **Tests**: `tests/test_answer_engine.py`

## Phase 8 — Memory System ✅
Short-term conversation turns + long-term facts/preferences in SQLite
(`memory/store.py`): `add_exchange`, `recent_turns`, `search_facts`,
preference get/set, context window, `cleanup(keep_turn_days)` with VACUUM,
`reset`. **Tests**: `tests/test_memory.py`

## Phase 9 — Learning & Self-Improvement ✅
Safe pipeline: **Learn → Propose → Backup → Sandbox → Test → Approve → Apply →
Rollback**. Nothing is ever applied without explicit approval; every change is
backed up first and can be rolled back. **Never unrestricted self-modification.**
**Tests**: `tests/test_learning.py`

## Phase 10 — Task & Automation Engine ✅
Reminders (`remind me in 10 minutes to…`), scheduled tasks (one-shot),
recurring jobs (`every day 9am…`), background routines, event triggers,
priorities, and full task history. Natural-language parsing registers AND
persists the task in one call. **Tests**: `tests/test_automation.py`

## Phase 11 — Tools & Action Layer ✅
Filesystem tools (read/write/list/delete), document tools, coding tools
(safe run/search), web fetch + API call (http/https only, size-capped), device
info, and **controlled package install** (proposal-only, never executed
blindly). Every sensitive action is **permission-gated** (allow/ask/deny +
session approvals) and **audited** (append-only JSONL). Forbidden paths
(`/etc/`, `.ssh/`, `.env`, `.git/`, `rolex/security/`, `reference_old/`,
emergency-stop flag) are hard-blocked. **Tests**: `tests/test_tools.py`

## Phase 12 — Document Intelligence ✅
Read **TXT/MD/PDF/DOCX/XLSX/PPTX/CSV/JSON** (PDF via poppler `pdftotext`,
OOXML via stdlib `zipfile` + `ElementTree` — no heavy deps), search text with
context snippets, extractive summaries (keyword-density scoring), create/edit
docs, and a **local document memory** (SQLite index with recall/forget/stats).
Corrupt/missing/unsupported files fail cleanly. **Tests**: `tests/test_documents.py`

## Phase 13 — Voice + Vision ✅
Wake word **"Hey Guru"** with fuzzy detection (STT mishears like "hey google",
"guruuu", "குரு" all work), STT (speech_recognition → typed fallback), TTS
(pyttsx3 → espeak → print-only), continuous conversation loop with memory,
camera (termux/OpenCV, honest when unavailable) and vision analysis
(PIL brightness/contrast, PNG/JPEG metadata via stdlib). Every capability
reports availability **honestly** — fallbacks always work. **Tests**:
`tests/test_voice_vision.py`

## Phase 14 — Security + Reliability ✅
Permission system + audit log + emergency stop (from Phase 11, hardened here):
**encrypted secrets** (SHA256-CTR keystream + HMAC-SHA256 — tamper detected,
wrong-key refused), **crash detection** (marker files; orphaned markers → boot
recovery), **backup/restore/prune** (zip of `data/`), **diagnostics** (10 health
checks → self-test score & verdict), and **recovery**. Self-test result:
**100/100 HEALTHY**. **Tests**: `tests/test_security.py`

## Phase 15 — Android UI + Integration + APK ✅
- **RolexAssistant facade** (`rolex/assistant.py`): the single entry point wiring
  all 15 phases — wake → math ⚡ → commands → reminders → documents → knowledge →
  AI hub → validator → memory. Returns `AskResult(text, route, confidence, local,
  seconds)`. **Tests**: `tests/test_assistant.py` (15)
- **Futuristic UI** (`rolex/ui/android_ui.py`): dark cockpit palette, voice orb,
  waveform, chat bubbles, dashboard chips, Kivy when available + a full **text
  cockpit fallback** on desktop. **Tests**: `tests/test_ui.py` (13)
- **Android toolchain**: `main.py` entry, `buildozer.spec` (api 34, minapi 24,
  RECORD_AUDIO/CAMERA/INTERNET/POST_NOTIFICATIONS), **GitHub Actions workflow**
  (`.github/workflows/build-apk.yml` — import+self-test gate, then APK artifact),
  and `docs/ANDROID_OPTIMIZATION.md` (battery/RAM strategy).

---

## v2.0 - HORIZON (master blueprint, 47 sections) OK

Everything in the user's 47-section v2.0 master specification, built on top of
the 15-phase core. All optional external services stay optional; Rolex is
fully functional with zero keys and zero network.

- **9 - Task Manager**: NL todo board (add/complete/update/prioritize,
  ordinal completion, Tamil). `rolex/tasks/manager.py`
- **10 - Planning Engine**: goal -> steps templates, execute hooks, progress.
  `rolex/planning/engine.py`
- **6/32 - Live Info**: Open-Meteo weather (NO key) + Serper search (optional
  key) + SQLite TTL cache -> offline fallback. `rolex/live/engine.py`
- **23-29 - Life modules**: finance ledger, business notes, travel packs,
  family events, health (info-only, never diagnoses), vision, comms
  (drafts-never-send). `rolex/life/`
- **30 - Smart Home VI2**: device registry + on/off NL + **danger-lock**
  (unlock/alarm-off/thermostat-max always ask, never silently ignored).
  `rolex/smarthome/engine.py`
- **31 - Device Mgmt**: battery/storage/describe with honest platform
  replies. `rolex/device/manager.py`
- **20 - Sync/Backup**: zip backup/verify/restore + rclone/rsync push to
  VPS/Drive, confirm-gated. `rolex/sync/engine.py`
- **21 - Remote Lab**: TCP/JSON server, SHA-256 token pairing, unauthed
  emergency stop (safety valve). `rolex/remote_lab/server.py`
- **12 - Voice Modulation**: JARVIS / ASSISTANT / NARRATOR profiles,
  ask()-routable ("set voice to jarvis"). `rolex/voice/modulation.py`
- **14/36 - Android + Termux**: Horizon Kivy UI (gold + crown, Jarvis TTS on
  every reply, todo chip), TTS fallback chain, termux-tts support.
  `rolex/ui/android_ui.py`
- **UI FLAGSHIP - Horizon HUD**: best-in-class unique web UI - boot splash
  with crown, pulsing voice orb, gold-on-deep-space chat with LOCAL/AI/OFFLINE
  meta tags, 16-module telemetry grid, dashboard (todos/memory/knowledge/
  plans), voice-profile switcher, settings (Serper/danger-lock/local-first),
  diagnostics view. Pure stdlib bridge on port 8777.
  `rolex/ui/web/` + `rolex/ui/bridge.py`
- **Router**: 16-step local-first ask() routing, every optional module
  wrapped in safe_parse() (a module exception = "skipped", never a crash).
  `rolex/assistant.py`
- **Tests**: `tests/test_v2_modules.py` (57) - module + routing + regression
  coverage; caught and fixed 3 real product bugs (content-matched memory
  forget, smarthome danger NL routing, unauthed remote stop).

---

## Final deliverables

- `README.md` - bilingual quick start & overview (v2)
- `ROADMAP.md` - this file
- `ARCHITECTURE.md` - system diagram & 16-step routing (v2)
- `run.py` - desktop CLI (`REPL` / `--self-test` / `--demo`)
- `python -m rolex.ui.bridge` - Horizon HUD web UI (port 8777)
- `buildozer -v android debug` / GitHub Actions tag - APK v2.2.0
- `ROLEX_AI_v2.2.0.zip` - packaged project (source + HUD + tests + docs,
  runtime `data/` excluded)

**Scratch -> stable core -> complete Rolex -> v2 Horizon -> final APK.
Mudichathu. OK**

