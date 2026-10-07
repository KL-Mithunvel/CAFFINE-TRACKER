"""Render README.md to docs/README.pdf using ReportLab.

Usage: python scripts/readme_to_pdf.py
Handles the subset of Markdown the README uses: headings, paragraphs,
bullet lists, tables, fenced code, images, bold/italic/code/links.
Relative links are rewritten to GitHub URLs so they work in the PDF.
"""
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, Paragraph,
                                Preformatted, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "README.md"
OUT = ROOT / "docs" / "README.pdf"
REPO = "https://github.com/KL-Mithunvel/CAFFINE-TRACKER"
BLOB = REPO + "/blob/main/"
PAGE_W = A4[0] - 40 * mm

ss = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=ss["BodyText"], fontSize=10, leading=14, alignment=TA_LEFT)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=9, leading=12)
H = {1: ParagraphStyle("h1", parent=ss["Heading1"], fontSize=22, spaceAfter=6, keepWithNext=1),
     2: ParagraphStyle("h2", parent=ss["Heading2"], fontSize=15, spaceBefore=12, spaceAfter=4, keepWithNext=1),
     3: ParagraphStyle("h3", parent=ss["Heading3"], fontSize=12, spaceBefore=8, spaceAfter=3, keepWithNext=1)}
CODE = ParagraphStyle("code", fontName="Courier", fontSize=8, leading=10,
                      backColor=colors.HexColor("#f4f4f4"), borderPadding=4)


def link_target(url):
    if url.startswith(("http://", "https://")):
        return url
    return BLOB + url.lstrip("./")


def inline(text):
    """Markdown inline -> ReportLab mini-HTML."""
    text = re.sub(r"<(https?://[^>]+)>", r"[\1](\1)", text)
    parts = re.split(r"(`[^`]+`|\[[^\]]+\]\([^)]+\))", text)
    out = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append('<font face="Courier">%s</font>' % escape(part[1:-1]))
        elif re.fullmatch(r"\[[^\]]+\]\([^)]+\)", part):
            label, url = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", part).groups()
            label = re.sub(r"^`(.*)`$", r"\1", label)
            out.append('<link href="%s" color="#1a56db"><u>%s</u></link>'
                       % (escape(link_target(url)), escape(label)))
        else:
            t = escape(part)
            t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
            t = re.sub(r"(?<!\*)\*(?!\s)(.+?)\*(?!\*)", r"<i>\1</i>", t)
            out.append(t)
    return "".join(out)


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def image_flowable(path, max_w):
    from reportlab.lib.utils import ImageReader
    w, h = ImageReader(str(path)).getSize()
    scale = max_w / w
    return Image(str(path), width=w * scale, height=h * scale)


def cell_content(text):
    m = re.fullmatch(r"!\[[^\]]*\]\(([^)]+)\)", text)
    if m:
        return image_flowable(ROOT / m.group(1), (PAGE_W - 12) / 2 - 8)
    return Paragraph(inline(text), CELL)


def table(rows):
    header, body = rows[0], rows[1:]
    has_header = any(header)
    data = ([[cell_content(c) for c in header]] if has_header else []) + \
           [[cell_content(c) for c in r] for r in body]
    ncol = len(rows[0])
    t = Table(data, colWidths=[PAGE_W / ncol] * ncol if ncol != 2 or any("![" in c for c in rows[1]) else [PAGE_W * 0.28, PAGE_W * 0.72])
    style = [("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
             ("VALIGN", (0, 0), (-1, -1), "TOP")]
    if has_header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")))
    t.setStyle(TableStyle(style))
    return t


def parse(lines):
    flow, i = [], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            block = []
            while not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            flow += [Preformatted("\n".join(block), CODE), Spacer(1, 6)]
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            flow.append(Paragraph(inline(line[level:].strip()), H[min(level, 3)]))
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.fullmatch(r"[|\s:-]+", lines[i]):
                    rows.append(split_row(lines[i]))
                i += 1
            flow += [KeepTogether(table(rows)), Spacer(1, 8)]
            continue
        elif re.match(r"- ", line):
            items = []
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("  ") and lines[i].strip()):
                if lines[i].startswith("- "):
                    items.append(lines[i][2:].strip())
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            flow += [ListFlowable([ListItem(Paragraph(inline(t), BODY)) for t in items],
                                  bulletType="bullet", start="•", leftIndent=14), Spacer(1, 6)]
            continue
        elif line.strip():
            para = [line.strip()]
            while (i + 1 < len(lines) and lines[i + 1].strip()
                   and not re.match(r"(#|\||- |```)", lines[i + 1])):
                i += 1
                para.append(lines[i].strip())
            flow += [Paragraph(inline(" ".join(para)), BODY), Spacer(1, 6)]
        i += 1
    return flow


def main():
    OUT.parent.mkdir(exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm,
                            title="Caffeine Tracker - README", author="Mithunvel K.L")
    doc.build(parse(SRC.read_text(encoding="utf-8").splitlines()))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
