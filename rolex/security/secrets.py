"""Rolex Secrets Manager (Phase 14) — API keys never in plain text.

Design (stdlib only):
  - master key from env ROLEX_MASTER_KEY, or auto-generated once
    and stored at data/.rolex_master_key (chmod 600)
  - secrets AES-free: XOR-stream + HMAC via hashlib (sha256 keystream)
    — "poor-man's authenticated encryption"
  - honest security model: protects casual snooping on the data
    folder; full-disk/attacker-with-env access is out of scope
  - secrets NEVER logged, NEVER returned in full (masked views)

Storage: data/secrets.json  {"name": {"nonce": hex, "ct": hex, "mac": hex}}
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets as _secrets
import stat
import time
from pathlib import Path

from ..config import CONFIG
from ..logging_setup import get_logger

log = get_logger("secrets")


def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    """SHA256-based counter-mode keystream."""
    out = bytearray()
    counter = 0
    while len(out) < n:
        block = hashlib.sha256(
            key + nonce + counter.to_bytes(8, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:n])


class SecretsManager:
    def __init__(self, path: str | None = None,
                 master_key_path: str | None = None,
                 env_key: str | None = None):
        self.path = Path(path or Path(CONFIG.DATA_DIR) / "secrets.json")
        self.master_key_path = Path(
            master_key_path or Path(CONFIG.DATA_DIR) / ".rolex_master_key")
        self._env_key = env_key or "ROLEX_MASTER_KEY"
        self._store: dict[str, dict] = {}
        self.load()

    # -------------------------------------------------------- master key
    def _master_key(self) -> bytes:
        env_val = os.getenv(self._env_key)
        if env_val:
            return hashlib.sha256(env_val.encode()).digest()
        if not self.master_key_path.exists():
            self.master_key_path.parent.mkdir(parents=True, exist_ok=True)
            raw = _secrets.token_hex(32)
            self.master_key_path.write_text(raw, encoding="utf-8")
            try:                                   # chmod 600
                os.chmod(self.master_key_path, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
            log.info("generated new master key")
        return hashlib.sha256(
            self.master_key_path.read_text(encoding="utf-8").strip()
            .encode()).digest()

    # ------------------------------------------------------------- store
    def load(self) -> None:
        if self.path.exists():
            try:
                self._store = json.loads(
                    self.path.read_text(encoding="utf-8"))
            except Exception as e:    # noqa: BLE001
                log.error("secrets load failed: %s", e)
                self._store = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._store), encoding="utf-8")
        try:
            os.chmod(self.path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    # -------------------------------------------------------------- CRUD
    def set(self, name: str, value: str) -> None:
        if not name or not value:
            raise ValueError("secret name/value required")
        key = self._master_key()
        nonce = _secrets.token_bytes(16)
        ct = bytes(a ^ b for a, b in zip(
            value.encode("utf-8"), _keystream(key, nonce, len(value))))
        mac = hmac.new(key, nonce + ct, hashlib.sha256).hexdigest()
        self._store[name] = {"nonce": nonce.hex(), "ct": ct.hex(),
                             "mac": mac}
        self.save()
        log.info("secret stored: %s (masked)", self._mask(name))

    def get(self, name: str) -> str | None:
        rec = self._store.get(name)
        if not rec:
            return None
        key = self._master_key()
        nonce = bytes.fromhex(rec["nonce"])
        ct = bytes.fromhex(rec["ct"])
        expect_mac = hmac.new(key, nonce + ct,
                              hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expect_mac, rec["mac"]):
            raise PermissionError(
                f"secret '{self._mask(name)}' tampered/decrypted "
                f"with wrong master key")
        pt = bytes(a ^ b for a, b in zip(ct, _keystream(key, nonce,
                                                        len(ct))))
        return pt.decode("utf-8", errors="replace")

    def delete(self, name: str) -> bool:
        if name in self._store:
            del self._store[name]
            self.save()
            return True
        return False

    def list(self) -> list[dict]:
        """Masked inventory — never full values."""
        out: list[dict] = []
        for n in sorted(self._store):
            try:
                val = self.get(n) or ""
                preview = (val[:3] + "****") if len(val) > 3 else "****"
            except PermissionError:
                preview = "(locked)"
            out.append({"name": n, "stored": True, "preview": preview})
        return out

    def _mask(self, name: str) -> str:
        return name[:2] + "***" if len(name) > 2 else "**"

    # ------------------------------------------------------- env bridge
    def sync_from_env(self, mapping: dict[str, str]) -> int:
        """Import API keys from env (OPENAI_API_KEY etc.) → encrypted."""
        imported = 0
        for env_name, secret_name in mapping.items():
            val = os.getenv(env_name)
            if val:
                self.set(secret_name, val)
                imported += 1
        return imported


SECRETS = SecretsManager()
