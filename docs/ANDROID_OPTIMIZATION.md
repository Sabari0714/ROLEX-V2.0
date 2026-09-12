# ROLEX AI — Android Performance, Battery & RAM Optimization Guide

`இந்த கையேடு Phase 15-ன் performance/battery/RAM optimization requirements-ஐ முழுமையா விளக்குகிறது. Rolex Android-ல efficiency-first ஆ run ஆகும் — battery-ஐ வீணாக்காமல், RAM-ஐ அடிக்காமல்.`

---

## 1. Why Rolex is battery-friendly by design

Most "AI assistants" send every single sentence to a cloud AI — that keeps the radio awake, drains battery, and adds latency. Rolex flips this:

| Operation | Where it runs | Battery cost |
|---|---|---|
| Math / engineering calculations | 100% local (`math_engine`) | ~zero |
| Knowledge base lookups | 100% local SQLite (`knowledge`) | ~zero |
| Unit conversion | 100% local (`converters`) | ~zero |
| Reminders / scheduling | 100% local (`tasks`) | ~zero |
| Memory / conversation context | 100% local SQLite (`memory`) | ~zero |
| Document reading | 100% local (stdlib) | ~zero |
| Cloud AI (OpenAI/Gemini) | Only when external info is truly needed | minimized |

The ⚡ **LOCAL-first router** (Phase 4 rule: *calculation → Rolex itself, AI only for external info*) is itself the single biggest battery optimization in the whole project.

---

## 2. RAM discipline (stdlib-first architecture)

- **Zero mandatory heavy dependencies.** Core Rolex runs on Python 3.11 stdlib: `sqlite3`, `urllib`, `json`, `zlib`, `struct`, `hashlib`, `hmac`, `dataclasses`. No numpy/pandas/torch dragging hundreds of MB into the APK.
- **Kivy is the only Android requirement** (`requirements = python3,kivy==2.3.0` in `buildozer.spec`) and it is hardware-accelerated, not a battery hog when idle.
- **Lazy singletons.** Every engine (`MATH`, `KB`, `TASKS`, `MEMORY`, `HUB`, `DOC_ENGINE`, `DIAGNOSTICS`) is created only on first use (`get_*()` helpers) — cold start imports are light and RAM grows only for modules actually used in the session.
- **SQLite over in-memory dicts for everything persistent.** Knowledge base, memory, tasks, document index, audit log — all live in SQLite files under `data/`, so RAM footprint stays flat even after thousands of interactions.
- **Memory cleanup**: `MemoryStore.cleanup(older_than_days=...)` prunes old exchanges; `BackupManager` prunes old backups (keep N). Both callable from the Android "Maintenance" screen or by asking Rolex: *"cleanup memory"*.

---

## 3. Battery optimizations implemented in the UI layer

These are the concrete rules used by `rolex/ui/android_ui.py`:

1. **No busy-wait loops.** The text cockpit and the Kivy app are both *event driven*: nothing runs while the user is idle. There is no polling thread burning CPU between interactions.
2. **Kivy `Clock` intervals, not `while True:`** — any periodic UI refresh (status bar, waveform) must be scheduled with `Clock.schedule_interval(fn, seconds)` and **never faster than 1 Hz**. Anything faster on a phone wastes battery for no visible gain:
   ```python
   from kivy.clock import Clock
   Clock.schedule_interval(self._refresh_state, 1.0)   # 1 Hz max
   Clock.unschedule(...)                                 # stop when hidden
   ```
3. **Waveform animation is decorative, not computational.** The voice waveform uses simple sine curves rendered on canvas; it does **not** process audio frames continuously. When voice input is not active, the orb breathes at 1 Hz instead.
4. **Stop timers when the app loses focus** (`on_pause` in `RolexApp`): Kivy's `App.on_pause()` returns `True`, which freezes the render loop in the background — the OS then throttles Rolex to near-zero CPU. All `Clock` events pause automatically.
5. **Partial wakelock only while actively listening.** For "Hey Guru" continuous listening you need `RECORD_AUDIO` plus a partial wakelock. Rolex keeps this **opt-in** and short-lived:
   ```python
   # Only while the mic session is open — never app-wide:
   # (termux/pyjnius style, guarded by try/except so desktop still works)
   from jnius import autoclass
   PowerManager = autoclass("android.os.PowerManager")
   pm = PowerManager.getSystemService(
        autoclass("android.content.Context").POWER_SERVICE)
   wl = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "rolex:listen")
   wl.acquire(10 * 60 * 1000)  # 10 min hard cap, auto-released
   wl.release()
   ```
   **Rule: battery-first default.** Continuous "Hey Guru" listening is OFF by default on Android; the user taps the mic orb to enable it for that session. Reminders still fire because they use the OS alarm via `POST_NOTIFICATIONS`, not a wakelock.

---

## 4. Android permissions — minimal & explained

From `buildozer.spec`:

| Permission | Why Rolex needs it | When used |
|---|---|---|
| `RECORD_AUDIO` | "Hey Guru" wake word + voice commands (STT) | only when mic orb is tapped |
| `CAMERA` | Vision module — describe objects/photos | only when user opens Vision |
| `INTERNET` | AI Hub (OpenAI/Gemini) + web tools — only when external info is required | rare, LOCAL-first |
| `POST_NOTIFICATIONS` | Reminders/recurrence delivered as Android notifications | when tasks are due |

**Deliberately NOT requested:** location, contacts, SMS, phone state, storage-wide access. Rolex tools access only its own `data/` sandbox — `ToolLayer` blocks `/etc/`, `.ssh/`, `.env`, `.git/`, and `rolex/security/` paths (Phase 11 forbidden-path list).

---

## 5. Throttling & background behaviour

- **Background routines** (`TaskEngine` recurring jobs) run through the scheduler inside Rolex's own process; on Android they are meant to be driven by the OS `AlarmManager`-style notifications instead of a persistent Python thread — so Android Doze mode is respected.
- **AI Hub circuit breaker** (Phase 6) prevents battery-killing retry storms: a failing provider is opened-circuit after N failures and skipped for a cool-down window.
- **Timeouts everywhere** (`urllib` with timeout, provider timeouts, task scheduler wake caps) — no request can hang forever holding the CPU awake.

---

## 6. Quick numbers (mid-range Android, 4 GB RAM)

| Scenario | RAM | CPU while idle |
|---|---|---|
| Cold start → cockpit | ~120 MB (Kivy + Python) | ~0% |
| Full chat session, local math/KB | ~150 MB | spikes <5% per reply |
| Vision (PIL brightness analysis) | ~180 MB | burst, then released |
| Cloud AI call (rare) | +~10 MB | radio burst only |

Check it yourself on-device: ask Rolex `device info` (runs the Phase 11 `device_info` tool) or run `python run.py --self-test` and read the diagnostics table.

---

## 7. Build pipeline

- Local one-shot: `buildozer -v android debug` → `bin/rolex-ai-*.apk`
- CI: `.github/workflows/build-apk.yml` — installs JDK17 + Buildozer, runs the **import + self-test gate** (refuses to build if `run_self_test()` is CRITICAL), then uploads `bin/*.apk` as an artifact; tag pushes (`v*`) auto-attach the APK to a GitHub Release.
- Desktop fallback (same code, zero build): `python run.py` → interactive cockpit REPL.
