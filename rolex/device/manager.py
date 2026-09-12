"""Rolex Device Manager (v2 §31) — Android/Termux device intelligence.

Pure-python detection — works everywhere, Android-aware, never crashes.
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path

from ..config import CONFIG
from ..logging_setup import get_logger

log = get_logger("device")


def _is_android() -> bool:
    return ("ANDROID_ROOT" in os.environ or "TERMUX_VERSION" in os.environ
            or Path("/system/app").exists())


class DeviceManager:
    """Battery, storage, connectivity, info — local & permission-free."""

    def __init__(self):
        self.android = _is_android()

    # ------------------------------------------------------------ info
    def info(self) -> dict:
        d = {
            "platform": platform.system(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "android": self.android,
            "termux": "TERMUX_VERSION" in os.environ,
            "pydroid": "PYDROID_PACKAGE" in os.environ,
        }
        return d

    def describe(self) -> str:
        d = self.info()
        where = ("Android" if d["android"] else d["platform"])
        extra = []
        if d["termux"]:
            extra.append("Termux")
        if d["pydroid"]:
            extra.append("Pydroid3")
        suffix = f" ({'+'.join(extra)})" if extra else ""
        return (f"📱 {where}{suffix} · Python {d['python']} · "
                f"{d['machine']} · Rolex v{CONFIG.VERSION}")

    # --------------------------------------------------------- battery
    def battery(self) -> dict:
        """Android: termux-battery-status / dumpsys; desktop: acpi fallback."""
        out = {"level": None, "charging": None, "source": None}
        if shutil.which("termux-battery-status"):
            try:
                r = subprocess.run(["termux-battery-status"],
                                   capture_output=True, timeout=5)
                data = __import__("json").loads(r.stdout.decode() or "{}")
                out.update({"level": data.get("percentage"),
                            "charging": data.get("status") == "CHARGING",
                            "source": "termux"})
                return out
            except Exception:                                   # noqa: BLE001
                pass
        if shutil.which("dumpsys") and self.android:
            try:
                r = subprocess.run(["dumpsys", "battery"],
                                   capture_output=True, timeout=5)
                txt = r.stdout.decode(errors="replace")
                m = re.search(r"level:\s*(\d+)", txt)
                if m:
                    out["level"] = int(m.group(1))
                    out["source"] = "dumpsys"
                return out
            except Exception:                                   # noqa: BLE001
                pass
        # desktop fallback
        for f in ("/sys/class/power_supply/BAT0/capacity",):
            try:
                out["level"] = int(Path(f).read_text().strip())
                out["source"] = "sysfs"
            except Exception:                                   # noqa: BLE001
                continue
        return out

    def battery_report(self) -> str:
        b = self.battery()
        if b["level"] is None:
            return "🔋 battery info unavailable on this platform"
        charge = "⚡ charging" if b.get("charging") else "🔋 discharging"
        return f"🔋 battery: {b['level']}% · {charge} ({b['source']})"

    # -------------------------------------------------------- storage
    def storage(self) -> dict:
        try:
            usage = shutil.disk_usage(str(Path.home()))
            return {"total_gb": round(usage.total / 1e9, 1),
                    "used_gb": round(usage.used / 1e9, 1),
                    "free_gb": round(usage.free / 1e9, 1)}
        except Exception:                                       # noqa: BLE001
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0}

    def storage_report(self) -> str:
        s = self.storage()
        pct = (s["used_gb"] / s["total_gb"] * 100) if s["total_gb"] else 0
        return (f"💾 storage: {s['free_gb']}GB free / {s['total_gb']}GB "
                f"({pct:.0f}% used)")

    # ---------------------------------------------------- connectivity
    def connectivity(self) -> dict:
        st = {"internet": False, "source": None}
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=3)
            st["internet"], st["source"] = True, "tcp:1.1.1.1:53"
        except Exception:                                       # noqa: BLE001
            # termux alternative
            if shutil.which("termux-wifi-connectioninfo"):
                try:
                    subprocess.run(["termux-wifi-connectioninfo"],
                                   capture_output=True, timeout=4)
                    st["source"] = "termux-wifi"
                except Exception:                               # noqa: BLE001
                    pass
        return st

    def connectivity_report(self) -> str:
        c = self.connectivity()
        return ("🌐 internet: " + ("online ✓" if c["internet"]
                                   else "offline ⚠️ (local mode)"))

    # ------------------------------------------------- natural language
    def parse_command(self, text: str) -> str:
        low = (text or "").lower()
        if re.search(r"\b(battery|charge|பேட்டரி)\b", low):
            return self.battery_report()
        if re.search(r"\b(storage|space|disk|இடம்|ஸ்டோரேஜ்)\b", low):
            return self.storage_report()
        if re.search(r"\b(device info|about (this )?device|சாதனம்)\b", low):
            return self.describe()
        if re.search(r"\b(internet|online|offline|net|connection)\b", low):
            return self.connectivity_report()
        return ""


DEVICE = DeviceManager()
