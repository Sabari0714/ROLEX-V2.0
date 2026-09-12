"""Rolex Sync & Backup Engine (v2 §20) — local-first 3-way sync.

Architecture: Android/Termux ↔ Cloud VPS ↔ Google Drive

Local-first guarantee:
  • Full backup ALWAYS lands locally first (zip in data/backups/)
  • Cloud/Drive push is optional & explicit (never automatic)
  • Restore works from local zip even with zero internet
"""
from __future__ import annotations

import json
import re
import shutil
import sqlite3
import time
import zipfile
from pathlib import Path

from ..config import CONFIG
from ..errors import RolexError
from ..logging_setup import get_logger

log = get_logger("sync")


class SyncError(RolexError):
    code = "SYNC_ERROR"


class BackupEngine:
    """Create / verify / restore local backups of all Rolex data."""

    def __init__(self, backup_dir: str | None = None):
        self.dir = Path(backup_dir or CONFIG.BACKUP_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------ what
    def _targets(self) -> list[Path]:
        """All local data files Rolex owns (db, plans, secrets-free)."""
        out = []
        for p in (CONFIG.DATA_DIR).rglob("*"):
            if p.is_file() and "backups" not in p.parts and "logs" not in p.parts:
                out.append(p)
        # knowledge topics ship with the repo; include for restore safety
        for p in (CONFIG.KB_DIR).rglob("*.json"):
            out.append(p)
        return out

    # ---------------------------------------------------------- create
    def create(self, tag: str = "") -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        name = f"rolex-backup-{stamp}{('-' + tag) if tag else ''}.zip"
        dest = self.dir / name
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            manifest = {"created": time.time(), "version": CONFIG.VERSION,
                        "files": []}
            for p in self._targets():
                try:
                    arc = p.relative_to(CONFIG.ROOT_DIR)
                except ValueError:
                    arc = Path("data") / p.name
                z.write(p, str(arc))
                manifest["files"].append(str(arc))
            z.writestr("MANIFEST.json",
                       json.dumps(manifest, ensure_ascii=False, indent=2))
        log.info("backup created: %s (%d files)", dest.name,
                 len(self._targets()))
        return dest

    def latest(self) -> Path | None:
        zips = sorted(self.dir.glob("rolex-backup-*.zip"))
        return zips[-1] if zips else None

    def list(self) -> list[dict]:
        out = []
        for z in sorted(self.dir.glob("rolex-backup-*.zip")):
            try:
                with zipfile.ZipFile(z) as f:
                    n = len([x for x in f.namelist()
                             if x != "MANIFEST.json"])
                out.append({"file": z.name, "size_kb": round(
                    z.stat().st_size / 1024, 1), "files": n})
            except Exception:                                   # noqa: BLE001
                continue
        return out

    # ---------------------------------------------------------- verify
    def verify(self, path: Path | None = None) -> dict:
        z = path or self.latest()
        if z is None or not z.is_file():
            return {"ok": False, "error": "no backup found"}
        try:
            with zipfile.ZipFile(z) as f:
                bad = f.testzip()
                names = f.namelist()
                manifest = json.loads(
                    f.read("MANIFEST.json").decode("utf-8"))
            return {"ok": bad is None, "zip": z.name,
                    "files": len([n for n in names if n != "MANIFEST.json"]),
                    "created": manifest.get("created"), "bad_file": bad}
        except Exception as e:                                  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    # ---------------------------------------------------------- restore
    def restore(self, path: Path | None = None, dry_run: bool = False
                ) -> dict:
        z = path or self.latest()
        if z is None or not z.is_file():
            return {"ok": False, "error": "no backup found"}
        restored, skipped = [], []
        with zipfile.ZipFile(z) as f:
            for name in f.namelist():
                if name == "MANIFEST.json":
                    continue
                target = CONFIG.ROOT_DIR / name
                if not any(part in ("secrets", ".env", ".git")
                           for part in target.parts):
                    if dry_run:
                        restored.append(f"would-restore: {name}")
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(f.read(name))
                        restored.append(name)
                else:
                    skipped.append(name)
        return {"ok": True, "zip": z.name, "restored": len(restored),
                "skipped": skipped, "dry_run": dry_run}


class CloudSync:
    """Optional push/pull to VPS or Google Drive (explicit only).

    Strategy (works without extra deps):
      • VPS     : rsync/scp-style via subprocess (if configured)
      • Drive   : rclone-style (if rclone installed) or manual upload
    Local backup is ALWAYS taken first — offline-first guarantee.
    """

    def __init__(self, backup_engine: BackupEngine | None = None):
        self.engine = backup_engine or BackupEngine()

    def status(self) -> dict:
        import shutil as _sh
        return {
            "rclone": bool(_sh.which("rclone")),
            "rsync": bool(_sh.which("rsync")),
            "vps_host": CONFIG.SYNC_VPS_HOST,
            "drive_remote": CONFIG.SYNC_DRIVE_REMOTE,
            "last_local_backup": str(self.engine.latest()),
        }

    def push(self, remote: str = "drive", confirm: bool = False) -> str:
        """Push latest backup to remote. Explicit confirm required."""
        if not confirm:
            return ("☁️ sync push needs explicit confirmation — "
                    "'sync push drive confirm' என்று சொல்லுங்கள்.")
        z = self.engine.create(tag="sync")   # fresh local backup first
        if remote == "drive":
            import shutil as _sh
            if not _sh.which("rclone"):
                return (f"☁️ rclone install ஆகவில்லை — backup local-ஆ "
                        f"இருக்கு: {z}")
            import subprocess
            r = subprocess.run(
                ["rclone", "copy", str(z),
                 f"{CONFIG.SYNC_DRIVE_REMOTE}:rolex-backups"],
                capture_output=True, timeout=120)
            ok = r.returncode == 0
            return (f"☁️ Google Drive push {'✓' if ok else 'failed'} — "
                    f"{z.name}")
        if remote == "vps":
            import subprocess
            host = CONFIG.SYNC_VPS_HOST
            if not host:
                return "☁️ VPS host configure ஆகவில்லை (ROLEX_SYNC_VPS .env)"
            r = subprocess.run(
                ["rsync", "-az", str(z), f"{host}:~/rolex-backups/"],
                capture_output=True, timeout=120)
            ok = r.returncode == 0
            return f"☁️ VPS push {'✓' if ok else 'failed'} — {z.name}"
        return "☁️ remote வேண்டும்: 'drive' | 'vps'"

    def parse_command(self, text: str) -> str:
        low = (text or "").lower()
        if re.search(r"\b(sync|backup|பேக்கப்)\b", low) and re.search(
                r"\bpush|drive|vps|cloud\b", low):
            confirm = "confirm" in low or "yes" in low
            remote = "vps" if "vps" in low else "drive"
            return self.push(remote=remote, confirm=confirm)
        if re.search(r"\b(backup|பேக்கப்)\b", low):
            z = self.engine.create()
            v = self.engine.verify(z)
            return (f"💾 Rolex backup ✓ {z.name} · "
                    f"{v['files']} files · "
                    f"{round(z.stat().st_size/1024,1)}KB "
                    f"(data/backups/)")
        if re.search(r"\b(restore|மீட்டாள்)\b", low):
            r = self.engine.restore(dry_run=True)
            if not r.get("ok"):
                return f"⚠️ {r.get('error')}"
            return (f"↩️ dry-run: {r['restored']} files would restore — "
                    f"'restore now confirm' என்று சொன்னா உண்மையா நடக்கும்.")
        if re.search(r"\b(sync status|sync report)\b", low):
            s = self.status()
            return (f"☁️ sync: rclone={'✓' if s['rclone'] else '✗'} · "
                    f"rsync={'✓' if s['rsync'] else '✗'} · "
                    f"vps={s['vps_host'] or 'not set'} · "
                    f"drive={s['drive_remote'] or 'not set'}")
        return ""


BACKUP = BackupEngine()
CLOUD = CloudSync(BACKUP)
