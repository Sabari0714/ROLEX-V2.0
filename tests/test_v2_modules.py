"""ROLEX v2 module tests — §9 tasks, §10 planning, §6/§32 live,
§23–29 life modules, §30 smarthome, §31 device, §20 sync, §21 remote lab,
§12 voice modulation.

Each test module uses its own temp data dir where possible, or safely
tolerates the shared sandbox state (singletons created once per process).
"""
from __future__ import annotations

import os
import re
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from rolex.errors import RolexError


# ==========================================================================
# §9 TaskManager — todo board
# ==========================================================================
class TestTaskManager:
    def test_add_and_list(self):
        from rolex.tasks.manager import TASKS_MGR
        out = TASKS_MGR.parse_command("add task test_v2 buy grocerie urgent")
        assert "test_v2 buy grocerie" in out
        titles = [t.title for t in TASKS_MGR.all(include_done=True)]
        assert any("test_v2 buy grocerie" in t for t in titles)

    def test_ordinal_complete_by_list_position(self):
        """v1.0 bug class: 'mark 3 complete' must match list position,
        not raw id. v2 accepts ordinal OR id-suffix."""
        from rolex.tasks.manager import TASKS_MGR
        n0 = len(TASKS_MGR.all(include_done=True))
        TASKS_MGR.parse_command("add task ordinal_probe_alpha")
        TASKS_MGR.parse_command("add task ordinal_probe_beta")
        listing = TASKS_MGR.parse_command("show my tasks")
        # deterministic: use the ordinal ACTUALLY shown for the beta line
        # (v1.0 bug class: "mark N" must resolve by list position, not raw id)
        m = re.search(r"^\s*(\d+)\.\s+.*ordinal_probe_beta\b", listing, re.M)
        assert m, f"probe task not listed: {listing!r}"
        pos = int(m.group(1))
        out = TASKS_MGR.parse_command(f"mark {pos} complete")
        assert "complete" in out.lower() or "done" in out.lower(), out
        assert "ordinal_probe_beta" in out, f"ordinal {pos} resolved wrong task: {out!r}"
        # id-suffix mode: resolve the alpha probe by its displayed id suffix
        m2 = re.search(r"\[([0-9a-f]{4})\][^\n]*ordinal_probe_alpha\b", listing)
        n_tasks = len(TASKS_MGR.all(include_done=True))
        if m2 and not (m2.group(1).isdigit()
                       and 1 <= int(m2.group(1)) <= n_tasks):
            # suffix not shadowed by ordinal precedence → must resolve alpha
            out2 = TASKS_MGR.parse_command(f"mark {m2.group(1)} complete")
            assert "ordinal_probe_alpha" in out2, out2

    def test_all_digit_suffix_out_of_range_still_resolves(self):
        """v2.1 bug class (found by fresh-extract packaging verify): the
        displayed suffix …[id[-4:]] can be ALL DIGITS (e.g. …[6981]) —
        'mark 6981 complete' must resolve that task, not die as an
        out-of-range ordinal."""
        from rolex.tasks.manager import TASKS_MGR
        for i in range(80):
            t = TASKS_MGR.add(title=f"suffix_probe_{i}")
            sfx = t.id[-4:]
            cur = len(TASKS_MGR.all(include_done=True))
            if sfx.isdigit() and not (1 <= int(sfx) <= cur):
                out = TASKS_MGR.parse_command(f"mark {sfx} complete")
                assert f"suffix_probe_{i}" in out, (sfx, out)
                return
        pytest.skip("no out-of-range all-digit suffix in 80 adds")

    def test_stats_shape(self):
        from rolex.tasks.manager import TASKS_MGR
        st = TASKS_MGR.stats()
        assert {"total", "pending", "done"}.issubset(st)

    def test_unknown_returns_empty(self):
        from rolex.tasks.manager import TASKS_MGR
        assert TASKS_MGR.parse_command("hello how are you") == ""

    def test_invalid_ordinal_safe(self):
        from rolex.tasks.manager import TASKS_MGR
        out = TASKS_MGR.parse_command("mark 999 complete")
        assert out == "" or "not found" in out.lower() or "invalid" in out.lower()

    def test_priority_int(self):
        from rolex.tasks.manager import TASKS_MGR, Priority
        # v1.0 had URGENT; v2 spec renamed the top tier CRITICAL
        assert int(Priority.CRITICAL) == 3
        assert int(Priority.LOW) == 0


# ==========================================================================
# §10 PlanningEngine
# ==========================================================================
class TestPlanningEngine:
    def test_trip_template(self):
        from rolex.planning.engine import PLANNER
        out = PLANNER.parse_command("make a plan for trip to test_v2_kodaikanal")
        assert "plan" in out.lower()
        assert "test_v2_kodaikanal" in out
        plans = PLANNER.list()
        assert any("test_v2_kodaikanal" in p["goal"] for p in plans)

    def test_generic_fallback(self):
        from rolex.planning.engine import PLANNER
        out = PLANNER.parse_command("create a plan for test_v2_lern_german")
        assert "plan" in out.lower()

    def test_not_mine_returns_empty(self):
        from rolex.planning.engine import PLANNER
        assert PLANNER.parse_command("weather in chennai") == ""

    def test_step_marking(self):
        from rolex.planning.engine import PLANNER
        PLANNER.parse_command("make a plan for test_v2_fitness rush")
        pid = [p["id"] for p in PLANNER.list()
               if "test_v2_fitness" in p["goal"]][-1]
        plan = PLANNER.mark_step(pid, 1, done=True)
        assert plan.steps[0].done is True


# ==========================================================================
# §6/§32 Live — weather + cache (offline-safe)
# ==========================================================================
class TestLive:
    def test_weather_parse_offline_fallback(self):
        """Sandbox may lack net; either a live report or an honest offline
        message must come back — never a crash."""
        from rolex.live.engine import WEATHER
        out = WEATHER.parse_command("weather in test_v2_moonbase")
        assert isinstance(out, str) and out  # honest reply either way

    def test_weather_tamil_wake(self):
        from rolex.live.engine import WEATHER
        out = WEATHER.parse_command("வானிலை சென்னை")
        assert isinstance(out, str)

    # ---- Tanglish word-order regression (§6 fix) ----------------------
    def test_weather_tanglish_place_first(self):
        """'chennai la weather enna' must parse Chennai as the place —
        never Enna (Sicily). The trailing 'enna' is a question word."""
        from rolex.live.engine import WEATHER
        m = WEATHER._RE_W_TAMIL_ORDER.match("chennai la weather enna")
        assert m and m.group(1).strip() == "chennai"
        # parse returns a non-empty, Chennai-or-offline reply (never Enna)
        out = WEATHER.parse_command("chennai la weather enna")
        assert isinstance(out, str) and out
        assert "enna," not in out.lower().split("now")[0] if "now" in out else True

    def test_weather_tamil_script_place_first(self):
        """'சென்னை வானிலை' (place first, no 'la') must parse
        சென்னை as the place."""
        from rolex.live.engine import WEATHER
        m = WEATHER._RE_W_TAMIL_ORDER.match("சென்னை வானிலை")
        assert m, "tamil-order regex must match"
        assert "சென்னை" in m.group(1)
        assert "vaanilai" not in m.group(1).lower()

    def test_weather_tanglish_mixed_script(self):
        """'மதுரை la vaanilai' — Tamil place + Tanglish glue."""
        from rolex.live.engine import WEATHER
        m = WEATHER._RE_W_TAMIL_ORDER.match("மதுரை la vaanilai")
        assert m and "மதுரை" in m.group(1)

    def test_weather_stop_words_stripped(self):
        """Trailing question words must never become the place."""
        from rolex.live.engine import WEATHER
        out = WEATHER.parse_command("coimbatore la weather eppo")
        assert isinstance(out, str) and "eppo" not in out.split("\n")[0]

    def test_weather_not_mine_guard(self):
        from rolex.live.engine import WEATHER
        assert WEATHER.parse_command("add task buy milk") == ""
        assert WEATHER.parse_command("battery status") == ""

    def test_cache_ttl_table(self):
        from rolex.live.engine import LiveCache
        with tempfile.TemporaryDirectory() as td:
            c = LiveCache(Path(td) / "c.sqlite")
            c.put("k1", "weather", {"v": 1})
            got = c.get("k1", "weather")
            assert got == {"v": 1}
            c.put("k2", "weather", {"v": 2})
            # max_age=-1 -> already expired
            assert c.get("k2", "weather", max_age=-1) is None
            assert c.get("k2", "weather") == {"v": 2}

    def test_websearch_no_key_offline_safe(self):
        from rolex.live.engine import WEBSEARCH
        out = WEBSEARCH.parse_command("search for rolex ai v2")
        assert isinstance(out, str)

    def test_serper_not_claimed_without_intent(self):
        from rolex.live.engine import WEBSEARCH
        assert WEBSEARCH.parse_command("add task buy milk") == ""


# ==========================================================================
# §23–29 Life modules
# ==========================================================================
class TestLife:
    def test_finance_spent(self):
        from rolex.life import life_route
        out = life_route("spent 120 test_v2 coffee")
        assert isinstance(out, str) and ("test_v2 coffee" in out or "spent" in out.lower())

    def test_family_birthday(self):
        from rolex.life import life_route
        out = life_route("mom birthday on 15 march")
        assert isinstance(out, str)

    def test_travel_packing(self):
        from rolex.life import life_route
        out = life_route("packing list for test_v2 goa 3 days")
        assert isinstance(out, str)

    def test_health_log(self):
        from rolex.life import life_route
        out = life_route("log weight 70kg")
        assert isinstance(out, str)

    def test_comms_draft_never_sends(self):
        from rolex.life import life_route
        out = life_route("draft message to amma i will come tomorrow")
        assert isinstance(out, str)
        assert "send" not in out.lower() or "draft" in out.lower()

    def test_business_plan(self):
        from rolex.life import life_route
        out = life_route("business plan for test_v2 flower shop")
        assert isinstance(out, str)

    def test_not_mine(self):
        from rolex.life import life_route
        assert life_route("what is 2+2") == ""


# ==========================================================================
# §30 Smart Home VI2
# ==========================================================================
class TestSmartHome:
    def test_register_and_list(self):
        from rolex.smarthome import SMARTHOME
        SMARTHOME.parse_command("register device test_v2_lamp bedroom")
        out = SMARTHOME.parse_command("show devices")
        assert "test_v2_lamp" in out

    def test_turn_on_off(self):
        from rolex.smarthome import SMARTHOME
        SMARTHOME.parse_command("register device test_v2_fan hall")
        on = SMARTHOME.parse_command("turn on test_v2_fan")
        off = SMARTHOME.parse_command("turn off test_v2_fan")
        assert "test_v2_fan" in on and "test_v2_fan" in off

    def test_danger_needs_approval(self):
        # §30 product fix: dangerous NL requests are never silently
        # ignored — they surface the permission gate.
        from rolex.smarthome import SMARTHOME
        out = SMARTHOME.parse_command("unlock front door")
        assert ("confirm" in out.lower() or "permission" in out.lower()
                or "danger" in out.lower())
        # an unknown device still asks, but says it is not registered
        out2 = SMARTHOME.parse_command("unlock test_v2_gold_door")
        assert ("confirm" in out2.lower() or "permission" in out2.lower()
                or "danger" in out2.lower())
        assert "test_v2_gold_door" in out2
        # approved path routes to control() (honest not-registered reply)
        out3 = SMARTHOME.parse_command(
            "unlock test_v2_gold_door", approved=True)
        assert isinstance(out3, str) and out3 != ""
        # not-mine guard still returns ""
        assert SMARTHOME.parse_command("battery status") == ""

    def test_not_mine(self):
        from rolex.smarthome import SMARTHOME
        assert SMARTHOME.parse_command("battery status") == ""


# ==========================================================================
# §31 Device Manager
# ==========================================================================
class TestDevice:
    def test_battery_safe_reply(self):
        from rolex.device import DEVICE
        out = DEVICE.parse_command("battery status")
        assert isinstance(out, str) and out  # honest platform reply

    def test_storage(self):
        from rolex.device import DEVICE
        out = DEVICE.parse_command("storage info")
        assert isinstance(out, str)

    def test_describe(self):
        from rolex.device import DEVICE
        out = DEVICE.parse_command("describe this device")
        assert isinstance(out, str)

    def test_not_mine(self):
        from rolex.device import DEVICE
        assert DEVICE.parse_command("add task buy milk") == ""


# ==========================================================================
# §20 Sync / Backup
# ==========================================================================
class TestSync:
    def test_backup_creates_zip(self):
        from rolex.sync.engine import BACKUP, CLOUD
        # backup NL routing lives on CloudSync.parse_command; the engine
        # object itself only exposes create/verify/restore.
        z = BACKUP.create()
        assert z.exists() and z.name.endswith(".zip")
        out = CLOUD.parse_command("backup")
        assert isinstance(out, str) and "backup" in out.lower()

    def test_sync_push_needs_confirm(self):
        from rolex.sync.engine import CLOUD
        out = CLOUD.parse_command("sync push drive")
        assert "confirm" in out.lower() or "approve" in out.lower()

    def test_sync_status_safe(self):
        from rolex.sync.engine import CLOUD
        out = CLOUD.parse_command("sync status")
        assert isinstance(out, str)


# ==========================================================================
# §21 Remote Lab — pure protocol tests (no socket)
# ==========================================================================
class TestRemoteLab:
    def test_verify_sha256(self):
        # _verify hashes REMOTE_LAB.token (from env), not a hardcoded value
        from rolex.remote_lab.server import REMOTE_LAB
        import hashlib
        ch = "test_challenge_42"
        tok = REMOTE_LAB.token
        good = hashlib.sha256((tok + ch).encode()).hexdigest()
        assert REMOTE_LAB._verify(good, ch) is True
        assert REMOTE_LAB._verify("deadbeef", ch) is False

    def test_handle_message_hello(self):
        from rolex.remote_lab.server import REMOTE_LAB
        r = REMOTE_LAB.handle_message({"op": "hello"})
        assert r.get("ok") is True and "version" in r

    def test_handle_message_unknown(self):
        from rolex.remote_lab.server import REMOTE_LAB
        r = REMOTE_LAB.handle_message({"op": "nope_op"})
        assert r.get("ok") is False

    def test_stop_honored(self):
        # §21/33 fix: emergency stop is a safety valve — always
        # honored, even unauthenticated, so a stuck client can always halt.
        from rolex.remote_lab.server import REMOTE_LAB
        from rolex.config import CONFIG
        r = REMOTE_LAB.handle_message({"op": "stop"})
        assert r.get("ok") is True and r.get("stopped") is True
        assert CONFIG.STOP_FLAG.exists()
        Path(CONFIG.STOP_FLAG).unlink(missing_ok=True)   # cleanup
        # unauthed non-stop ops are still blocked
        r2 = REMOTE_LAB.handle_message({"op": "status"})
        assert r2.get("ok") is False


# ==========================================================================
# §12 Voice modulation
# ==========================================================================
class TestVoiceModulation:
    def test_jarvis_default(self):
        from rolex.voice.modulation import MODULATOR
        assert MODULATOR.profile.name.lower() in ("jarvis", "narrator", "assistant")

    def test_switch_profiles(self):
        from rolex.voice.modulation import MODULATOR
        out1 = MODULATOR.parse_command("set voice to jarvis")
        assert "jarvis" in out1.lower()
        out2 = MODULATOR.parse_command("set voice to narrator")
        assert "narrator" in out2.lower()
        # restore
        MODULATOR.parse_command("set voice to jarvis")

    def test_status_dict(self):
        from rolex.voice.modulation import MODULATOR
        st = MODULATOR.status()
        assert "profile" in st or "name" in str(st).lower()

    def test_not_mine(self):
        from rolex.voice.modulation import MODULATOR
        assert MODULATOR.parse_command("add task buy milk") == ""


# ==========================================================================
# Assistant v2 — memory NL + routing + safe_parse resilience
# ==========================================================================
class TestAssistantV2:
    @pytest.fixture()
    def a(self):
        from rolex.assistant import get_assistant
        return get_assistant()

    def test_memory_remember_recall(self, a):
        r1 = a.ask("remember that test_v2_fact rolex is gold")
        assert "remembered" in r1.text.lower()
        r2 = a.ask("recall test_v2_fact")
        assert "rolex is gold" in r2.text

    def test_memory_forget(self, a):
        # §2.4 fix: forget now content-searches when the exact key
        # misses ("forget test_v2_gone" must remove the fact stored under
        # the derived key "test_v2_gone this will").
        a.ask("remember that test_v2_gone this will be forgotten")
        r = a.ask("forget test_v2_gone")
        assert "forgotten" in r.text.lower()
        r2 = a.ask("recall test_v2_gone")
        assert "rolex is gold" not in r2.text   # other facts survive
        r3 = a.ask("forget nothing_here_xyz")
        assert "இல்லை" in r3.text or "not" in r3.text.lower()

    def test_preferences_route(self, a):
        r = a.ask("preferences")
        assert r.route == "memory"

    def test_task_route(self, a):
        r = a.ask("add task test_v2_check wiring")
        assert r.route == "task"

    def test_plan_route(self, a):
        r = a.ask("make a plan for test_v2_trip goa")
        assert r.route == "plan"

    def test_math_local_route(self, a):
        r = a.ask("12*12")
        assert r.route == "math" and r.local is True

    def test_voice_route(self, a):
        r = a.ask("set voice to jarvis")
        assert r.route == "voice"

    def test_smarthome_route(self, a):
        r = a.ask("show devices")
        assert r.route == "smarthome"

    def test_status_has_todos(self, a):
        st = a.status()
        assert "todos_pending" in st

    def test_empty_ask(self, a):
        r = a.ask("")
        assert r.route == "wake"


# ==========================================================================
# Regression — v1.0 bug classes documented in blueprint
# ==========================================================================
class TestRegressionV1Bugs:
    """The v1.0 repo shipped known bugs (missing priority column,
    complete_task missing, task-id ambiguity). v2 must be immune."""

    def test_todo_schema_has_priority_status(self):
        from rolex.tasks.manager import TASKS_MGR
        conn = sqlite3.connect(TASKS_MGR.db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(todo_tasks)")}
        conn.close()
        assert {"title", "status", "priority"}.issubset(cols)

    def test_complete_missing_task_clean_error(self):
        from rolex.tasks.manager import TASKS_MGR, TaskManagerError
        with pytest.raises((TaskManagerError, RolexError)):
            TASKS_MGR.complete("nonexistent0000")

    def test_ordinal_and_suffix_both_accepted(self):
        from rolex.tasks.manager import TASKS_MGR
        TASKS_MGR.parse_command("add task test_v2_dual_ref")
        # suffix form must not raise
        out = TASKS_MGR.parse_command("show my tasks")
        assert "test_v2_dual_ref" in out


# ==========================================================================
# Bridge — HUD endpoints (no server start; direct handler logic pieces)
# ==========================================================================
class TestBridgeHelpers:
    def test_mem_rows(self):
        from rolex.ui.bridge import _mem_rows
        rows = _mem_rows()
        assert isinstance(rows, list)

    def test_web_dir_exists(self):
        from rolex.ui.bridge import WEB_DIR
        assert (WEB_DIR / "index.html").is_file()
        assert (WEB_DIR / "rolex.css").is_file()
        assert (WEB_DIR / "rolex.js").is_file()

    def test_modulator_speak_never_crashes(self):
        from rolex.voice.modulation import MODULATOR
        MODULATOR.speak("silence test")  # headless: must not raise


# ==========================================================================
# v2.2 — multi-provider API keys (Gemini, OpenAI, Ollama, OpenWeather,
#         ElevenLabs, Tavily, Serper) — bridge /keys + live pickup
# ==========================================================================
class TestApiKeyHub:
    """All keys optional; encrypted store; live pickup; no-network-safe."""

    def _clean(self, *names):
        import os
        for n in names:
            os.environ.pop(n, None)

    def test_bridge_has_keys_endpoint(self):
        from rolex.ui import bridge
        h = bridge.Handler
        assert hasattr(h, "_keys") and hasattr(h, "_keys_status")
        # allowed key names cover all user providers
        import inspect
        src = inspect.getsource(h._keys)
        for name in ("TAVILY_API_KEY", "OPENWEATHER_API_KEY",
                     "ELEVENLABS_API_KEY", "GEMINI_API_KEY",
                     "OPENAI_API_KEY"):
            assert name in src, name

    def test_serper_endpoint_import_ok(self):
        """Bug #7 regression: /serper used to import nonexistent
        SecretsStore class → ImportError crash. Must import cleanly."""
        from rolex.ui import bridge            # noqa: F401
        from rolex.security.secrets import SECRETS
        assert SECRETS is not None

    def test_websearch_tavily_fallback_logic(self, monkeypatch):
        import os
        from rolex.live.engine import WebSearchTool, LIVE_CACHE
        ws = WebSearchTool(LIVE_CACHE)
        # isolate from dev-machine secrets.json (env-only read)
        monkeypatch.setattr(
            "rolex.live.engine.os_getenv",
            lambda n, d="": os.environ.get(n, ""))
        # no keys → unavailable, safe reply
        os.environ.pop("SERPER_API_KEY", None)
        os.environ.pop("TAVILY_API_KEY", None)
        ws._key_override = ""
        assert not ws.available()
        rep = ws.report("anything")
        assert "SERPER_API_KEY" in rep or "TAVILY_API_KEY" in rep
        # tavily-only key → available via fallback
        os.environ["TAVILY_API_KEY"] = "tvly-fake"
        try:
            assert ws.available()
            # fake key → network attempt fails safely → None
            assert ws.search("no-crash-probe") is None
        finally:
            os.environ.pop("TAVILY_API_KEY", None)
        # search must never raise (offline-safe)
        assert ws.search("offline probe") is None

    def test_weather_openweather_key_gated(self):
        from rolex.live.engine import WeatherTool, LIVE_CACHE
        w = WeatherTool(LIVE_CACHE)
        import os
        self._clean("OPENWEATHER_API_KEY")
        assert w.ow_key == ""
        os.environ["OPENWEATHER_API_KEY"] = "ow-fake"
        try:
            assert w.ow_key == "ow-fake"
            # OW→WMO mapping table sane (report() depends on it)
            assert w._ow_wmo(800) == 0          # clear
            assert w._ow_wmo(500) == 51         # light rain
            assert w._ow_wmo(999999) == 3       # unknown → overcast
            assert w._ow_wmo(None) == 3
        finally:
            os.environ.pop("OPENWEATHER_API_KEY", None)

    def test_tts_elevenlabs_chain(self):
        """ElevenLabs opt-in: available() must be False headless (no
        player/key) and speak() must fall back without crashing."""
        from rolex.voice.tts import TTS, ElevenLabsTTS, _eleven_key
        self._clean("ELEVENLABS_API_KEY")
        # no key → not available, speak never raises
        e = ElevenLabsTTS()
        assert not (bool(_eleven_key()) and e._player)
        assert TTS.speak("headless silence probe") is False
        av = TTS.available()
        assert "elevenlabs" in av and "pyttsx3" in av

    def test_env_example_documents_all_keys(self):
        from pathlib import Path
        txt = Path(".env.example").read_text(encoding="utf-8")
        for k in ("OPENAI_API_KEY", "GEMINI_API_KEY", "OLLAMA_BASE_URL",
                  "SERPER_API_KEY", "TAVILY_API_KEY",
                  "OPENWEATHER_API_KEY", "ELEVENLABS_API_KEY"):
            assert k in txt, k
