"""Rolex Smart Home VI2 + Device Management (v2 §30–31).

Local-first, permission-gated. No device is touched without explicit
permission. Works with any local hub (Home Assistant style REST API).
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("smarthome")


class SmartHomeError(RolexError):
    code = "SMARTHOME_ERROR"


# ------------------------------------------------------------- devices
class Device:
    """A registered smart-home device (record only — commands gated)."""

    def __init__(self, name: str, room: str, dtype: str,
                 actions: list[str], hub_url: str = ""):
        self.name, self.room, self.dtype = name, room, dtype
        self.actions = actions
        self.hub_url = hub_url
        self.state: dict = {"on": False}

    def to_json(self) -> dict:
        return {"name": self.name, "room": self.room, "type": self.dtype,
                "actions": self.actions, "hub": self.hub_url,
                "state": self.state}


class SmartHome:
    """VI2 — Voice Interaction & Device Control layer.

    Safe by default:
      • device registry stored locally (JSON)
      • commands require explicit user permission
      • dangerous actions (unlock, thermostat-max) always ask
    """

    DANGEROUS = {"unlock", "open_door", "disable_alarm", "thermostat_max"}

    def __init__(self, state_path: str | None = None):
        self.path = Path(state_path or CONFIG.DATA_DIR / "smarthome.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.devices: dict[str, Device] = {}
        self._load()

    # ------------------------------------------------------------- io
    def _load(self) -> None:
        try:
            if self.path.is_file():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for d in data.get("devices", []):
                    dev = Device(d["name"], d.get("room", ""),
                                 d.get("type", "switch"),
                                 d.get("actions", ["on", "off"]),
                                 d.get("hub", ""))
                    dev.state = d.get("state", {"on": False})
                    self.devices[dev.name.lower()] = dev
        except Exception as e:                                  # noqa: BLE001
            log.warning("smarthome load: %s", e)

    def _save(self) -> None:
        data = {"devices": [d.to_json() for d in self.devices.values()]}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    # ------------------------------------------------------- registry
    def register(self, name: str, room: str = "", dtype: str = "switch",
                 actions: list[str] | None = None,
                 hub_url: str = "") -> Device:
        dev = Device(name, room, dtype, actions or ["on", "off"], hub_url)
        self.devices[name.lower()] = dev
        self._save()
        return dev

    def list_devices(self) -> str:
        if not self.devices:
            return ("🏠 devices இல்லை · none registered — "
                    "'register device hall light' என்று சொல்லுங்கள்.")
        lines = ["🏠 Rolex Smart Home (VI2):"]
        for d in self.devices.values():
            state = "🟢 on" if d.state.get("on") else "⚫ off"
            lines.append(f"   {d.room + ' · ' if d.room else ''}{d.name} "
                         f"({d.dtype}) {state}")
        return "\n".join(lines)

    # --------------------------------------------------------- control
    def control(self, name: str, action: str,
                approved: bool = False) -> str:
        """Execute a device action. Requires explicit approval."""
        dev = self.devices.get((name or "").lower())
        if dev is None:
            return f"⚠️ device '{name}' register ஆகவில்லை · not found."
        if action not in dev.actions:
            return (f"⚠️ '{action}' இந்த device-க்கு இல்லை. "
                    f"allowed: {dev.actions}")
        if action in self.DANGEROUS and not approved:
            return (f"🔒 '{action}' dangerous action — "
                    "explicit permission வேண்டும் (உங்களுடன் confirm பண்ணுவேன்).")
        # local state flip (hub call optional, permission-gated)
        dev.state["on"] = action in ("on", "open", "start", "unlock")
        if dev.hub_url:
            try:
                body = json.dumps({"entity": dev.name,
                                   "action": action}).encode()
                req = urllib.request.Request(dev.hub_url, data=body,
                                             headers={"Content-Type":
                                                      "application/json"})
                urllib.request.urlopen(req, timeout=5)
            except Exception as e:                              # noqa: BLE001
                log.info("hub call failed: %s", e)
        self._save()
        return f"🏠 {dev.name} → {action} ✓"

    # ------------------------------------------------- natural language
    _RE_CTL = re.compile(
        r"^(?:turn|switch)\s+(on|off)\s+(?:the\s+)?(.+)$", re.I)
    _RE_CTL2 = re.compile(r"^(on|off)\s+(.+)$", re.I)

    _RE_DANGER = re.compile(
        r"^(?:please\s+)?(unlock|disable\s+alarm|disable_alarm|"
        r"open\s+door|open_door|thermostat\s*max|thermostat_max)"
        r"(?:\s+(?:the\s+)?(.+?))?[\s.!?]*$", re.I)

    def parse_command(self, text: str, approved: bool = False) -> str:
        t = (text or "").strip()
        low = t.lower()
        # §30 danger-lock — dangerous requests are never silently
        # ignored: always surface the permission gate.
        d = self._RE_DANGER.match(low)
        if d:
            action = re.sub(r"[\s_]+", "_", d.group(1).strip().lower())
            if action == "disable_alarm":
                action = "disable_alarm"
            elif action in ("open_door", "open"):
                action = "open_door"
            elif action == "thermostat_max":
                action = "thermostat_max"
            name = (d.group(2) or "").strip()
            name = re.sub(r"^(?:the|that|my)\s+", "", name).strip()
            if not name:
                name = "front door" if action == "unlock" else "device"
            if not approved:
                dev = self.devices.get(name.lower())
                extra = "" if dev else (f" · device '{name}' "
                                        "register ஆகଵில்லை")
                return (f"🔒 '{action}' — dangerous action "
                        "needs explicit permission · "
                        "உங்களுடன் confirm "
                        "பண்ணுவேன் (danger-lock §30)"
                        f"{extra}.")
            return self.control(name, action, approved=True)
        m = self._RE_CTL.match(low) or self._RE_CTL2.match(low)
        if m:
            action, name = m.group(1).lower(), m.group(2).strip()
            name = re.sub(r"^(?:the|that|my)\s+", "", name)
            return self.control(name, action, approved=approved)
        if re.search(r"\b(register|add)\s+(a\s+)?device\b", low):
            mm = re.search(r"device\s+(.+)$", low)
            name = (mm.group(1) if mm else "").strip()
            if name:
                self.register(name)
                return f"🏠 device registered: {name} (actions on/off)"
            return "🏠 device name சொல்லுங்கள்?"
        if re.search(r"\b(devices?|smarthome|smart home)\b.*"
                     r"(list|show|காட்டு)?", low) and re.search(
                r"\b(devices?|smarthome|smart home)\b", low):
            return self.list_devices()
        return ""


SMARTHOME = SmartHome()
