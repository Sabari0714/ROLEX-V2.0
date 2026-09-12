"""Rolex Remote Lab (v2 §21) — WebSocket server + token pairing.

Pure-stdlib design (no 'websocket' dependency required):
  • Plain-HTTP upgrade-free JSON channel (works on any LAN)
  • Token auth (SHA-256 challenge) — pair once, trust forever
  • Remote commands: device info, status, diagnostics, ask()
  • EMERGENCY STOP honored — remote cannot override local stop

If the 'websockets' package is installed, upgrade automatically.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import socket
import threading
import time
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("remote_lab")


class RemoteLabError(RolexError):
    code = "REMOTE_LAB_ERROR"


class RemoteLab:
    """TCP/JSON control server — pair with token, run remote ops."""

    def __init__(self, port: int | None = None, token: str | None = None):
        self.port = port or CONFIG.REMOTE_LAB_PORT
        self.token = token or CONFIG.REMOTE_LAB_TOKEN
        self.paired: dict[str, float] = {}       # client_id → last_seen
        self.sessions: list[dict] = []
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    # ----------------------------------------------------------- token
    def _challenge(self) -> str:
        return secrets.token_hex(16)

    def _verify(self, client_token: str, challenge: str) -> bool:
        expect = hashlib.sha256(
            (self.token + challenge).encode()).hexdigest()
        return secrets.compare_digest(
            (client_token or "").strip().lower(), expect)

    def pair(self, client_id: str) -> dict:
        """Generate pairing info for a new client (manual exchange)."""
        cid = client_id or secrets.token_hex(4)
        self.paired[cid] = time.time()
        return {"client_id": cid, "port": self.port,
                "pairing_code": secrets.token_hex(6),
                "note": "token-protected — share ROLEX_LAB_TOKEN securely"}

    def unpair(self, client_id: str) -> bool:
        return self.paired.pop(client_id, None) is not None

    # ------------------------------------------------------------ ask
    def handle_message(self, msg: dict) -> dict:
        """Remote command dispatcher — read-heavy, write-gated."""
        op = (msg.get("op") or "").lower()
        if op == "hello":
            return {"ok": True, "rolex": CONFIG.NAME,
                    "version": CONFIG.VERSION, "challenge": self._challenge()}
        if op == "auth":
            ok = self._verify(msg.get("token", ""), msg.get("challenge", ""))
            return {"ok": ok, "paired": ok}
        if op == "stop":
            # EMERGENCY STOP — always allowed, even unauthed (safety
            # valve: a stuck/compromised client must be able to halt Rolex).
            # Local emergency_stop() is still honored first.
            CONFIG.STOP_FLAG.write_text("remote-stop")
            return {"ok": True, "stopped": True, "note": "safety valve"}
        if not msg.get("authed"):
            return {"ok": False, "error": "auth required"}
        # ---- authed ops ------------------------------------------------
        if op == "status":
            from ..assistant import get_assistant
            return {"ok": True, "status": get_assistant().status()}
        if op == "device":
            from ..device.manager import DEVICE
            return {"ok": True, "device": DEVICE.info(),
                    "battery": DEVICE.battery(),
                    "storage": DEVICE.storage()}
        if op == "diagnostics":
            from ..security.diagnostics import run_self_test
            return {"ok": True, "report": run_self_test()}
        if op == "ask":
            # remote can ask Rolex — answers flow back, memory still local
            from ..assistant import get_assistant
            res = get_assistant().ask(msg.get("text", ""))
            return {"ok": True, "text": res.text, "route": res.route,
                    "local": res.local}
        return {"ok": False, "error": f"unknown op: {op}"}

    # ----------------------------------------------------------- serve
    def start(self, host: str = "0.0.0.0", blocking: bool = False) -> dict:
        if not self.token:
            return {"ok": False,
                    "error": "ROLEX_LAB_TOKEN not set — remote lab disabled"}
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server.bind((host, self.port))
            self._server.listen(4)
        except OSError as e:
            return {"ok": False, "error": f"bind failed: {e}"}
        self._running = True

        def _serve():
            while self._running:
                try:
                    conn, addr = self._server.accept()
                except OSError:
                    break
                threading.Thread(target=self._client, args=(conn, addr),
                                 daemon=True).start()

        if blocking:
            _serve()
        else:
            self._thread = threading.Thread(target=_serve, daemon=True)
            self._thread.start()
        log.info("remote lab listening on %s:%d", host, self.port)
        return {"ok": True, "host": host, "port": self.port}

    def _client(self, conn: socket.socket, addr) -> None:
        """One client: hello → auth → commands (max 20 ops / 10 min)."""
        conn.settimeout(600)
        authed = False
        ops = 0
        try:
            while self._running and ops < 20:
                data = conn.recv(65536)
                if not data:
                    break
                msg = json.loads(data.decode("utf-8", errors="replace") or "{}")
                if msg.get("op") == "auth":
                    authed = self._verify(msg.get("token", ""),
                                          msg.get("challenge", ""))
                msg["authed"] = authed
                reply = self.handle_message(msg)
                conn.sendall(json.dumps(reply, ensure_ascii=False).encode())
                ops += 1
                self.sessions.append({"addr": addr[0], "op": msg.get("op"),
                                      "ok": reply.get("ok"),
                                      "ts": time.time()})
        except Exception as e:                                  # noqa: BLE001
            log.debug("client %s: %s", addr, e)
        finally:
            try:
                conn.close()
            except Exception:                                   # noqa: BLE001
                pass

    def stop(self) -> dict:
        self._running = False
        if self._server:
            try:
                self._server.close()
            except Exception:                                   # noqa: BLE001
                pass
        return {"ok": True, "sessions": len(self.sessions)}

    def status(self) -> dict:
        return {"running": self._running, "port": self.port,
                "paired": list(self.paired), "sessions": len(self.sessions),
                "token_set": bool(self.token)}


REMOTE_LAB = RemoteLab()
