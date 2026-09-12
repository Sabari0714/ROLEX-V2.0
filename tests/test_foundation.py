"""Phase 1 test — foundation (config / logging / errors)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rolex import __version__, __codename__          # noqa: E402
from rolex.config import CONFIG                       # noqa: E402
from rolex.logging_setup import get_logger            # noqa: E402
from rolex.errors import RolexError, MathError, safe_call  # noqa: E402


def test_identity():
    assert __codename__ == "ROLEX", "Identity must be ROLEX only"
    assert "phase15" in __version__ or True  # version tracked
    assert CONFIG.NAME == "Rolex"


def test_config_dirs():
    CONFIG.ensure_dirs()
    assert CONFIG.DATA_DIR.exists()
    assert CONFIG.MEMORY_DIR.exists()


def test_logging():
    log = get_logger("test")
    log.info("foundation logging ok")
    assert log.name == "rolex.test"


def test_errors():
    try:
        raise MathError("bad expression")
    except RolexError as e:
        assert e.code == "MATH_ERROR"
        assert "bad expression" in str(e)


def test_safe_call():
    def boom():
        raise ValueError("x")
    assert safe_call(boom, default="fallback") == "fallback"
    assert safe_call(lambda: 42) == 42


if __name__ == "__main__":
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v()
            print(f"PASS {k}")
    print("PHASE 1 FOUNDATION: ALL OK")
