"""Rolex lifecycle — startup / shutdown orchestration (Phase 2)."""
from __future__ import annotations

from .events import EVENT_BUS
from .identity import IDENTITY
from .state import StateMachine, SystemState


class RolexLifecycle:
    """Boots modules in order and shuts them down safely."""

    def __init__(self, modules: dict | None = None):
        self.sm = StateMachine()
        self.modules: dict[str, object] = modules or {}
        self._booted: list[str] = []

    # -----------------------------------------------------------
    def register(self, name: str, module) -> None:
        self.modules[name] = module

    def startup(self) -> dict:
        """Boot every module; degraded modules never stop the boot."""
        self.sm.transition(SystemState.BOOTING, "startup")
        EVENT_BUS.publish("rolex.boot.start", {"version": IDENTITY.version})

        report = {}
        for name, mod in self.modules.items():
            ok = True
            try:
                if hasattr(mod, "startup"):
                    mod.startup()
                self._booted.append(name)
                EVENT_BUS.publish("rolex.module.ready", {"module": name})
            except Exception as e:  # noqa: BLE001
                ok = False
                EVENT_BUS.publish("rolex.module.failed",
                                  {"module": name, "error": str(e)})
            report[name] = "ok" if ok else "failed"

        state = SystemState.LISTENING if all(
            v == "ok" for v in report.values()) else SystemState.DEGRADED
        self.sm.transition(state, "boot complete")
        EVENT_BUS.publish("rolex.boot.done", report)
        return report

    # -----------------------------------------------------------
    def shutdown(self, reason: str = "user") -> dict:
        EVENT_BUS.publish("rolex.shutdown.start", {"reason": reason})
        report = {}
        # Reverse order — later modules depend on earlier ones.
        for name in reversed(self._booted):
            ok = True
            try:
                mod = self.modules.get(name)
                if mod and hasattr(mod, "shutdown"):
                    mod.shutdown()
            except Exception as e:  # noqa: BLE001
                ok = False
            report[name] = "ok" if ok else "failed"
        self.sm.force(SystemState.STOPPED, f"shutdown:{reason}")
        EVENT_BUS.publish("rolex.shutdown.done", report)
        return report

    def restart(self, reason: str = "restart") -> dict:
        self.shutdown(reason)
        return self.startup()

    # -----------------------------------------------------------
    def status(self) -> dict:
        return {
            "identity": IDENTITY.whoami(),
            "system": self.sm.snapshot(),
            "modules": {n: (n in self._booted) for n in self.modules},
        }
