"""Rolex command processor — slash/keyword system commands (Phase 2)."""
from __future__ import annotations

from .identity import IDENTITY
from .state import SystemState


class CommandProcessor:
    """Handles system-level commands before the brain sees them.
    Returns None when input is NOT a command (normal chat flows on)."""

    def __init__(self, lifecycle=None, state_machine=None, extra: dict | None = None):
        self.lifecycle = lifecycle
        self.sm = state_machine or (lifecycle.sm if lifecycle else None)
        self.extra: dict = extra or {}
        self.history: list[dict] = []
        self.commands = {
            "help": self._help, "?": self._help,
            "status": self._status,
            "whoami": self._whoami, "who": self._whoami,
            "version": self._version,
            "uptime": self._uptime,
            "state": self._state,
            "stop": self._stop, "shutdown": self._stop,
            "restart": self._restart,
        }

    # -----------------------------------------------------------
    def register(self, name: str, fn) -> None:
        self.commands[name] = fn

    def parse(self, text: str) -> str | None:
        """Return command name if text is a Rolex command, else None.

        A command is the WHOLE utterance ("status", "/help", "who?").
        Just matching the first word hijacks normal chat — "who won the
        world cup" is a question for the brain, NOT /whoami.
        """
        t = (text or "").strip()
        if not t:
            return None
        low = t.lower()
        if low.startswith("/"):
            low = low[1:]
        core = low.strip("!?., ")
        if not core:
            return None
        words = core.split()
        if len(words) == 1 and words[0] in self.commands:
            return words[0]
        return None

    def execute(self, text: str) -> str | None:
        """Run a command. Returns reply text or None (not a command)."""
        name = self.parse(text)
        if not name:
            return None
        fn = self.commands[name]
        out = fn()
        self.history.append({"command": name, "reply": out})
        return out

    # -----------------------------------------------------------
    def _help(self) -> str:
        return (
            "ROLEX commands:\n"
            "  /status   — full system status\n"
            "  /state    — current lifecycle state\n"
            "  /uptime   — how long Rolex has been running\n"
            "  /version  — Rolex version\n"
            "  /whoami   — Rolex identity\n"
            "  /restart  — restart Rolex\n"
            "  /stop     — emergency shutdown\n"
            "  Math direct-a ketta: '12*5', 'ohm law 12V 2A' — Rolex local solve pannum."
        )

    def _status(self) -> str:
        if self.lifecycle:
            s = self.lifecycle.status()
            mods = ", ".join(f"{k}:{'OK' if v else 'DOWN'}"
                             for k, v in s["modules"].items()) or "no modules"
            sys_ = s["system"]
            return (f"ROLEX {IDENTITY.version} | state: {sys_['state']} | "
                    f"uptime: {sys_['uptime_sec']}s\nModules: {mods}")
        return f"ROLEX status: {self.sm.state.value if self.sm else 'offline'}"

    def _whoami(self) -> str:
        return IDENTITY.introduction

    def _version(self) -> str:
        return f"ROLEX AI v{IDENTITY.version}"

    def _uptime(self) -> str:
        if self.sm:
            u = self.sm.uptime
            m, s = divmod(int(u), 60)
            h, m = divmod(m, 60)
            return f"Uptime: {h}h {m}m {s}s"
        return "Uptime: n/a (offline)"

    def _state(self) -> str:
        return f"State: {self.sm.state.value}" if self.sm else "State: offline"

    def _stop(self) -> str:
        if self.sm:
            self.sm.force(SystemState.STOPPED, "emergency stop command")
        return "ROLEX stopping. Emergency stop engaged. 🔴"

    def _restart(self) -> str:
        if self.lifecycle:
            self.lifecycle.restart("command")
            return "ROLEX restarted. ✅"
        return "Restart needs lifecycle module."
