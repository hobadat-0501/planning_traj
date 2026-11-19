"""Build the two .docx reports from Markdown via pandoc (LaTeX math -> native Word OMML equations)."""
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REF = HERE / "reference.docx"
DOCS = [
    "BAO_CAO_1_DIEU_KIEN_MO_PHONG_VA_PHUONG_AN_A",
    "BAO_CAO_2_THAY_DOI_PHUONG_AN_B_VA_SO_SANH_A_B",
]
FONT = "Times New Roman"


def make_reference() -> None:
    subprocess.run(
        ["pandoc", "-o", str(REF), "--print-default-data-file", "reference.docx"],
        check=True,
    )
    doc = Document(str(REF))
    for st in doc.styles:
        if st.type != 1:  # paragraph/character styles only
            continue
        try:
            st.font.name = FONT
            rpr = st.element.get_or_add_rPr()
            rfonts = rpr.find(qn("w:rFonts"))
            if rfonts is None:
                rfonts = OxmlElement("w:rFonts")
                rpr.append(rfonts)
            for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
                rfonts.set(qn(a), FONT)
            for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
                if rfonts.get(qn(a)) is not None:
                    del rfonts.attrib[qn(a)]
        except Exception:
            pass
    sizes = {"Normal": 13, "Body Text": 13, "First Paragraph": 13, "Compact": 12,
             "Title": 18, "Subtitle": 14, "Heading 1": 15, "Heading 2": 13.5, "Heading 3": 13}
    for name, sz in sizes.items():
        try:
            st = doc.styles[name]
            st.font.size = Pt(sz)
            if name.startswith("Heading") or name == "Title":
                st.font.color.rgb = RGBColor(0x1F, 0x3A, 0x68)
                st.font.bold = True
        except KeyError:
            pass
    doc.save(str(REF))


def set_borders(tbl) -> None:
    tblPr = tbl._tbl.tblPr
    old = tblPr.find(qn("w:tblBorders"))
    if old is not None:
        tblPr.remove(old)
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "808080")
        borders.append(el)
    tblPr.append(borders)


def postprocess(path: Path) -> tuple[int, int]:
    doc = Document(str(path))
    for tbl in doc.tables:
        set_borders(tbl)
        for i, row in enumerate(tbl.rows):
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(11)
                        if i == 0:
                            r.font.bold = True
                if i == 0:
                    tcPr = cell._tc.get_or_add_tcPr()
                    shd = OxmlElement("w:shd")
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:color"), "auto")
                    shd.set(qn("w:fill"), "DCE6F1")
                    tcPr.append(shd)
    for p in doc.paragraphs:
        if p.style.name in ("Title", "Subtitle", "Date"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.save(str(path))
    body = doc.element.body
    n_disp = len(body.findall(".//" + qn("m:oMathPara")))
    n_all = len(body.findall(".//" + qn("m:oMath")))
    return n_disp, n_all


def main() -> int:
    make_reference()
    for name in DOCS:
        src = HERE / f"{name}.md"
        dst = OUT / f"{name}.docx"
        subprocess.run(
            ["pandoc", str(src), "-f", "markdown+tex_math_dollars", "-t", "docx",
             "--reference-doc", str(REF), "-o", str(dst)],
            check=True,
        )
        n_disp, n_all = postprocess(dst)
        print(f"{dst.name}: {n_disp} khối phương trình, {n_all} đối tượng OMML, {len(Document(str(dst)).tables)} bảng")
    return 0


if __name__ == "__main__":
    sys.exit(main())
