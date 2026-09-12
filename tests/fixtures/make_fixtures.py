"""Build Phase-12 test fixtures: docx/xlsx/pptx via stdlib zipfile,
pdf via wkhtmltopdf. Re-run any time; outputs are deterministic."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from rolex.config import CONFIG  # noqa: E402

FIX = Path(__file__).resolve().parent


def make_docx() -> Path:
    """Minimal but valid Word file: 3 paragraphs, w:t runs."""
    p = lambda t: (
        '<w:p><w:r><w:t xml:space="preserve">' + t + "</w:t></w:r></w:p>")
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>'
           + p("Rolex Project Plan") + p("Phase 1 foundation done.")
           + p("The motor gearbox design review is next week.")
           + p("Torque calculation spreadsheet attached in xlsx format.")
           + "</w:body></w:document>")
    out = FIX / "sample.docx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0" encoding="UTF-8"?>'
                   '<Types xmlns="http://schemas.openxmlformats.org/'
                   'package/2006/content-types"/>')
        z.writestr("word/document.xml", doc)
    return out


def make_xlsx() -> Path:
    """Minimal valid Excel: sharedStrings + sheet1 with 2 rows."""
    shared = ('<?xml version="1.0" encoding="UTF-8"?>'
              '<sst xmlns="http://schemas.openxmlformats.org/'
              'spreadsheetml/2006/main" count="4" uniqueCount="4">'
              '<si><t>Name</t></si><si><t>Role</t></si>'
              '<si><t>Rolex</t></si><si><t>Assistant</t></si></sst>')
    sheet = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/'
             'spreadsheetml/2006/main">'
             '<row r="1"><c r="A1" t="s"><v>0</v></c>'
             '<c r="B1" t="s"><v>1</v></c></row>'
             '<row r="2"><c r="A2" t="s"><v>2</v></c>'
             '<c r="B2" t="s"><v>3</v></c></row>'
             '</worksheet>')
    out = FIX / "sample.xlsx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<Types/>')
        z.writestr("xl/workbook.xml", '<workbook/>')
        z.writestr("xl/sharedStrings.xml", shared)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return out


def make_pptx() -> Path:
    """Minimal valid PowerPoint: 2 slides with a:t text."""
    slide = lambda texts: (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/'
        'main" xmlns:p="http://schemas.openxmlformats.org/presentationml/'
        '2006/main"><p:cSld><p:spTree>'
        + "".join('<p:sp><p:txBody><a:p><a:r><a:t>' + t +
                  "</a:t></a:r></a:p></p:txBody></p:sp>" for t in texts)
        + "</p:spTree></p:cSld></p:sld>")
    out = FIX / "sample.pptx"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<Types/>')
        z.writestr("ppt/slides/slide1.xml", slide(["Rolex AI Overview",
                                                   "Local first architecture"]))
        z.writestr("ppt/slides/slide2.xml", slide(["Math engine 100% offline",
                                                   "No eval, AST safe"]))
    return out


def make_pdf() -> Path:
    """Real PDF via wkhtmltopdf (installed in sandbox)."""
    import subprocess
    html = FIX / "sample.html"
    out = FIX / "sample.pdf"
    html.write_text(
        "<html><body><h1>Rolex Power Report</h1>"
        "<p>The motor draws 12 amps at 230 volts. Power equals 2760 watts."
        " Efficiency of the gearbox is 92 percent.</p>"
        "<p>Gear ratio calculation uses teeth counts. Battery energy is "
        "measured in watt hours.</p>"
        "</body></html>", encoding="utf-8")
    r = subprocess.run(["wkhtmltopdf", "--no-pdf-compression", "-q",
                        str(html), str(out)], capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"wkhtmltopdf failed: {r.stderr[:200]}")
    return out


if __name__ == "__main__":
    print("docx:", make_docx().name)
    print("xlsx:", make_xlsx().name)
    print("pptx:", make_pptx().name)
    print("pdf: ", make_pdf().name)
    print("FIXTURES READY")
