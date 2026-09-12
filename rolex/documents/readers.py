"""Rolex Document Readers (Phase 12) — every format, local only.

TXT / MD      → direct text read
CSV           → csv module (rows joined)
JSON          → pretty-dump
PDF           → pdftotext CLI (poppler), graceful if missing
DOCX / XLSX / PPTX → OOXML via stdlib zipfile + ElementTree
              (no external libraries ever required)

Every reader returns plain text. Errors raise DocError (never crash).
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ..logging_setup import get_logger

log = get_logger("documents")

_MAX_DOC_BYTES = 15 * 1024 * 1024     # 15 MB cap


class DocError(Exception):
    """Document read/parse failure."""


_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_A_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


# ----------------------------------------------------------------- plain
def read_txt(path: Path) -> str:
    if path.stat().st_size > _MAX_DOC_BYTES:
        raise DocError("file too large (>15MB)")
    return path.read_text(encoding="utf-8", errors="replace")


def read_csv(path: Path) -> str:
    text = read_txt(path)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return ""
    out = [" | ".join(r) for r in rows]
    return "\n".join(out)


def read_json(path: Path) -> str:
    text = read_txt(path)
    try:
        data = json.loads(text)
    except ValueError as e:
        raise DocError(f"invalid JSON: {e}") from e
    return json.dumps(data, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------- pdf
def read_pdf(path: Path) -> str:
    """pdftotext (poppler) — one page per form-feed."""
    try:
        r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                           capture_output=True, text=True, timeout=60)
    except FileNotFoundError as e:
        raise DocError("pdftotext not installed (poppler-utils)") from e
    except subprocess.TimeoutExpired as e:
        raise DocError("pdftotext timed out") from e
    if r.returncode != 0:
        raise DocError(f"pdftotext failed: {r.stderr.strip()[:120]}")
    return r.stdout


# ------------------------------------------------------------------ docx
def read_docx(path: Path) -> str:
    """Word: word/document.xml → paragraphs from w:t runs."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise DocError(f"not a valid docx: {e}") from e
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise DocError(f"docx xml broken: {e}") from e
    paras: list[str] = []
    for p in root.iter(f"{_W_NS}p"):
        text = "".join(t.text or "" for t in p.iter(f"{_W_NS}t"))
        if text.strip():
            paras.append(text.strip())
    return "\n".join(paras)


# ------------------------------------------------------------------ xlsx
def read_xlsx(path: Path) -> str:
    """Excel: sharedStrings + sheet1 → 'v | v | v' rows."""
    try:
        with zipfile.ZipFile(path) as z:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in z.namelist():
                sroot = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in sroot.iter(f"{_S_NS}si"):
                    shared.append(
                        "".join(t.text or "" for t in si.iter(f"{_S_NS}t")))
            sheet_xml = z.read("xl/worksheets/sheet1.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise DocError(f"not a valid xlsx: {e}") from e
    except ET.ParseError as e:
        raise DocError(f"xlsx xml broken: {e}") from e
    root = ET.fromstring(sheet_xml)
    lines: list[str] = []
    for row in root.iter(f"{_S_NS}row"):
        cells: list[str] = []
        for c in row.iter(f"{_S_NS}c"):
            t = c.get("t")
            if t == "s":                              # shared string
                idx = int(c.findtext(f"{_S_NS}v", default="-1") or -1)
                cells.append(shared[idx] if 0 <= idx < len(shared) else "")
            elif t == "inlineStr":
                cells.append("".join(x.text or ""
                                    for x in c.iter(f"{_S_NS}t")))
            else:
                cells.append(c.findtext(f"{_W_NS}v", default=""))
        if any(x.strip() for x in cells):
            lines.append(" | ".join(cells))
    return "\n".join(lines)


# ------------------------------------------------------------------ pptx
def _slide_num(name: str) -> int:
    m = re.search(r"slide(\d+)\.xml$", name)
    return int(m.group(1)) if m else 0


def read_pptx(path: Path) -> str:
    """PowerPoint: every slide's a:t runs, SLIDE n headers."""
    try:
        with zipfile.ZipFile(path) as z:
            slides = sorted(
                (n for n in z.namelist()
                 if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                key=_slide_num)
            if not slides:
                raise DocError("pptx has no slides")
            parts: list[str] = []
            for n in slides:
                root = ET.fromstring(z.read(n))
                texts = [t.text or "" for t in root.iter(f"{_A_NS}t")]
                body = "\n".join(x for x in (s.strip() for s in texts) if x)
                parts.append(f"SLIDE {_slide_num(n)}\n{body}")
    except zipfile.BadZipFile as e:
        raise DocError(f"not a valid pptx: {e}") from e
    except ET.ParseError as e:
        raise DocError(f"pptx xml broken: {e}") from e
    return "\n\n".join(parts)


# ------------------------------------------------------------------ main
READERS = {
    ".txt": read_txt, ".md": read_txt, ".log": read_txt,
    ".csv": read_csv,
    ".json": read_json,
    ".pdf": read_pdf,
    ".docx": read_docx,
    ".xlsx": read_xlsx,
    ".pptx": read_pptx,
}


def extract_text(path: str | Path) -> str:
    """Auto-detect by extension → plain text. Raises DocError."""
    p = Path(path)
    if not p.exists():
        raise DocError(f"file not found: {path}")
    if not p.is_file():
        raise DocError(f"not a file: {path}")
    reader = READERS.get(p.suffix.lower())
    if reader is None:
        raise DocError(f"unsupported format: {p.suffix or '(no ext)'} "
                       f"(supported: {', '.join(sorted(READERS))})")
    try:
        return reader(p)
    except DocError:
        raise
    except OSError as e:
        raise DocError(f"read failed: {e}") from e


def supported_formats() -> list[str]:
    return sorted(READERS)
