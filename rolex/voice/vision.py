"""Rolex Vision (Phase 13) — camera/photo understanding, local-first.

No external libs required:
  - basic image info + type/size via header sniffing (pure stdlib)
  - PIL when installed: dimensions, brightness, dominant-ish stats

Camera capture:
  - imageio/OpenCV/ffmpeg when installed (opt-in)
  - otherwise reports "camera unavailable" honestly
"""
from __future__ import annotations

import struct
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger("vision")

try:
    from PIL import Image              # optional
    _PIL_OK = True
except Exception:                      # pragma: no cover
    Image = None
    _PIL_OK = False


class VisionError(Exception):
    pass


# ------------------------------------------------------- header sniff
def sniff_format(path: str | Path) -> str:
    """Pure-stdlib image format detection from magic bytes."""
    p = Path(path)
    if not p.is_file():
        raise VisionError(f"image not found: {path}")
    head = p.open("rb").read(32)
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head[:4] == b"II*\x00" or head[:4] == b"MM\x00*":
        return "tiff"
    if head.startswith(b"BM"):
        return "bmp"
    if head[:2] == b"\x00\x00" and head[8:12] == b"ftyp":
        return "webp-ish/heic"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "webp"
    return "unknown"


def _png_dims(head: bytes) -> tuple[int, int] | None:
    if head.startswith(b"\x89PNG\r\n\x1a\n") and len(head) >= 24:
        w, h = struct.unpack(">II", head[16:24])
        return w, h
    return None


def basic_info(path: str | Path) -> dict:
    """Format + size + (stdlib) dimensions when parseable."""
    p = Path(path)
    fmt = sniff_format(p)
    info = {"path": str(p), "format": fmt,
            "size_kb": round(p.stat().st_size / 1024, 1)}
    with p.open("rb") as f:
        head = f.read(64)
    # PNG dimensions — pure stdlib
    dims = _png_dims(head)
    if dims:
        info["width"], info["height"] = dims
    # JPEG dimensions — parse SOF markers (stdlib)
    if fmt == "jpeg" and "width" not in info:
        w = h = None
        with p.open("rb") as f:
            data = f.read()
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                break
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = struct.unpack(">H", data[i + 2:i + 4])[0]
            i += 2 + seglen
        if w and h:
            info["width"], info["height"] = w, h
    return info


# ------------------------------------------------------------- camera
class Camera:
    """Photo capture — honest availability reporting."""

    def __init__(self):
        self._cmds = {}
        for tool, url in (
                ("termux-api", "termux-camera-photo"),
                ("imageio", "imageio"),
                ("opencv", "cv2")):
            try:
                if tool == "termux-api":
                    import shutil
                    self._cmds[tool] = shutil.which(url)
                elif tool == "imageio":
                    import importlib
                    importlib.import_module("imageio")
                    self._cmds[tool] = True
                elif tool == "opencv":
                    import importlib
                    importlib.import_module("cv2")
                    self._cmds[tool] = True
            except Exception:
                self._cmds[tool] = False

    def available(self) -> dict:
        return dict(self._cmds)

    def capture(self, out_path: str | Path = "data/camera.jpg",
                camera_id: int = 0) -> str:
        """Take a photo → saved file path. Raises VisionError if none."""
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if self._cmds.get("termux-api"):
            import subprocess
            r = subprocess.run(
                ["termux-api", "termux-camera-photo", "-c", str(camera_id),
                 str(p)], capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and p.exists():
                return str(p)
        if self._cmds.get("opencv"):
            import cv2
            cap = cv2.VideoCapture(camera_id)
            try:
                ok, frame = cap.read()
                if ok:
                    cv2.imwrite(str(p), frame)
                    return str(p)
            finally:
                cap.release()
        raise VisionError("no camera backend available")


class Vision:
    """Image understanding: metadata + stats + honest limits."""

    def analyze_image(self, path: str | Path) -> dict:
        info = basic_info(path)
        if _PIL_OK:
            try:
                from PIL import ImageStat
                with Image.open(path) as im:
                    im.load()
                    gray = im.convert("L")
                    st = ImageStat.Stat(gray)
                    info["brightness"] = round(st.mean[0], 1)
                    info["contrast"] = round(
                        (st.stddev[0] / max(1, st.mean[0])), 2)
                    info["mode"] = im.mode
            except Exception as e:    # pragma: no cover
                log.info("PIL analysis failed: %s", e)
        else:
            info["analysis"] = ("full pixel analysis needs PIL "
                                "(pip install Pillow) — metadata shown")
        return info

    def describe(self, path: str | Path) -> str:
        """Human-friendly image description (local, honest)."""
        info = self.analyze_image(path)
        dims = (f"{info['width']}x{info['height']}"
                if "width" in info else "unknown size")
        b = info.get("brightness")
        tone = ""
        if b is not None:
            tone = " · bright image" if b > 140 else (
                " · dark image" if b < 80 else " · normal lighting")
        return (f"🖼️ {Path(path).name}: {info['format'].upper()} "
                f"{dims} · {info['size_kb']}KB{tone}")


VISION = Vision()
CAMERA = Camera()
