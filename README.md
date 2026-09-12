# 👑 ROLEX AI — Your Personal Intelligence System

**`ஒரு personal AI assistant — scratch-la irundhu build panna, local-first, privacy-first. Android APK varaikkum ready. v2: Horizon HUD, Jarvis voice, life modules, smart home.`**

ROLEX is a complete personal intelligence system built **from scratch**: it does
its own math, keeps its own knowledge base, remembers you locally, learns
safely, talks and listens (Jarvis-style), runs your life modules, controls your
smart home, and finally ships as an Android app or a **best-in-class web HUD**.
No old code was copied — every module is new, tested, and wired into one
assistant.

> **Identity**: ROLEX · `v2.2.0` · wake word **"Hey Guru"** · voice **JARVIS**
> **UI**: **Horizon HUD** (web) + Horizon Kivy (Android) — original gold identity,
> *not* an Autobots clone

---

## ⚡ The One Rule (design philosophy)

```
Calculation → ROLEX does it LOCALLY. ⚡
AI / Internet → ONLY when external information is truly needed.
```

Math, engineering, unit conversion, knowledge, memory, reminders, documents,
tasks, plans, finance, family, travel, health info, comms drafts, smart home —
all run **100% on-device** (SQLite + Python stdlib). Cloud AI (OpenAI / Gemini /
Ollama) and web APIs (Open-Meteo / Serper) are *intelligence sources* Rolex
consults **only** when it genuinely needs outside info, and every one of them is
**optional** — with no keys and no network Rolex still answers from its local
cache and knowledge. The user-facing final answer is **always Rolex's own**.

---

## 🚀 Quick start (desktop)

```bash
# no dependencies required — pure Python 3.11 stdlib
python run.py                 # interactive cockpit REPL
python run.py --self-test     # full diagnostics + health report
python run.py --demo          # scripted working demo
python -m pytest tests/ -q    # 267 tests across 17 files
```

## 🖥️ Horizon HUD — the web UI (v2 flagship)

```bash
python -m rolex.ui.bridge     # → http://127.0.0.1:8777
```

Open the URL in any browser: boot splash with the crown, a pulsing voice orb
with live waveform, gold-on-deep-space chat stream with LOCAL / AI / OFFLINE
meta tags, real-time telemetry (16-module grid), a dashboard with your todos /
memory / knowledge / plans, one-tap voice profile switching (Jarvis /
Assistant / Narrator), settings for all optional API keys + danger-lock + local-first
mode, and a live diagnostics view. No build tools, no npm — pure stdlib server
(`rolex/ui/bridge.py`) + hand-crafted HTML/CSS/JS.

## 📱 Android APK

```bash
pip install buildozer cython
buildozer -v android debug     # → bin/rolex-2.2.0-debug.apk
```

Or push a `v*` tag and **GitHub Actions** (`.github/workflows/build-apk.yml`)
runs the **full 267-test suite**, then builds and attaches the APK
automatically. The on-device UI is the **Horizon Kivy cockpit** (gold + crown,
Jarvis TTS on every reply, todo chip in the status bar). See
[docs/ANDROID_OPTIMIZATION.md](docs/ANDROID_OPTIMIZATION.md) for battery / RAM
strategy (LOCAL-first routing, 1 Hz UI clock, opt-in wakelock, minimal
permissions).

---

## 🔑 Optional API keys (all of them!)

Every key is **optional** — Rolex runs 100% local with zero keys. Add keys to
upgrade specific features; final answers are always Rolex's own.

| Key | Feature | Without key |
|---|---|---|
| `GEMINI_API_KEY` | AI intelligence source | local brain handles it |
| `OPENAI_API_KEY` | AI intelligence source | local brain handles it |
| `OLLAMA_BASE_URL` | local LLM source | local brain handles it |
| `SERPER_API_KEY` | Google web search | cache/offline-safe replies |
| `TAVILY_API_KEY` | web search fallback | (serper missing → tavily) |
| `OPENWEATHER_API_KEY` | richer weather source | Open-Meteo keyless |
| `ELEVENLABS_API_KEY` | premium voice TTS | pyttsx3 / espeak local |

**Way 1 — HUD (easiest, live pickup, no restart):**
open `http://127.0.0.1:8777` → **Settings** → paste key → **SAVE**.
Keys land in `data/secrets.json` (OS-key encrypted, HMAC-verified, 600 perms)
and are picked up immediately.

**Way 2 — `.env` file:**
```bash
cp .env.example .env     # then fill keys
```

**Way 3 — environment variables:**
```bash
export GEMINI_API_KEY="..."
export SERPER_API_KEY="..."
```

## 📱 Run on your phone (3 ways)

**1. Termux (no PC needed, fully local):**
```bash
pkg install python git espeak
git clone <your-repo> rolex   # or unzip ROLEX_AI_v2.2.0.zip
cd rolex
python run.py                # text+voice cockpit
python -m rolex.ui.bridge    # → http://127.0.0.1:8777 in phone browser
```

**2. Android APK (native Kivy cockpit):** see APK section below.

**3. PC bridge + phone browser (same Wi-Fi):**
```bash
python -m rolex.ui.bridge    # binds 0.0.0.0 by default
# find PC IP: ipconfig (Windows) / ip a (Linux)
# phone browser → http://<PC-LAN-IP>:8777
```

## 🏗️ What's inside (v2.0)

### Core (v1 phases, kept and hardened)

| # | Module | What it does | Key files |
|---|--------|--------------|----------|
| 1 | Foundation | config, `.env`, logging, error handling | `rolex/config.py` |
| 2 | Rolex Core | identity, state, lifecycle, events | `rolex/core/` |
| 3 | Local Brain | Tamil/English/Tanglish NLU, intents | `rolex/brain/` |
| 4 | Math & Engineering | ±×÷, algebra, geometry, trig, units, Ohm, motors — local ⚡ | `rolex/math_engine/` |
| 5 | Knowledge Engine | local KB (7 domains, 51 entries), searchable | `rolex/knowledge/` |
| 6 | AI Hub | OpenAI + Gemini + Ollama — **optional** sources | `rolex/ai/` |
| 7 | Answer Engine | fact consistency, confidence → ONE Rolex answer | `rolex/answer_engine/` |
| 8 | Memory | short/long-term SQLite, prefs, search, **content-matched forget** | `rolex/memory/` |
| 9 | Learning | Learn→Sandbox→Test→Approve→Apply→Rollback | `rolex/learning/` |
| 10 | Automation | reminders, recurring tasks, triggers | `rolex/automation/` |
| 11 | Tools | filesystem, documents, coding — permission-gated | `rolex/tools/` |
| 12 | Documents | TXT/MD/PDF/DOCX/XLSX/PPTX/CSV/JSON | `rolex/documents/` |
| 13 | Voice + Vision | "Hey Guru" wake word, fuzzy STT, TTS, camera | `rolex/voice/` |
| 14 | Security | permissions, secrets, audit, emergency stop | `rolex/security/` |

### New in v2.0 (the blueprint's §5–§47 modules)

| § | Module | What it does | Key files |
|---|--------|--------------|----------|
| 9 | Task Manager | NL todo board — add/complete/update/prioritize, ordinals, Tamil | `rolex/tasks/manager.py` |
| 10 | Planning Engine | goal→steps templates, execute hooks, progress | `rolex/planning/engine.py` |
| 6/32 | Live Info | **Open-Meteo weather (no key)** + Serper search (optional) + SQLite cache | `rolex/live/engine.py` |
| 23 | Finance | spent/track/budget, local ledger | `rolex/life/finance.py` |
| 24 | Business | ideas, reminders draft, notes | `rolex/life/business.py` |
| 25 | Travel | plan skeleton, checklist, packing | `rolex/life/travel.py` |
| 26 | Family | birthdays, events, important days | `rolex/life/family.py` |
| 27 | Health | **info-only** — never diagnoses, never prescribes | `rolex/life/health.py` |
| 28 | Vision | camera/image notes when PIL present | `rolex/life/vision.py` |
| 29 | Comms | **drafts-never-send** message drafts | `rolex/life/comms.py` |
| 30 | Smart Home VI2 | device registry, on/off NL, **danger-lock** (unlock/alarm always ask) | `rolex/smarthome/engine.py` |
| 31 | Device Mgmt | battery/storage/describe — honest platform replies | `rolex/device/manager.py` |
| 20 | Sync / Backup | zip backup/restore + rclone/rsync push (VPS/Drive, confirm-gated) | `rolex/sync/engine.py` |
| 21 | Remote Lab | TCP/JSON server, SHA-256 token pairing, **unauthed emergency stop** | `rolex/remote_lab/server.py` |
| 12 | Voice Modulation | **JARVIS / ASSISTANT / NARRATOR** profiles, ask()-routable | `rolex/voice/modulation.py` |
| 14/36 | Android + Termux | Kivy Horizon UI, TTS fallback chain, termux-tts | `rolex/ui/android_ui.py` |
| E | **Horizon HUD** | web UI + stdlib bridge — the flagship UI | `rolex/ui/web/`, `rolex/ui/bridge.py` |

---

## 🗣️ Talk to it

```
🧑 what is 12 * 8 + 4
👑 ⚡ 100   [LOCAL·math·1.00]

🧑 hey guru, ohms law 12V 2A
👑 ⚡ V = 12 V · I = 2 A → R = 6 Ω   [LOCAL·math·1.00]

🧑 chennai la weather enna
👑 🌤 Chennai: 33.3°C · feels 36° · wind 12 km/h   [LIVE·weather·0.90]

🧑 add task buy milk tomorrow, priority urgent
👑 📝 Rolex added: buy milk tomorrow (a1b2c3)   [LOCAL·task·0.95]

🧑 make a plan for trip to ooty this weekend
👑 🧭 Plan created: trip to ooty — 6 steps   [LOCAL·plan·0.95]

🧑 remember that my bike is black and gold
👑 💾 Rolex-க்கு நினைவில் · remembered   [LOCAL·memory·0.95]

🧑 unlock front door
👑 🔓-danger locked: needs explicit permission — confirm பண்ணுவேன்   [LOCAL·smarthome·0.90]

🧑 set voice to jarvis
👑 🎙 Jarvis modulation ON — as you wish, sir.   [LOCAL·voice·1.00]

🧑 வணக்கம் guru
👑 👑 வணக்கம்! Rolex ready.   [LOCAL·greeting·0.99]
```

`Tamil/Tanglish pesalam`: "5 perukku 3", "25 சதவீதம் 200", "metha 12 vaagai 4",
"வணக்கம்", "வானிலை சென்னை".

## 🛰️ The one entry point — 16-step router

Everything funnels through **`RolexAssistant.ask(text)`** (`rolex/assistant.py`):

```
math ⚡ → commands → memory NL → voice profile → tasks → planning →
reminders → life (finance/business/travel/family/health/comms) →
smarthome → device → weather → search → sync → documents →
knowledge → AI-hub (optional) → offline cache
```

```python
from rolex.assistant import get_assistant
a = get_assistant()
a.startup()
res = a.ask("what is 9 squared")   # AskResult(text, route, confidence, local, seconds)
```

Every optional module is wrapped in `safe_parse()` — an exception in any one
module can never crash the assistant (§33 resilience): it just means that
module skipped.

## 🔐 Security model

- **Permissions**: every sensitive tool action is allow/ask/deny-gated
  (`data/permissions.json`); unknown actions default to *ask*.
- **Danger-lock (§30)**: unlock / alarm-off / thermostat-max always require
  explicit confirmation — and are never *silently ignored*.
- **Drafts-never-send (§29)**: comms module drafts messages; sending stays yours.
- **Health info-only (§27)**: health module informs, never diagnoses.
- **Audit**: append-only JSONL of every gated action (`data/logs/audit.jsonl`).
- **Secrets**: AES-style authenticated encryption (SHA256-CTR + HMAC-SHA256).
- **Emergency stop**: `data/EMERGENCY_STOP` halts gated actions — and the
  remote lab honors it **unauthenticated** (safety valve, §21/33).
- **Crash guard + backups**: markers around risky ops; one-command zip + restore.

## 📂 Project tree

```
rolex/               # the assistant
  core/  brain/  math_engine/  knowledge/  ai/  answer_engine/
  memory/  learning/  automation/  tools/  documents/  voice/  security/
  tasks/  planning/  live/  life/  smarthome/  device/  sync/  remote_lab/
  assistant.py       # RolexAssistant facade + 16-step router
  ui/                # Horizon HUD (web/) + Horizon Kivy (android_ui.py) + bridge.py
main.py              # Android entry (buildozer)
run.py               # desktop CLI (REPL / --self-test / --demo)
buildozer.spec       # APK build config (v2.2.0)
.github/workflows/   # CI: 267 tests + APK on every tag
tests/               # 267 tests, 17 files
docs/                # ANDROID_OPTIMIZATION.md
data/                # runtime state (gitignored)
knowledge/           # local KB JSON (7 topics, 51 entries)
```

## ✅ Verified

- **267 tests / 17 files — all passing** (198 legacy + 69 v2)
- **Self-test: 100/100 HEALTHY** (10 health checks)
- **LIVE end-to-end**: Chennai weather via Open-Meteo answered through the HUD
- 16-step router verified live — every route answers
- Product bugs caught & fixed by the v2 suite: content-matched memory forget
  (§2.4), smarthome danger NL routing (§30), unauthed remote stop (§21/33)
- Backup→destroy→restore roundtrip proven; secrets tamper detection proven

## 📄 License / credits

Built to spec: *ROLEX AI 47-section master blueprint* — scratch build, nothing
copied from the old reference archive, nothing missed from the specification.
Original identity: **gold + crown**, not an Autobots clone.
