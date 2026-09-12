"""Rolex logging — rotating file + console, UTF-8 safe."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import CONFIG

_CONFIGURED = False


def setup_logging() -> logging.Logger:
    """Idempotent logging setup. Returns the 'rolex' root logger."""
    global _CONFIGURED
    logger = logging.getLogger("rolex")
    if _CONFIGURED or logger.handlers:
        return logger

    logger.setLevel(getattr(logging, CONFIG.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-22s | %(message)s"
    )

    # Console
    try:
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)
    except Exception:
        pass

    # Rotating file
    try:
        CONFIG.ensure_dirs()
        fh = RotatingFileHandler(
            CONFIG.LOG_DIR / "rolex.log",
            maxBytes=1_000_000, backupCount=3, encoding="utf-8",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass

    _CONFIGURED = True
    return logger


def get_logger(name: str = "core") -> logging.Logger:
    setup_logging()
    if not name.startswith("rolex"):
        name = f"rolex.{name}"
    return logging.getLogger(name)
