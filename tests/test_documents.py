"""Tests for Phase 12 - Document Intelligence (all formats, temp DB)."""
import sys
import tempfile
import os
import json
import csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rolex.documents.readers import (DocError, extract_text,
                                     read_docx, read_xlsx, read_pptx,
                                     read_pdf, supported_formats)
from rolex.documents.engine import DocumentEngine, DOC_ENGINE

FIX = Path(__file__).resolve().parent / "fixtures"
APPROVED = {"doc.create", "doc.edit"}     # for gated create/edit flows


def _engine() -> DocumentEngine:
    tmp = tempfile.mkdtemp()
    return DocumentEngine(db_path=os.path.join(tmp, "docs.db"))


# ------------------------------------------------------------ readers
def test_read_txt_md():
    tmp = tempfile.mkdtemp()
    p = Path(tmp) / "note.md"
    p.write_text("# Rolex\nlocal brain", encoding="utf-8")
    text = extract_text(p)
    assert "local brain" in text
    print("PASS test_read_txt_md")


def test_read_csv_and_json():
    tmp = tempfile.mkdtemp()
    c = Path(tmp) / "t.csv"
    c.write_text("name,score\nrolex,100\n", encoding="utf-8")
    out = extract_text(c)
    assert "name | score" in out and "rolex | 100" in out
    j = Path(tmp) / "t.json"
    j.write_text(json.dumps({"ok": True, "list": [1, 2]}), encoding="utf-8")
    jout = extract_text(j)
    assert '"ok": true' in jout
    print("PASS test_read_csv_and_json")


def test_read_docx():
    text = read_docx(FIX / "sample.docx")
    for want in ("Rolex Project Plan", "gearbox design review",
                 "Torque calculation"):
        assert want in text, f"missing: {want}"
    print("PASS test_read_docx")


def test_read_xlsx_shared_strings():
    text = read_xlsx(FIX / "sample.xlsx")
    assert "Name | Role" in text
    assert "Rolex | Assistant" in text
    print("PASS test_read_xlsx_shared_strings")


def test_read_pptx_slides():
    text = read_pptx(FIX / "sample.pptx")
    assert "SLIDE 1" in text and "Rolex AI Overview" in text
    assert "SLIDE 2" in text and "AST safe" in text
    print("PASS test_read_pptx_slides")


def test_read_pdf_real_file():
    text = read_pdf(FIX / "sample.pdf")
    assert "2760" in text and "92 percent" in text
    print("PASS test_read_pdf_real_file")


def test_unsupported_and_missing_fail_cleanly():
    tmp = tempfile.mkdtemp()
    p = Path(tmp) / "x.xyz"
    p.write_text("data", encoding="utf-8")
    try:
        extract_text(p)
        raise AssertionError("unsupported must raise")
    except DocError as e:
        assert "unsupported" in str(e)
    try:
        extract_text(Path(tmp) / "ghost.txt")
        raise AssertionError("missing must raise")
    except DocError:
        pass
    # corrupt docx (not a zip)
    bad = Path(tmp) / "bad.docx"
    bad.write_text("not a zip", encoding="utf-8")
    try:
        extract_text(bad)
        raise AssertionError("corrupt must raise")
    except DocError:
        pass
    assert ".pdf" in supported_formats()
    print("PASS test_unsupported_and_missing_fail_cleanly")


# ------------------------------------------------------------- engine
def test_engine_analyze_summary():
    e = _engine()
    s = e.analyze(FIX / "sample.docx")
    assert s.format == "docx" and s.words > 15
    assert s.summary and len(s.summary) > 10
    assert s.top_keywords and all(isinstance(k, str) for k in s.top_keywords)
    assert "gearbox" in s.top_keywords or "torque" in s.top_keywords
    print("PASS test_engine_analyze_summary")


def test_engine_analyze_pdf():
    e = _engine()
    s = e.analyze(FIX / "sample.pdf")
    assert s.format == "pdf" and s.words > 20
    assert any(k in ("motor", "power", "watts", "gearbox", "battery")
               for k in s.top_keywords)
    print("PASS test_engine_analyze_pdf")


def test_engine_search_text():
    e = _engine()
    hits = e.search_text(FIX / "sample.pdf", "watts")
    assert hits and all("watts" in h for h in hits)
    hits2 = e.search_text(FIX / "sample.docx", "gearbox")
    assert hits2
    no = e.search_text(FIX / "sample.docx", "zzz-not-there")
    assert no == []
    print("PASS test_engine_search_text")


def test_engine_document_memory():
    e = _engine()
    e.analyze(FIX / "sample.docx")
    e.analyze(FIX / "sample.pdf")
    all_docs = e.recall()
    assert len(all_docs) == 2
    # keyword/path query works
    found = e.recall("gearbox")
    assert any("sample.docx" in d["path"] for d in found)
    found = e.recall("pdf")
    assert any("sample.pdf" in d["path"] for d in found)
    # re-analyze updates, does not duplicate (path UNIQUE)
    e.analyze(FIX / "sample.docx")
    assert e.stats()["documents_remembered"] == 2
    print("PASS test_engine_document_memory")


def test_engine_forget_and_stats():
    e = _engine()
    e.analyze(FIX / "sample.xlsx")
    assert e.stats()["documents_remembered"] == 1
    n = e.forget(str(FIX / "sample.xlsx"))
    assert n == 1 and e.stats()["documents_remembered"] == 0
    assert e.forget("never-seen.txt") == 0
    print("PASS test_engine_forget_and_stats")


def test_engine_edit_find_replace():
    tmp = tempfile.mkdtemp()
    p = Path(tmp) / "edit_me.txt"
    p.write_text("Rolex uses old engine. Fix old engine now.",
                 encoding="utf-8")
    e = _engine()
    n = e.edit(p, "old engine", "AST engine")
    assert n == 2
    assert "AST engine" in p.read_text(encoding="utf-8")
    assert "old engine" not in p.read_text(encoding="utf-8")
    assert e.edit(p, "not-present", "x") == 0
    print("PASS test_engine_edit_find_replace")


def test_engine_singleton_and_all_formats():
    assert DOC_ENGINE is not None
    fmts = supported_formats()
    for ext in (".txt", ".md", ".csv", ".json", ".pdf",
                ".docx", ".xlsx", ".pptx"):
        assert ext in fmts, f"missing {ext}"
    print("PASS test_engine_singleton_and_all_formats")


if __name__ == "__main__":
    test_read_txt_md()
    test_read_csv_and_json()
    test_read_docx()
    test_read_xlsx_shared_strings()
    test_read_pptx_slides()
    test_read_pdf_real_file()
    test_unsupported_and_missing_fail_cleanly()
    test_engine_analyze_summary()
    test_engine_analyze_pdf()
    test_engine_search_text()
    test_engine_document_memory()
    test_engine_forget_and_stats()
    test_engine_edit_find_replace()
    test_engine_singleton_and_all_formats()
    print("ALL DOCUMENTS TESTS PASSED")
