# ROLEX AI — Architecture

**`எப்படி Rolex work aagudhu — full data flow, one diagram-la.`**

---

## The flow (user spec, implemented exactly)

```
                    ┌──────────────────────────────────────────┐
                    │                U S E R                   │
                    │   text · voice ("Hey Guru") · camera     │
                    └───────────────────┬──────────────────────┘
                                        │
                     ┌──────────────────▼───────────────────┐
                     │            ROLEX CORE                │
                     │  identity · lifecycle · state machine│
                     │  commands · response pipeline · bus  │
                     └──────────────────┬───────────────────┘
                                        │
                          ┌─────────────▼──────────────┐
                          │       INTENT ROUTER       │
                          │  Phase 3 brain + Phase 4  │
                          │  math detector (local ⚡)  │
                          └─────┬──────┬──────┬───────┬┘
                                │      │      │       │
              ┌─────────────────▼┐ ┌───▼────┐ ┌▼──────────────┐
              │   LOCAL BRAIN    │ │ TOOLS  │ │   KNOWLEDGE   │
              │ Tamil/Eng/Tang   │ │ gated  │ │ 51 entries,   │
              │ intents, context │ │ audit  │ │ 7 topics 📘   │
              └─────────────────┘ └───┬────┘ └───────┬───────┘
                                      │              │
                          (external info needed only)
                                      │              │
                     ┌────────────────▼──────────────▼───────────┐
                     │        INTELLIGENCE HUB (parallel)       │
                     │   OpenAI ∥ Gemini ∥ Ollama               │
                     │   health · timeout · retry · circuit     │
                     └────────────────────┬─────────────────────┘
                                          │
                        ┌─────────────────▼─────────────────┐
                        │     VALIDATOR / ANSWER ENGINE     │
                        │  fact consistency · confidence    │
                        │  hallucination check · one final  │
                        └─────────────────┬─────────────────┘
                                          │
                        ┌─────────────────▼─────────────────┐
                        │      ROLEX FINAL ANSWER 🤖        │
                        │   (Rolex owns the final answer)   │
                        └───────┬───────────────────┬───────┘
                                │                   │
                  ┌─────────────▼──────┐   ┌────────▼─────────┐
                  │   MEMORY 🧠        │   │    LEARNING 🎓   │
                  │ SQLite turns/facts │   │ propose→approve  │
                  └────────────────────┘   │ →apply→rollback  │
                                           └──────────────────┘
                                │
                     ┌──────────▼───────────────────┐
                     │            USER              │
                     │  text · TTS voice · UI       │
                     └──────────────────────────────┘
```

Wrapped around everything: **SECURITY 🛡** (permissions, audit, encrypted
secrets, emergency stop, crash guard, backups) and **RELIABILITY**
(diagnostics, self-test 100/100, recovery).

---

## Module map

| Layer | Modules | Responsibility |
|---|---|---|
| Core | `rolex/core/` | identity, state machine, lifecycle, commands, events, response pipeline |
| Brain | `rolex/brain/` | NLU (Tamil/English/Tanglish), intent detection, context, reasoning, conversation flow |
| Math ⚡ | `rolex/math_engine/` | arithmetic, algebra, geometry, trig, units, electrical/mechanical/electronics engineering — always local |
| Knowledge | `rolex/knowledge/` | local searchable KB (JSON + index) |
| AI Hub | `rolex/ai/` | OpenAI/Gemini/Ollama, health, timeout, retry, parallel, circuit breaker |
| Answer | `rolex/answer_engine/` | validation, fact consistency, confidence, hallucination check → ONE final answer |
| Memory | `rolex/memory/` | short-term turns, long-term facts/preferences (SQLite) |
| Learning | `rolex/learning/` | safe Learn→Propose→Backup→Sandbox→Test→Approve→Apply→Rollback |
| Automation | `rolex/automation/` | reminders, schedules, recurring, triggers, history |
| Tools | `rolex/tools/` | filesystem/docs/coding/web/API/device — permission-gated + audited |
| Documents | `rolex/documents/` | 8-format read/search/summarize/create/edit + doc memory |
| Voice+Vision | `rolex/voice/` | wake word, STT, TTS, conversation loop, camera, image analysis |
| Security | `rolex/security/` | permissions, audit, secrets, crash guard, backups, diagnostics |
| UI | `rolex/ui/` | Kivy cockpit + text cockpit (same facade) |
| Facade | `rolex/assistant.py` | **the single entry point** `ask()` used by UI, voice, CLI |
| Entry | `main.py` (Android), `run.py` (desktop) | boot → cockpit |

---

## Routing order (what `ask()` tries, in order - v2 16-step)

0. **Wake word** - "Hey Guru ..." -> strip, continue (empty -> "yes?")
1. **Math** - `MATH.solve()` (conversational prefixes stripped) -> LOCAL
2. **Commands** - whole-utterance system commands (`/status`, `version`, ...)
3. **Memory NL** - remember / recall / forget (content-matched) / preferences
4. **Voice profile** - "set voice to jarvis/assistant/narrator" -> MODULATOR
5. **Tasks (9)** - add/complete/update/prioritize todo board
6. **Planning (10)** - "make a plan for ..." -> steps + progress
7. **Reminders** - natural language -> task registered + persisted
8. **Life (23-29)** - finance/business/travel/family/health-info/comms-drafts
9. **SmartHome (30)** - on/off NL + danger-lock messages (never silent)
10. **Device (31)** - battery/storage/describe honest replies
11. **Weather (6)** - Open-Meteo live (no key) -> cache -> offline notice
12. **Search (6.1)** - Serper (optional key) -> cache -> offline notice
13. **Sync (20)** - backup / sync push (confirm) / restore / sync status
14. **Documents** - "summarize/read/analyze <file>" -> local doc intelligence
15. **Knowledge** - local KB `best()` match -> LOCAL
16. **AI Hub** (only now) - parallel providers -> **Validator** -> final answer;
    offline -> honest KB fallback or explicit offline notice

Every optional module call is wrapped in `safe_parse()` - a module exception
means "skipped", never a crash (33 resilience).

## Data flow & storage

```
knowledge/*.json      7 topics · 51 entries          (read-only source of truth)
data/memory/*.db      conversations + facts + prefs (SQLite, VACUUM cleanup)
data/tasks/tasks.db   reminders/schedules/recurring  (SQLite, cancel/history)
data/documents/*.db   doc index + summaries          (SQLite)
data/logs/            rolex.log + audit.jsonl       (append-only audit)
data/secrets.json     encrypted (CTR keystream+HMAC)
data/backups/*.zip    BackupEngine create/verify/restore/prune
data/tasks/tasks.db   todo board (title, priority, status, due) - 9
data/plans.json       planning engine state + steps - 10
data/live_cache.db    weather/search/geocode cache (offline fallback) - 32
data/smarthome.json   device registry + states - 30
data/life/*.json      finance ledger / family events / travel packs - 23-29
data/crash_markers/   CrashGuard mark/clear/recover
data/permissions.json allow/ask/deny + session approvals
data/EMERGENCY_STOP   emergency halt flag
```

## Key design rules

- **LOCAL-first**: cloud AI is a *source*, never the owner of the final answer
- **stdlib-first**: zero hard dependencies; optional extras auto-detected
- **Everything gated**: sensitive tools → permission + audit
- **Honest degradation**: no mic/TTS/providers? — say so, fall back, never fake
- **One facade**: UI, voice loop, and CLI all share `RolexAssistant.ask()`
- **Test isolation**: tests use temp DBs/dirs; real `data/` never polluted
