"""Rolex Horizon bridge — serves the web HUD + live JSON API.

Pure stdlib. Two jobs:
  1. Serve rolex/ui/web/ (index.html, rolex.css, rolex.js)
  2. POST /ask /status /dash /plans /memory /voice /serper
     → the REAL RolexAssistant v2 (local-first, live weather etc.)

Run:  python -m rolex.ui.bridge       (then open http://127.0.0.1:8777)
"""
from __future__ import annotations

import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ..assistant import get_assistant
from ..logging_setup import get_logger
from ..tasks.manager import TASKS_MGR
from ..planning.engine import PLANNER
from ..memory.store import MEMORY
from ..automation.engine import TASKS
from ..voice.modulation import MODULATOR
from ..knowledge.base import KnowledgeBase

log = get_logger("bridge")
WEB_DIR = Path(__file__).parent / "web"
PORT = int(os.getenv("ROLEX_HUD_PORT", "8777"))

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    assistant = None          # set by serve()

    # ------------------------------------------------------------ silence
    def log_message(self, fmt, *args):           # noqa: A003
        log.debug("hud %s", fmt % args)

    # ------------------------------------------------------------ helpers
    def _json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:                        # noqa: BLE001
            return {}

    # ------------------------------------------------------------ GET
    def do_GET(self):                            # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html", "/hud"):
            return self._file("index.html")
        if path.startswith("/api/health"):
            return self._json({"ok": True, "version": "2.2.0"})
        if path == "/api/keys":
            return self._keys_status()
        name = path.lstrip("/")
        if re.fullmatch(r"[\w.\-]+\.(?:css|js|svg|png|ico|html)", name):
            return self._file(name)
        self._json({"error": "not found"}, 404)

    def _file(self, name: str) -> None:
        p = WEB_DIR / name
        if not p.is_file():
            return self._json({"error": "missing " + name}, 404)
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME.get(p.suffix, "text/plain"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ POST
    def do_POST(self):                           # noqa: N802
        path = urlparse(self.path).path
        data = self._body()
        try:
            if path == "/ask":
                return self._ask(data)
            if path == "/status":
                return self._status()
            if path == "/dash":
                return self._dash()
            if path == "/plans":
                return self._plans()
            if path == "/memory":
                return self._memory()
            if path == "/voice":
                return self._voice(data)
            if path == "/serper":
                return self._serper(data)
            if path == "/keys":
                return self._keys(data)
        except Exception as exc:                 # noqa: BLE001
            log.warning("api %s failed: %s", path, exc)
            return self._json({"error": str(exc)}, 500)
        self._json({"error": "unknown endpoint"}, 404)

    # ------------------------------------------------------------ /ask
    def _ask(self, data: dict) -> None:
        res = self.assistant.ask(str(data.get("text", "")))
        return self._json({
            "text": res.text,
            "route": res.route,
            "local": res.local,
            "conf": res.confidence,
            "secs": res.seconds,
        })

    def _status(self) -> None:
        a = self.assistant
        st = a.status()
        vp = MODULATOR.profile
        return self._json({
            "state": st.get("state", "running"),
            "uptime": round(a.started_at and __import__("time").time() - a.started_at, 0) or 0,
            "turns": st.get("turns", 0),
            "kb": st.get("kb_entries", 0),
            "sm_count": _sm_count(),
            "voice_profile": vp.name.lower(),
            "vrate": vp.rate,
            "vpitch": vp.pitch,
        })

    def _dash(self) -> None:
        todos = []
        for t in TASKS_MGR.all():
            todos.append({
                "id": t.id[-4:], "title": t.title,
                "prio": {1: "low", 2: "med", 3: "high"}.get(int(t.priority), "med"),
                "done": t.status == "done",
            })
        mem = _mem_rows()
        reminders = [
            {"title": t.title, "when": getattr(t, "due_text", "")}
            for t in TASKS.upcoming()
        ]
        return self._json({
            "todos": todos, "mem": mem, "reminders": reminders,
            "kb": KnowledgeBase().count(), "plans": len(PLANNER.list()),
        })

    def _plans(self) -> None:
        plans = []
        for p in PLANNER.list():
            plans.append({
                "id": str(p.get("id", ""))[:8], "goal": p.get("goal", ""),
                "steps": [
                    {"text": s.get("text", ""), "done": s.get("done", False),
                     "kind": s.get("kind", "")}
                    for s in p.get("steps", [])
                ],
            })
        return self._json({"plans": plans})

    def _memory(self) -> None:
        return self._json({"mem": _mem_rows()})

    def _voice(self, data: dict) -> None:
        name = str(data.get("profile", "jarvis")).strip().lower()
        out = MODULATOR.parse_command(f"set voice to {name}")
        return self._json({"ok": True, "msg": out})

    def _serper(self, data: dict) -> None:
        key = str(data.get("key", "")).strip()
        if not key:
            return self._json({"ok": False, "msg": "empty key"}, 400)
        from ..security.secrets import SECRETS
        SECRETS.set("SERPER_API_KEY", key)
        os.environ["SERPER_API_KEY"] = key
        return self._json({"ok": True, "msg": "serper key saved locally"})

    def _keys(self, data: dict) -> None:
        """v2.2: generic encrypted key store — Gemini, OpenAI, Serper,
        Tavily, OpenWeather, ElevenLabs keys all land in data/secrets.json
        (OS-level master key, 600 perms, HMAC-verified). Saved keys are
        picked up live (no restart): config re-reads env, tools re-read
        secrets via os_getenv()."""
        allowed = ("SERPER_API_KEY", "TAVILY_API_KEY",
                   "OPENWEATHER_API_KEY", "ELEVENLABS_API_KEY",
                   "GEMINI_API_KEY", "OPENAI_API_KEY",
                   "OLLAMA_BASE_URL")
        name = str(data.get("name", "")).strip().upper()
        key = str(data.get("key", "")).strip()
        if name not in allowed:
            return self._json(
                {"ok": False,
                 "msg": f"unknown key name: {name or '(empty)'}"}, 400)
        if not key:
            return self._json({"ok": False, "msg": "empty key"}, 400)
        from ..security.secrets import SECRETS
        SECRETS.set(name, key)
        os.environ[name] = key          # live pickup, no restart needed
        return self._json({"ok": True, "msg": f"{name} saved locally"})

    def _keys_status(self) -> None:
        """Masked availability of every optional key (never leaks value)."""
        from ..security.secrets import SECRETS
        names = ("SERPER_API_KEY", "TAVILY_API_KEY", "OPENWEATHER_API_KEY",
                 "ELEVENLABS_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY")
        out = {}
        for n in names:
            try:
                out[n] = bool(os.environ.get(n) or SECRETS.get(n))
            except Exception:                       # noqa: BLE001
                out[n] = False
        return self._json({"keys": out})


def _sm_count() -> int:
    try:
        from ..smarthome import SMARTHOME
        return len(SMARTHOME.devices)
    except Exception:                            # noqa: BLE001
        return 0


def _mem_rows() -> list[dict]:
    rows: list[dict] = []
    try:
        with MEMORY._connect() as conn:          # noqa: SLF001
            cur = conn.execute(
                "SELECT key, value FROM facts ORDER BY ts DESC LIMIT 50")
            for r in cur.fetchall():
                rows.append({"key": r["key"], "value": r["value"]})
    except Exception:                            # noqa: BLE001
        pass
    return rows


def serve(port: int | None = None, blocking: bool = True):
    """Start the Horizon HUD bridge."""
    port = port or PORT
    Handler.assistant = get_assistant()
    Handler.assistant.startup()
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    log.info("Rolex Horizon HUD → http://127.0.0.1:%d", port)
    print(f"\n  👑 ROLEX Horizon HUD → http://127.0.0.1:{port}\n")
    if blocking:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  👑 Rolex HUD closed.")
            Handler.assistant.shutdown()
    else:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        return httpd


if __name__ == "__main__":
    serve()
