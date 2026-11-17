"""
docx_builder.py
===============
Branded A4 Microsoft Word (.docx) lesson plan generator for AITADZ (aitadz.pro).

Produces ready-to-print A4 documents (210mm x 297mm, 12.7mm / 0.5-inch margins)
styled with the AITADZ Brand Palette and aligned strictly with the Algerian
Primary School English Didactic Guide layout (KS1 p. 75 / KS3 p. 86).
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Mm, Pt, RGBColor

# ---------------------------------------------------------------------------
# AITADZ BRAND PALETTE CONSTANTS
# ---------------------------------------------------------------------------

HEX_DEEP_NAVY = "0D1B2A"
HEX_PRIMARY_BLUE = "0056D2"
HEX_SKY_BLUE = "3FA9F5"
HEX_ACCENT_ORANGE = "FF8C42"
HEX_SOFT_GRAY = "F5F7FA"
HEX_TINT_BLUE = "EDF5FF"
HEX_TINT_ORANGE = "FFF7F0"
HEX_BORDER_GRAY = "D0D9E6"
HEX_WHITE = "FFFFFF"

COLOR_DEEP_NAVY = RGBColor(0x0D, 0x1B, 0x2A)
COLOR_PRIMARY_BLUE = RGBColor(0x00, 0x56, 0xD2)
COLOR_SKY_BLUE = RGBColor(0x3F, 0xA9, 0xF5)
COLOR_ACCENT_ORANGE = RGBColor(0xFF, 0x8C, 0x42)
COLOR_SOFT_GRAY = RGBColor(0xF5, 0xF7, 0xFA)
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
COLOR_TEXT_DARK = RGBColor(0x1E, 0x29, 0x3B)
COLOR_TEXT_MUTED = RGBColor(0x47, 0x55, 0x69)

FONT_FAMILY = "Calibri"
USABLE_WIDTH_MM = 184.6  # 210mm A4 - (2 * 12.7mm margins)

# Modern "Executive Standard (4Cs & VARK)" Palette
HEX_MODERN_NAVY = "0F172A"
HEX_MODERN_BLUE = "2563EB"
HEX_MODERN_ROYAL = "1E3A8A"
HEX_MODERN_LINK = "1D4ED8"
HEX_MODERN_SLATE_BG = "F8FAFC"
HEX_MODERN_BORDER = "CBD5E1"
HEX_MODERN_DASHED = "94A3B8"
COLOR_MODERN_NAVY = RGBColor(0x0F, 0x17, 0x2A)
COLOR_MODERN_ROYAL = RGBColor(0x1E, 0x3A, 0x8A)
COLOR_MODERN_LINK = RGBColor(0x1D, 0x4E, 0xD8)
COLOR_MODERN_SUBTITLE = RGBColor(0x94, 0xA3, 0xB8)

# ---------------------------------------------------------------------------
# TEMPLATE REGISTRY
# ---------------------------------------------------------------------------

TEMPLATES: Dict[str, Dict[str, str]] = {
    "classic": {
        "id": "classic",
        "name": "AITADZ Classic Didactic",
        "short_name": "Classic Didactic",
        "emoji": "🏛️",
        "description": (
            "Official Ministry 13-field grid, 5-column procedure table, "
            "Gamification/Exit Ticket callout, and 3-panel Visual Whiteboard."
        ),
    },
    "modern": {
        "id": "modern",
        "name": "Executive Standard (4Cs & VARK)",
        "short_name": "Executive 4Cs & VARK",
        "emoji": "📋",
        "description": (
            "Dark-navy header banner, 2x2 Objectives/Solutions card, 4Cs skill boxes, "
            "Installing Resources (Presentation/Practice/Production), and Time / VARK."
        ),
    },
}


def normalize_template_id(template_id: Optional[str]) -> str:
    cleaned = (template_id or "classic").strip().lower()
    return cleaned if cleaned in TEMPLATES else "classic"


def get_template_meta(template_id: Optional[str]) -> Dict[str, str]:
    return dict(TEMPLATES[normalize_template_id(template_id)])


# ---------------------------------------------------------------------------
# OXML STYLING HELPERS
# ---------------------------------------------------------------------------


def _set_cell_shading(cell: Any, fill_hex: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    for existing in tc_pr.findall(qn("w:shd")):
        tc_pr.remove(existing)
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tc_pr.append(shd)


def _set_cell_margins(
    cell: Any,
    top_dxa: int = 80,
    bottom_dxa: int = 80,
    left_dxa: int = 110,
    right_dxa: int = 110,
) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    for existing in tc_pr.findall(qn("w:tcMar")):
        tc_pr.remove(existing)
    tc_mar = OxmlElement("w:tcMar")
    for side, val in (
        ("top", top_dxa),
        ("bottom", bottom_dxa),
        ("left", left_dxa),
        ("right", right_dxa),
    ):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tc_mar.append(node)
    tc_pr.append(tc_mar)


def _set_cell_borders(
    cell: Any,
    top: Optional[Tuple[str, int, str]] = None,
    bottom: Optional[Tuple[str, int, str]] = None,
    left: Optional[Tuple[str, int, str]] = None,
    right: Optional[Tuple[str, int, str]] = None,
) -> None:
    """
    Configure individual cell borders where each tuple is (color_hex, sz_eighths_pt, style).
    """
    tc_pr = cell._tc.get_or_add_tcPr()
    for existing in tc_pr.findall(qn("w:tcBorders")):
        tc_pr.remove(existing)
    borders = OxmlElement("w:tcBorders")
    for side_name, spec in (
        ("top", top),
        ("bottom", bottom),
        ("left", left),
        ("right", right),
    ):
        if spec is None:
            continue
        color_hex, sz, val = spec
        edge = OxmlElement(f"w:{side_name}")
        edge.set(qn("w:val"), val)
        edge.set(qn("w:sz"), str(sz))
        edge.set(qn("w:space"), "0")
        edge.set(qn("w:color"), color_hex)
        borders.append(edge)
    tc_pr.append(borders)


def _set_table_borders(
    table: Any,
    outer_color: str = HEX_SKY_BLUE,
    inner_color: str = HEX_BORDER_GRAY,
    outer_sz: int = 8,
    inner_sz: int = 4,
) -> None:
    tbl_pr = table._tbl.tblPr
    for existing in tbl_pr.findall(qn("w:tblBorders")):
        tbl_pr.remove(existing)
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="single" w:sz="{outer_sz}" w:space="0" w:color="{outer_color}"/>'
        f'  <w:left w:val="single" w:sz="{outer_sz}" w:space="0" w:color="{outer_color}"/>'
        f'  <w:bottom w:val="single" w:sz="{outer_sz}" w:space="0" w:color="{outer_color}"/>'
        f'  <w:right w:val="single" w:sz="{outer_sz}" w:space="0" w:color="{outer_color}"/>'
        f'  <w:insideH w:val="single" w:sz="{inner_sz}" w:space="0" w:color="{inner_color}"/>'
        f'  <w:insideV w:val="single" w:sz="{inner_sz}" w:space="0" w:color="{inner_color}"/>'
        f"</w:tblBorders>"
    )
    tbl_pr.append(borders)


def _prevent_row_split(row: Any) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    if tr_pr.find(qn("w:cantSplit")) is None:
        tr_pr.append(OxmlElement("w:cantSplit"))


def _repeat_header_row(row: Any) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    if tr_pr.find(qn("w:tblHeader")) is None:
        tr_pr.append(OxmlElement("w:tblHeader"))


def _set_row_min_height(row: Any, height_mm: float) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    for existing in tr_pr.findall(qn("w:trHeight")):
        tr_pr.remove(existing)
    tr_height = OxmlElement("w:trHeight")
    # 1 mm = ~56.7 twips
    tr_height.set(qn("w:val"), str(int(round(height_mm * 56.7))))
    tr_height.set(qn("w:hRule"), "atLeast")
    tr_pr.append(tr_height)


def _set_cell_width_mm(cell: Any, width_mm: float) -> None:
    cell.width = Mm(width_mm)
    tc_pr = cell._tc.get_or_add_tcPr()
    for existing in tc_pr.findall(qn("w:tcW")):
        tc_pr.remove(existing)
    tc_w = OxmlElement("w:tcW")
    tc_w.set(qn("w:w"), str(int(round(width_mm * 56.7))))
    tc_w.set(qn("w:type"), "dxa")
    tc_pr.append(tc_w)


def _add_field(paragraph: Any, field_name: str, font_size: float = 8.5, color: RGBColor = COLOR_TEXT_MUTED) -> None:
    run_begin = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    run_begin._r.append(fld_begin)

    run_instr = paragraph.add_run()
    run_instr.font.name = FONT_FAMILY
    run_instr.font.size = Pt(font_size)
    run_instr.font.color.rgb = color
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {field_name} "
    run_instr._r.append(instr)

    run_sep = paragraph.add_run()
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    run_sep._r.append(fld_sep)

    run_val = paragraph.add_run("1")
    run_val.font.name = FONT_FAMILY
    run_val.font.size = Pt(font_size)
    run_val.font.color.rgb = color

    run_end = paragraph.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run_end._r.append(fld_end)


_RICH_PREFIX_RE = re.compile(
    r"^((?:[•\-]\s*)?"
    r"(?:Activity\s+\d+(?:\s*\([^)]+\))?"
    r"|Task\s+\d+(?:\s*\([^)]+\))?"
    r"|Phase\s+\d+(?:\s*\([^)]+\))?"
    r"|Step\s+\d+(?:\s*\([^)]+\))?"
    r"|Listening\s+Script|Reading\s+Text|Listening\s*/\s*Reading\s+Model"
    r"|Model\s+Form|Practice\s+Form|Model\s+Message|Word\s+Bank|Answer\s+Key|Game\s+Rules"
    r"|Target\s+Lexis(?:\s*&\s*Chunks)?|Model\s+Chunks\s*/\s*Prompts|Phonics\s*/\s*Mechanics"
    r"|Model\s+Text\s*/\s*Task|Flashcards\s*&\s*Lexis|Classroom\s+Reward\s+Board"
    r"|Learner\s+Slate\s+Zone|Topic|Session|Date|Teacher|Learners|T|Ls)"
    r":)\s*(.*)$"
)


def _write_cell_text(
    cell: Any,
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    font_size: float = 9.0,
    color: RGBColor = COLOR_TEXT_DARK,
    align: WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH.LEFT,
    valign: WD_ALIGN_VERTICAL = WD_ALIGN_VERTICAL.CENTER,
    space_after: float = 1.5,
    rich_prefixes: bool = False,
) -> None:
    cell.vertical_alignment = valign
    lines = (text or "").splitlines() or [""]
    first_para = cell.paragraphs[0]
    for idx, line in enumerate(lines):
        p = first_para if idx == 0 else cell.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after if idx < len(lines) - 1 else 0)
        p.paragraph_format.line_spacing = 1.12

        match = _RICH_PREFIX_RE.match(line) if rich_prefixes and not bold else None
        if match:
            prefix, rest = match.group(1), match.group(2)
            p_run = p.add_run(prefix + (" " if rest else ""))
            p_run.bold = True
            p_run.italic = italic
            p_run.font.name = FONT_FAMILY
            p_run.font.size = Pt(font_size)
            p_run.font.color.rgb = COLOR_DEEP_NAVY

            if rest:
                r_run = p.add_run(rest)
                r_run.bold = False
                r_run.italic = italic
                r_run.font.name = FONT_FAMILY
                r_run.font.size = Pt(font_size)
                r_run.font.color.rgb = color
        else:
            run = p.add_run(line)
            run.bold = bold
            run.italic = italic
            run.font.name = FONT_FAMILY
            run.font.size = Pt(font_size)
            run.font.color.rgb = color


def _add_section_title(doc: Document, title: str, accent_hex: str = HEX_PRIMARY_BLUE) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True

    p_pr = p._p.get_or_add_pPr()
    p_bdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}>'
        f'  <w:bottom w:val="single" w:sz="12" w:space="2" w:color="{accent_hex}"/>'
        f"</w:pBdr>"
    )
    p_pr.append(p_bdr)

    run = p.add_run(title)
    run.bold = True
    run.font.name = FONT_FAMILY
    run.font.size = Pt(10.5)
    run.font.color.rgb = COLOR_DEEP_NAVY


def generate_clean_filename(
    grade: str,
    sequence_num: int,
    session_title: str = "LessonPlan",
) -> str:
    """Create a clean, Telegram-friendly filename such as AITADZ_4PS_Seq2_LessonPlan.docx."""
    g = re.sub(r"[^A-Za-z0-9]", "", (grade or "3PS").upper())
    slug = re.sub(r"[^A-Za-z0-9]+", "", (session_title or "LessonPlan").title())[:24] or "LessonPlan"
    return f"AITADZ_{g}_Seq{int(sequence_num)}_{slug}.docx"


# ---------------------------------------------------------------------------
# MAIN DOCUMENT BUILDER
# ---------------------------------------------------------------------------


def build_classic_lesson_plan_docx(
    plan_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """
    Generate the AITADZ Classic Didactic branded A4 .docx lesson plan
    (Ministry 13-field metadata, 5-column procedure, Gamification callout,
    3-panel Whiteboard Layout, and 3-column Self-Reflection).

    Returns the path to the generated .docx file.
    """
    meta = plan_data.get("meta", {})
    header = plan_data.get("header", {})
    stages: List[Dict[str, Any]] = plan_data.get("stages", [])
    gamification = plan_data.get("gamification", {})
    exit_ticket = plan_data.get("exit_ticket", "")
    whiteboard = plan_data.get("whiteboard_layout", {})
    reflection = plan_data.get("self_reflection", {})

    doc = Document()

    # Configure strict A4 page dimensions & 12.7mm (0.5 inch) print margins
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(12.7)
    section.bottom_margin = Mm(12.7)
    section.left_margin = Mm(12.7)
    section.right_margin = Mm(12.7)
    section.header_distance = Mm(6)
    section.footer_distance = Mm(6)

    # Set default body font
    normal_style = doc.styles["Normal"]
    normal_style.font.name = FONT_FAMILY
    normal_style.font.size = Pt(9.5)
    normal_style.font.color.rgb = COLOR_TEXT_DARK

    # -----------------------------------------------------------------------
    # BLOCK 1: AITADZ HEADER BANNER
    # -----------------------------------------------------------------------
    banner_table = doc.add_table(rows=2, cols=2)
    banner_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    banner_table.autofit = False
    _set_table_borders(
        banner_table,
        outer_color=HEX_DEEP_NAVY,
        inner_color=HEX_PRIMARY_BLUE,
        outer_sz=8,
        inner_sz=4,
    )

    # Row 0: Ministry title merged across 2 columns in Deep Navy
    r0_c0 = banner_table.rows[0].cells[0]
    r0_c1 = banner_table.rows[0].cells[1]
    r0_c0.merge(r0_c1)
    _set_cell_width_mm(r0_c0, USABLE_WIDTH_MM)
    _set_cell_shading(r0_c0, HEX_DEEP_NAVY)
    _set_cell_margins(r0_c0, top_dxa=70, bottom_dxa=70, left_dxa=120, right_dxa=120)
    _write_cell_text(
        r0_c0,
        "PEOPLE'S DEMOCRATIC REPUBLIC OF ALGERIA  •  MINISTRY OF NATIONAL EDUCATION\n"
        "OFFICIAL PRIMARY SCHOOL ENGLISH LESSON PLAN (DIDACTIC GUIDE ALIGNED)",
        bold=True,
        font_size=8.5,
        color=COLOR_WHITE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    _prevent_row_split(banner_table.rows[0])

    # Row 1: AITADZ Brand Banner (Primary Blue) + Level Badge (Accent Orange)
    left_banner_w = 138.6
    right_banner_w = 46.0
    r1_c0, r1_c1 = banner_table.rows[1].cells[0], banner_table.rows[1].cells[1]
    _set_cell_width_mm(r1_c0, left_banner_w)
    _set_cell_width_mm(r1_c1, right_banner_w)
    _set_cell_shading(r1_c0, HEX_PRIMARY_BLUE)
    _set_cell_shading(r1_c1, HEX_ACCENT_ORANGE)
    _set_cell_margins(r1_c0, top_dxa=90, bottom_dxa=90, left_dxa=120, right_dxa=100)
    _set_cell_margins(r1_c1, top_dxa=90, bottom_dxa=90, left_dxa=80, right_dxa=80)
    _write_cell_text(
        r1_c0,
        f"AITADZ LESSON PLAN GENERATOR (aitadz.pro)\n"
        f"{header.get('sequence', '')}  |  {header.get('section', '')}",
        bold=True,
        font_size=10.5,
        color=COLOR_WHITE,
    )
    duration_minutes = int(
        meta.get("duration_minutes")
        or sum(int(st.get("minutes", 0) or 0) for st in stages)
        or (60 if str(meta.get("grade", "")).upper() in ("3PS", "4PS") else 45)
    )
    duration_label = header.get("duration") or f"{duration_minutes} mn"

    _write_cell_text(
        r1_c1,
        f"{meta.get('grade', 'PS')}\n{duration_minutes} MINUTES",
        bold=True,
        font_size=10.5,
        color=COLOR_WHITE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    _prevent_row_split(banner_table.rows[1])

    # -----------------------------------------------------------------------
    # BLOCK 2: OFFICIAL DIDACTIC METADATA GRID (KS1 p. 75 / KS3 p. 86)
    # -----------------------------------------------------------------------
    _add_section_title(doc, "1. Official Didactic Metadata & Pedagogical Framing", HEX_PRIMARY_BLUE)

    meta_table = doc.add_table(rows=0, cols=4)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_table.autofit = False
    _set_table_borders(
        meta_table,
        outer_color=HEX_PRIMARY_BLUE,
        inner_color=HEX_SKY_BLUE,
        outer_sz=8,
        inner_sz=4,
    )

    col_w4 = [34.0, 58.3, 34.0, 58.3]  # sums to 184.6 mm

    paired_rows = [
        ("Level", header.get("level", ""), "Class Profile", header.get("class_profile", "")),
        ("Sequence", header.get("sequence", ""), "Number of Learners", header.get("number_of_learners", "")),
        ("Section", header.get("section", ""), "Duration", duration_label),
        ("Session", header.get("session", ""), "Domain(s)", header.get("domains", "")),
    ]

    for row_idx, (l1, v1, l2, v2) in enumerate(paired_rows):
        row = meta_table.add_row()
        _prevent_row_split(row)
        val_bg = HEX_SOFT_GRAY if row_idx % 2 == 1 else HEX_WHITE
        cells = row.cells
        for c_idx, width in enumerate(col_w4):
            _set_cell_width_mm(cells[c_idx], width)
            _set_cell_margins(cells[c_idx], top_dxa=65, bottom_dxa=65, left_dxa=90, right_dxa=90)
        _set_cell_shading(cells[0], HEX_TINT_BLUE)
        _set_cell_shading(cells[1], val_bg)
        _set_cell_shading(cells[2], HEX_TINT_BLUE)
        _set_cell_shading(cells[3], val_bg)
        _write_cell_text(cells[0], l1, bold=True, font_size=8.5, color=COLOR_DEEP_NAVY)
        _write_cell_text(cells[1], str(v1), font_size=8.5)
        _write_cell_text(cells[2], l2, bold=True, font_size=8.5, color=COLOR_DEEP_NAVY)
        _write_cell_text(cells[3], str(v2), font_size=8.5)

    full_rows = [
        ("Target Competence", header.get("target_competence", ""), True),
        ("Session Objective(s)", header.get("session_objectives", ""), True),
        ("Subsidiary Objective(s)", header.get("subsidiary_objectives", ""), False),
        ("Phonics / Language Focus", header.get("phonics_focus", ""), False),
        ("Core Values", header.get("core_values", ""), False),
        ("Cross-Curricular Competencies", header.get("cross_curricular_competencies", ""), False),
        ("Teaching Materials (VAKT)", header.get("teaching_materials", ""), False),
        ("Anticipated Problems", header.get("anticipated_problems", ""), False),
        ("Solutions / Plan B", header.get("solutions_plan_b", ""), False),
    ]

    for idx, (label, val, highlight) in enumerate(full_rows):
        row = meta_table.add_row()
        _prevent_row_split(row)
        label_cell = row.cells[0]
        val_cell = row.cells[1]
        val_cell.merge(row.cells[3])
        _set_cell_width_mm(label_cell, col_w4[0])
        _set_cell_width_mm(val_cell, USABLE_WIDTH_MM - col_w4[0])
        _set_cell_margins(label_cell, top_dxa=65, bottom_dxa=65, left_dxa=90, right_dxa=90)
        _set_cell_margins(val_cell, top_dxa=65, bottom_dxa=65, left_dxa=90, right_dxa=90)

        _set_cell_shading(label_cell, HEX_DEEP_NAVY if highlight else HEX_TINT_BLUE)
        label_color = COLOR_WHITE if highlight else COLOR_DEEP_NAVY
        val_bg = HEX_TINT_ORANGE if label == "Session Objective(s)" else (
            HEX_SOFT_GRAY if idx % 2 == 1 else HEX_WHITE
        )
        _set_cell_shading(val_cell, val_bg)
        if label == "Session Objective(s)":
            _set_cell_borders(val_cell, left=(HEX_ACCENT_ORANGE, 18, "single"))
        _write_cell_text(label_cell, label, bold=True, font_size=8.5, color=label_color)
        _write_cell_text(
            val_cell,
            str(val),
            bold=(label == "Session Objective(s)"),
            font_size=8.5,
            color=COLOR_DEEP_NAVY if label == "Session Objective(s)" else COLOR_TEXT_DARK,
        )

    # -----------------------------------------------------------------------
    # BLOCK 3: STAGE-BY-STAGE LESSON PROCEDURE TABLE
    # -----------------------------------------------------------------------
    _add_section_title(doc, f"2. Stage-by-Stage Lesson Procedure ({duration_minutes} Minutes)", HEX_PRIMARY_BLUE)

    proc_widths = [16.0, 34.0, 77.6, 24.0, 33.0]  # sums to 184.6 mm
    proc_headers = [
        "Time",
        "Stage",
        "Procedure / Teacher & Learner Tasks",
        "Interaction",
        "Competency / Materials",
    ]

    proc_table = doc.add_table(rows=1, cols=5)
    proc_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    proc_table.autofit = False
    _set_table_borders(
        proc_table,
        outer_color=HEX_DEEP_NAVY,
        inner_color=HEX_BORDER_GRAY,
        outer_sz=8,
        inner_sz=4,
    )

    hdr_row = proc_table.rows[0]
    _repeat_header_row(hdr_row)
    _prevent_row_split(hdr_row)
    for idx, title in enumerate(proc_headers):
        cell = hdr_row.cells[idx]
        _set_cell_width_mm(cell, proc_widths[idx])
        _set_cell_shading(cell, HEX_PRIMARY_BLUE)
        _set_cell_margins(cell, top_dxa=90, bottom_dxa=90, left_dxa=85, right_dxa=85)
        _write_cell_text(
            cell,
            title,
            bold=True,
            font_size=8.5,
            color=COLOR_WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER if idx in (0, 3) else WD_ALIGN_PARAGRAPH.LEFT,
        )

    total_minutes = 0
    for r_idx, st in enumerate(stages):
        row = proc_table.add_row()
        proc_text = str(st.get("procedure", ""))
        if len(proc_text.splitlines()) <= 16:
            _prevent_row_split(row)
        bg_hex = HEX_SOFT_GRAY if r_idx % 2 == 1 else HEX_WHITE
        mins = int(st.get("minutes", 0) or 0)
        total_minutes += mins

        row_values = [
            st.get("time") or f"{mins} mn",
            st.get("stage", ""),
            proc_text,
            st.get("interaction", ""),
            st.get("competency_materials", ""),
        ]
        for c_idx, val in enumerate(row_values):
            cell = row.cells[c_idx]
            _set_cell_width_mm(cell, proc_widths[c_idx])
            _set_cell_shading(cell, bg_hex)
            _set_cell_margins(cell, top_dxa=80, bottom_dxa=80, left_dxa=85, right_dxa=85)
            _write_cell_text(
                cell,
                str(val),
                bold=(c_idx in (0, 1)),
                font_size=8.5,
                color=COLOR_PRIMARY_BLUE if c_idx == 0 else (COLOR_DEEP_NAVY if c_idx == 1 else COLOR_TEXT_DARK),
                align=WD_ALIGN_PARAGRAPH.CENTER if c_idx in (0, 3) else WD_ALIGN_PARAGRAPH.LEFT,
                valign=WD_ALIGN_VERTICAL.TOP,
                space_after=2.0 if c_idx == 2 else 1.5,
                rich_prefixes=(c_idx == 2),
            )

    # Total time verification footer row
    tot_row = proc_table.add_row()
    _prevent_row_split(tot_row)
    tot_c0 = tot_row.cells[0]
    tot_c1 = tot_row.cells[1]
    tot_c1.merge(tot_row.cells[4])
    _set_cell_width_mm(tot_c0, proc_widths[0])
    _set_cell_width_mm(tot_c1, USABLE_WIDTH_MM - proc_widths[0])
    _set_cell_shading(tot_c0, HEX_DEEP_NAVY)
    _set_cell_shading(tot_c1, HEX_TINT_BLUE)
    _set_cell_margins(tot_c0, top_dxa=65, bottom_dxa=65, left_dxa=80, right_dxa=80)
    _set_cell_margins(tot_c1, top_dxa=65, bottom_dxa=65, left_dxa=90, right_dxa=90)
    _write_cell_text(
        tot_c0,
        f"{total_minutes} mn",
        bold=True,
        font_size=8.5,
        color=COLOR_WHITE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    _write_cell_text(
        tot_c1,
        f"Total Session Time: {total_minutes} minutes (Compliant with Ministry {duration_minutes}-minute session framework).",
        bold=True,
        font_size=8.5,
        color=COLOR_DEEP_NAVY,
    )

    # -----------------------------------------------------------------------
    # BLOCK 4: CALLOUT BOX — EXIT TICKET & NON-MONETARY GAMIFICATION
    # -----------------------------------------------------------------------
    _add_section_title(doc, "3. Formative Exit Ticket & Non-Monetary Classroom Motivation", HEX_ACCENT_ORANGE)

    callout_tbl = doc.add_table(rows=2, cols=2)
    callout_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    callout_tbl.autofit = False
    _set_table_borders(
        callout_tbl,
        outer_color=HEX_ACCENT_ORANGE,
        inner_color=HEX_SKY_BLUE,
        outer_sz=10,
        inner_sz=4,
    )

    callout_w = [44.0, 140.6]
    rewards_list = ", ".join(gamification.get("rewards", ["Gold Stars", "Explorer Badges", "Team Points", "Stickers"]))
    callout_rows = [
        (
            "Classroom Gamification\n(Non-Monetary)",
            f"{gamification.get('title', 'Classroom Star Quest')}: {gamification.get('description', '')}\n"
            f"Allowed Rewards: {rewards_list}.",
        ),
        (
            "Formative Exit Ticket\n('Ticket to Leave')",
            exit_ticket or "Learners complete a quick oral/slate check and place an emoji card before leaving.",
        ),
    ]

    for idx, (label, content) in enumerate(callout_rows):
        row = callout_tbl.rows[idx]
        _prevent_row_split(row)
        c0, c1 = row.cells[0], row.cells[1]
        _set_cell_width_mm(c0, callout_w[0])
        _set_cell_width_mm(c1, callout_w[1])
        _set_cell_shading(c0, HEX_ACCENT_ORANGE if idx == 0 else HEX_SKY_BLUE)
        _set_cell_shading(c1, HEX_TINT_ORANGE if idx == 0 else HEX_TINT_BLUE)
        _set_cell_margins(c0, top_dxa=75, bottom_dxa=75, left_dxa=90, right_dxa=90)
        _set_cell_margins(c1, top_dxa=75, bottom_dxa=75, left_dxa=95, right_dxa=95)
        _write_cell_text(c0, label, bold=True, font_size=8.5, color=COLOR_WHITE)
        _write_cell_text(c1, content, font_size=8.5, color=COLOR_DEEP_NAVY)

    # -----------------------------------------------------------------------
    # BLOCK 5: VISUAL WHITEBOARD LAYOUT BOX
    # -----------------------------------------------------------------------
    _add_section_title(doc, "4. Visual Whiteboard Layout Box", HEX_SKY_BLUE)

    wb_widths = [61.5, 61.6, 61.5]  # sums to 184.6 mm
    wb_tbl = doc.add_table(rows=2, cols=3)
    wb_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    wb_tbl.autofit = False
    _set_table_borders(
        wb_tbl,
        outer_color=HEX_SKY_BLUE,
        inner_color=HEX_SKY_BLUE,
        outer_sz=10,
        inner_sz=6,
    )

    wb_titles = [
        "LEFT BOARD (Context & Lexis)",
        "CENTER BOARD (Core Model & Practice)",
        "RIGHT BOARD (Rewards & Slate Zone)",
    ]
    wb_contents = [
        whiteboard.get("left_panel", ""),
        whiteboard.get("center_panel", ""),
        whiteboard.get("right_panel", ""),
    ]

    _prevent_row_split(wb_tbl.rows[0])
    _prevent_row_split(wb_tbl.rows[1])
    _set_row_min_height(wb_tbl.rows[1], 24.0)

    for c_idx in range(3):
        hdr_c = wb_tbl.rows[0].cells[c_idx]
        _set_cell_width_mm(hdr_c, wb_widths[c_idx])
        _set_cell_shading(hdr_c, HEX_DEEP_NAVY)
        _set_cell_margins(hdr_c, top_dxa=70, bottom_dxa=70, left_dxa=80, right_dxa=80)
        _write_cell_text(
            hdr_c,
            wb_titles[c_idx],
            bold=True,
            font_size=8.5,
            color=COLOR_WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

        body_c = wb_tbl.rows[1].cells[c_idx]
        _set_cell_width_mm(body_c, wb_widths[c_idx])
        _set_cell_shading(body_c, HEX_SOFT_GRAY if c_idx != 1 else HEX_WHITE)
        _set_cell_margins(body_c, top_dxa=85, bottom_dxa=85, left_dxa=85, right_dxa=85)
        _write_cell_text(
            body_c,
            str(wb_contents[c_idx]),
            font_size=8.2,
            color=COLOR_TEXT_DARK,
            valign=WD_ALIGN_VERTICAL.TOP,
            rich_prefixes=True,
        )

    # -----------------------------------------------------------------------
    # BLOCK 6: OFFICIAL TEACHER SELF-REFLECTION GRID (Guide p. 75 / p. 86)
    # -----------------------------------------------------------------------
    _add_section_title(doc, "5. Teacher Self-Reflection (Official Guide Footer)", HEX_PRIMARY_BLUE)

    sr_tbl = doc.add_table(rows=2, cols=3)
    sr_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    sr_tbl.autofit = False
    _set_table_borders(
        sr_tbl,
        outer_color=HEX_PRIMARY_BLUE,
        inner_color=HEX_BORDER_GRAY,
        outer_sz=8,
        inner_sz=4,
    )

    sr_titles = ["What worked", "What hindered", "Action plan"]
    sr_vals = [
        reflection.get("what_worked", ""),
        reflection.get("what_hindered", ""),
        reflection.get("action_plan", ""),
    ]

    _prevent_row_split(sr_tbl.rows[0])
    _prevent_row_split(sr_tbl.rows[1])
    _set_row_min_height(sr_tbl.rows[1], 14.0)

    for c_idx in range(3):
        hdr_c = sr_tbl.rows[0].cells[c_idx]
        _set_cell_width_mm(hdr_c, wb_widths[c_idx])
        _set_cell_shading(hdr_c, HEX_PRIMARY_BLUE)
        _set_cell_margins(hdr_c, top_dxa=65, bottom_dxa=65, left_dxa=80, right_dxa=80)
        _write_cell_text(
            hdr_c,
            sr_titles[c_idx],
            bold=True,
            font_size=8.5,
            color=COLOR_WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )

        body_c = sr_tbl.rows[1].cells[c_idx]
        _set_cell_width_mm(body_c, wb_widths[c_idx])
        _set_cell_shading(body_c, HEX_SOFT_GRAY)
        _set_cell_margins(body_c, top_dxa=75, bottom_dxa=75, left_dxa=80, right_dxa=80)
        _write_cell_text(
            body_c,
            str(sr_vals[c_idx]),
            italic=True,
            font_size=8.2,
            color=COLOR_TEXT_MUTED,
            valign=WD_ALIGN_VERTICAL.TOP,
        )

    # -----------------------------------------------------------------------
    # BLOCK 7: BRANDED FOOTER WITH PAGE NUMBERING
    # -----------------------------------------------------------------------
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.space_before = Pt(2)
    fp.paragraph_format.space_after = Pt(0)

    fp_pr = fp._p.get_or_add_pPr()
    fp_pr.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'  <w:top w:val="single" w:sz="6" w:space="4" w:color="{HEX_SKY_BLUE}"/>'
            f"</w:pBdr>"
        )
    )

    left_run = fp.add_run("Generated by AITADZ Teacher Assistant (aitadz.pro)   •   Page ")
    left_run.font.name = FONT_FAMILY
    left_run.font.size = Pt(8.5)
    left_run.font.color.rgb = COLOR_TEXT_MUTED
    left_run.bold = True

    _add_field(fp, "PAGE", font_size=8.5, color=COLOR_PRIMARY_BLUE)

    mid_run = fp.add_run(" of ")
    mid_run.font.name = FONT_FAMILY
    mid_run.font.size = Pt(8.5)
    mid_run.font.color.rgb = COLOR_TEXT_MUTED

    _add_field(fp, "NUMPAGES", font_size=8.5, color=COLOR_PRIMARY_BLUE)

    # -----------------------------------------------------------------------
    # SAVE TO DISK
    # -----------------------------------------------------------------------
    if output_path is None:
        tmp_dir = tempfile.mkdtemp(prefix="aitadz_docx_")
        filename = generate_clean_filename(
            meta.get("grade", "3PS"),
            int(meta.get("sequence_number", 1) or 1),
            meta.get("session_title", "LessonPlan"),
        )
        output_path = os.path.join(tmp_dir, filename)
    else:
        parent = os.path.dirname(os.path.abspath(output_path))
        if parent:
            os.makedirs(parent, exist_ok=True)

    doc.save(output_path)
    return output_path


# ---------------------------------------------------------------------------
# MODERN "EXECUTIVE STANDARD (4CS & VARK)" TEMPLATE BUILDER
# ---------------------------------------------------------------------------


def _infer_vark_tags(text: str) -> str:
    """Infer VARK sensory tags (Visual, Auditory, Read/Write, Kinesthetic) from stage text."""
    low = (text or "").lower()
    tags: List[str] = []
    if any(k in low for k in ("visual", "flashcard", "picture", "board", "poster", "realia", "card", "illustration", "chart")):
        tags.append("V")
    if any(k in low for k in ("listen", "sing", "song", "audio", "oral", "choral", "echo", "pronunciation", "aloud", "repeat", "sound", "intonation", "dialogue")):
        tags.append("A")
    if any(k in low for k in ("read", "write", "copybook", "slate", "form", "text", "sentence", "spelling", "word", "print", "cursive", "proofread", "ticket")):
        tags.append("R")
    if any(k in low for k in ("mime", "gesture", "point", "clap", "trace", "race", "slap", "act", "puppet", "gallery", "role-play", "tpr", "finger")):
        tags.append("K")
    if not tags:
        tags = ["V", "A"]
    return " · ".join(tags)


def _split_bullet_items(text: str, max_items: int = 3) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return ["[To be completed by teacher]"]
    parts = [p.strip() for p in re.split(r"[;\n]+", cleaned) if p.strip()]
    return parts[:max_items] if parts else [cleaned]


def _split_stage_procedure(proc_text: str, parts_count: int) -> List[str]:
    """Split a multi-activity procedure across `parts_count` sub-stages cleanly."""
    lines = [ln.strip() for ln in (proc_text or "").splitlines() if ln.strip()]
    if not lines:
        return [""] * parts_count
    if parts_count <= 1:
        return ["\n".join(lines)]

    # Group by Activity / Phase headings if present
    chunks: List[List[str]] = []
    for ln in lines:
        if re.match(r"^(?:Activity|Phase|Task|Game)\s+\d+", ln, flags=re.IGNORECASE) and chunks:
            chunks.append([ln])
        elif not chunks:
            chunks.append([ln])
        else:
            chunks[-1].append(ln)

    if len(chunks) >= parts_count:
        grouped = [[] for _ in range(parts_count)]
        for idx, ch in enumerate(chunks):
            bucket = min(parts_count - 1, (idx * parts_count) // len(chunks))
            grouped[bucket].extend(ch)
        return ["\n".join(g) for g in grouped]

    # Fallback line split
    grouped = [[] for _ in range(parts_count)]
    for idx, ln in enumerate(lines):
        bucket = min(parts_count - 1, (idx * parts_count) // len(lines))
        grouped[bucket].append(ln)
    return ["\n".join(g) if g else lines[-1] for g in grouped]


def _allocate_minutes(total: int, parts: int) -> List[int]:
    if parts <= 0:
        return []
    base = total // parts
    rem = total - (base * parts)
    out = [base] * parts
    for i in range(rem):
        out[i] += 1
    return out


def _map_stages_to_modern_execution(
    stages: List[Dict[str, Any]],
    target_minutes: int,
) -> Dict[str, Any]:
    """
    Map any Didactic blueprint (3, 4, 5, or 6 stages) into the Executive Standard
    5-row layout: Warming up -> Installing resources (Presentation, Practice, Production) -> Assessment.
    """
    if not stages:
        alloc = _allocate_minutes(target_minutes, 5)
        return {
            "warmer": {"procedure": "Warm-up activity", "interaction": "T-Ls", "minutes": alloc[0]},
            "presentation": {"procedure": "Presentation activity", "interaction": "T-Ls", "minutes": alloc[1]},
            "practice": {"procedure": "Practice activity", "interaction": "Pair", "minutes": alloc[2]},
            "production": {"procedure": "Production activity", "interaction": "Group", "minutes": alloc[3]},
            "assessment": {"procedure": "Assessment & Exit Ticket", "interaction": "Individual", "minutes": alloc[4]},
        }

    if len(stages) == 1:
        st = stages[0]
        parts = _split_stage_procedure(st.get("procedure", ""), 5)
        alloc = _allocate_minutes(target_minutes, 5)
        return {
            "warmer": {"procedure": parts[0], "interaction": st.get("interaction", "T-Ls"), "minutes": alloc[0]},
            "presentation": {"procedure": parts[1], "interaction": st.get("interaction", "T-Ls"), "minutes": alloc[1]},
            "practice": {"procedure": parts[2], "interaction": st.get("interaction", "Pair"), "minutes": alloc[2]},
            "production": {"procedure": parts[3], "interaction": st.get("interaction", "Group"), "minutes": alloc[3]},
            "assessment": {"procedure": parts[4], "interaction": st.get("interaction", "Individual"), "minutes": alloc[4]},
        }

    warmer_st = stages[0]
    assess_st = stages[-1]
    middle = stages[1:-1]

    if len(middle) >= 3:
        pres_src = middle[:-2]
        prac_st = middle[-2]
        prod_st = middle[-1]
        pres_proc = "\n".join(str(s.get("procedure", "")) for s in pres_src if s.get("procedure"))
        pres_min = sum(int(s.get("minutes", 0) or 0) for s in pres_src)
        pres_int = " / ".join(dict.fromkeys(str(s.get("interaction", "T-Ls")) for s in pres_src))
    elif len(middle) == 2:
        s1, s2 = middle[0], middle[1]
        pres_proc = str(s1.get("procedure", ""))
        pres_min = int(s1.get("minutes", 0) or 0)
        pres_int = str(s1.get("interaction", "T-Ls"))
        split_2 = _split_stage_procedure(str(s2.get("procedure", "")), 2)
        m2 = int(s2.get("minutes", 0) or 0)
        m_prac, m_prod = _allocate_minutes(m2, 2)
        prac_st = {"procedure": split_2[0], "interaction": s2.get("interaction", "Pair"), "minutes": m_prac}
        prod_st = {"procedure": split_2[1], "interaction": s2.get("interaction", "Pair / Group"), "minutes": m_prod}
    elif len(middle) == 1:
        s1 = middle[0]
        split_3 = _split_stage_procedure(str(s1.get("procedure", "")), 3)
        m_all = _allocate_minutes(int(s1.get("minutes", 0) or 0), 3)
        pres_proc = split_3[0]
        pres_min = m_all[0]
        pres_int = str(s1.get("interaction", "T-Ls"))
        prac_st = {"procedure": split_3[1], "interaction": s1.get("interaction", "Pair"), "minutes": m_all[1]}
        prod_st = {"procedure": split_3[2], "interaction": s1.get("interaction", "Group"), "minutes": m_all[2]}
    else:
        # len(stages) == 2 -> split assess_st or warmer_st
        split_3 = _split_stage_procedure(str(warmer_st.get("procedure", "")), 4)
        w_total = int(warmer_st.get("minutes", 0) or 0)
        m_w = _allocate_minutes(w_total, 4)
        warmer_st = {**warmer_st, "procedure": split_3[0], "minutes": m_w[0]}
        pres_proc, pres_min, pres_int = split_3[1], m_w[1], str(warmer_st.get("interaction", "T-Ls"))
        prac_st = {"procedure": split_3[2], "interaction": "Pair", "minutes": m_w[2]}
        prod_st = {"procedure": split_3[3], "interaction": "Group", "minutes": m_w[3]}

    return {
        "warmer": {
            "procedure": str(warmer_st.get("procedure", "")),
            "interaction": str(warmer_st.get("interaction", "T-Ls")),
            "minutes": int(warmer_st.get("minutes", 0) or 0),
        },
        "presentation": {
            "procedure": pres_proc,
            "interaction": pres_int,
            "minutes": pres_min,
        },
        "practice": {
            "procedure": str(prac_st.get("procedure", "")),
            "interaction": str(prac_st.get("interaction", "Pair")),
            "minutes": int(prac_st.get("minutes", 0) or 0),
        },
        "production": {
            "procedure": str(prod_st.get("procedure", "")),
            "interaction": str(prod_st.get("interaction", "Pair / Group")),
            "minutes": int(prod_st.get("minutes", 0) or 0),
        },
        "assessment": {
            "procedure": str(assess_st.get("procedure", "")),
            "interaction": str(assess_st.get("interaction", "Individual / T-Ls")),
            "minutes": int(assess_st.get("minutes", 0) or 0),
        },
    }


def _add_modern_section_heading(doc: Document, title: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True

    p_pr = p._p.get_or_add_pPr()
    p_pr.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'  <w:bottom w:val="single" w:sz="12" w:space="2" w:color="{HEX_MODERN_BLUE}"/>'
            f"</w:pBdr>"
        )
    )
    run = p.add_run(title)
    run.bold = True
    run.font.name = FONT_FAMILY
    run.font.size = Pt(10.0)
    run.font.color.rgb = COLOR_MODERN_ROYAL


def _write_modern_card_block(
    cell: Any,
    heading: str,
    bullets: List[str],
) -> None:
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    p_head = cell.paragraphs[0]
    p_head.paragraph_format.space_before = Pt(0)
    p_head.paragraph_format.space_after = Pt(4)
    p_head_pr = p_head._p.get_or_add_pPr()
    p_head_pr.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'  <w:bottom w:val="single" w:sz="8" w:space="2" w:color="{HEX_MODERN_BLUE}"/>'
            f"</w:pBdr>"
        )
    )
    h_run = p_head.add_run(heading)
    h_run.bold = True
    h_run.font.name = FONT_FAMILY
    h_run.font.size = Pt(9.0)
    h_run.font.color.rgb = COLOR_MODERN_ROYAL

    for idx, item in enumerate(bullets):
        bp = cell.add_paragraph()
        bp.paragraph_format.space_before = Pt(1)
        bp.paragraph_format.space_after = Pt(2 if idx < len(bullets) - 1 else 0)
        bp.paragraph_format.line_spacing = 1.12
        r = bp.add_run(f"• {item}")
        r.font.name = FONT_FAMILY
        r.font.size = Pt(8.5)
        r.font.color.rgb = COLOR_TEXT_DARK


def _set_cell_all_borders(cell: Any, color_hex: str, sz: int = 4, val: str = "single") -> None:
    spec = (color_hex, sz, val)
    _set_cell_borders(cell, top=spec, bottom=spec, left=spec, right=spec)


def _clear_table_borders(table: Any) -> None:
    tbl_pr = table._tbl.tblPr
    for existing in tbl_pr.findall(qn("w:tblBorders")):
        tbl_pr.remove(existing)
    tbl_pr.append(
        parse_xml(
            f'<w:tblBorders {nsdecls("w")}>'
            '  <w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            '  <w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
            "</w:tblBorders>"
        )
    )


def build_modern_lesson_plan_docx(
    plan_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """
    Generate the Executive Standard (4Cs & VARK) A4 .docx lesson plan matching
    the attached Primary School Lesson Plan template layout.
    """
    meta = plan_data.get("meta", {})
    header = plan_data.get("header", {})
    stages: List[Dict[str, Any]] = plan_data.get("stages", [])
    exit_ticket = plan_data.get("exit_ticket", "")
    reflection = plan_data.get("self_reflection", {})

    duration_minutes = int(
        meta.get("duration_minutes")
        or sum(int(st.get("minutes", 0) or 0) for st in stages)
        or (60 if str(meta.get("grade", "")).upper() in ("3PS", "4PS") else 45)
    )
    raw_grade = str(meta.get("grade", "5PS")).upper()
    spaced_grade = f"{raw_grade[0]} {raw_grade[1:]}" if len(raw_grade) >= 3 and raw_grade.endswith("PS") else raw_grade

    doc = Document()
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Mm(12.7)
    section.bottom_margin = Mm(12.7)
    section.left_margin = Mm(12.7)
    section.right_margin = Mm(12.7)
    section.header_distance = Mm(6)
    section.footer_distance = Mm(6)

    normal_style = doc.styles["Normal"]
    normal_style.font.name = FONT_FAMILY
    normal_style.font.size = Pt(9.0)
    normal_style.font.color.rgb = COLOR_TEXT_DARK

    # -----------------------------------------------------------------------
    # BLOCK 1: DARK NAVY BANNER WITH ROYAL BLUE LEFT ACCENT STRIPE
    # -----------------------------------------------------------------------
    banner = doc.add_table(rows=1, cols=1)
    banner.alignment = WD_TABLE_ALIGNMENT.CENTER
    banner.autofit = False
    _clear_table_borders(banner)
    b_cell = banner.rows[0].cells[0]
    _set_cell_width_mm(b_cell, USABLE_WIDTH_MM)
    _set_cell_shading(b_cell, HEX_MODERN_NAVY)
    _set_cell_borders(
        b_cell,
        top=(HEX_MODERN_NAVY, 6, "single"),
        bottom=(HEX_MODERN_NAVY, 6, "single"),
        right=(HEX_MODERN_NAVY, 6, "single"),
        left=(HEX_MODERN_BLUE, 36, "single"),
    )
    _set_cell_margins(b_cell, top_dxa=130, bottom_dxa=130, left_dxa=180, right_dxa=140)
    _prevent_row_split(banner.rows[0])

    p_title = b_cell.paragraphs[0]
    p_title.paragraph_format.space_before = Pt(0)
    p_title.paragraph_format.space_after = Pt(2)
    r_title = p_title.add_run(f"PRIMARY SCHOOL LESSON PLAN — {spaced_grade}")
    r_title.bold = True
    r_title.font.name = FONT_FAMILY
    r_title.font.size = Pt(14.0)
    r_title.font.color.rgb = COLOR_WHITE

    p_sub = b_cell.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(0)
    r_sub = p_sub.add_run(
        f"Primary Education Framework | {header.get('sequence', '')} | {header.get('section', '')}"
    )
    r_sub.font.name = FONT_FAMILY
    r_sub.font.size = Pt(8.5)
    r_sub.font.color.rgb = COLOR_MODERN_SUBTITLE

    sp1 = doc.add_paragraph()
    sp1.paragraph_format.space_before = Pt(0)
    sp1.paragraph_format.space_after = Pt(4)

    # -----------------------------------------------------------------------
    # BLOCK 2: 5-ROW METADATA GRID
    # -----------------------------------------------------------------------
    meta_tbl = doc.add_table(rows=0, cols=4)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_tbl.autofit = False
    _set_table_borders(
        meta_tbl,
        outer_color=HEX_MODERN_BORDER,
        inner_color=HEX_MODERN_BORDER,
        outer_sz=6,
        inner_sz=4,
    )
    m_widths = [32.0, 60.3, 32.0, 60.3]  # sums to 184.6 mm

    teacher_val = header.get("teacher_name") or f"{header.get('class_profile', '')} (Time: {duration_minutes} mn)"
    top_meta_rows = [
        ("Teacher:", teacher_val, "Level:", header.get("level", "")),
        ("Sequence:", header.get("sequence", ""), "Section:", header.get("section", "")),
        ("Session:", header.get("session", ""), "Domains:", header.get("domains", "")),
    ]
    for l1, v1, l2, v2 in top_meta_rows:
        row = meta_tbl.add_row()
        _prevent_row_split(row)
        for idx, w in enumerate(m_widths):
            _set_cell_width_mm(row.cells[idx], w)
            _set_cell_margins(row.cells[idx], top_dxa=60, bottom_dxa=60, left_dxa=85, right_dxa=85)
        _set_cell_shading(row.cells[0], HEX_MODERN_SLATE_BG)
        _set_cell_shading(row.cells[1], HEX_WHITE)
        _set_cell_shading(row.cells[2], HEX_MODERN_SLATE_BG)
        _set_cell_shading(row.cells[3], HEX_WHITE)
        _write_cell_text(row.cells[0], l1, bold=True, font_size=8.5, color=COLOR_MODERN_NAVY)
        _write_cell_text(row.cells[1], str(v1), font_size=8.5)
        _write_cell_text(row.cells[2], l2, bold=True, font_size=8.5, color=COLOR_MODERN_NAVY)
        _write_cell_text(row.cells[3], str(v2), font_size=8.5)

    for label, val in (
        ("Target Competency:", header.get("target_competence", "")),
        ("Materials:", header.get("teaching_materials", "")),
    ):
        row = meta_tbl.add_row()
        _prevent_row_split(row)
        c0 = row.cells[0]
        c1 = row.cells[1]
        c1.merge(row.cells[3])
        _set_cell_width_mm(c0, m_widths[0])
        _set_cell_width_mm(c1, USABLE_WIDTH_MM - m_widths[0])
        _set_cell_margins(c0, top_dxa=60, bottom_dxa=60, left_dxa=85, right_dxa=85)
        _set_cell_margins(c1, top_dxa=60, bottom_dxa=60, left_dxa=85, right_dxa=85)
        _set_cell_shading(c0, HEX_MODERN_SLATE_BG)
        _set_cell_shading(c1, HEX_WHITE)
        _write_cell_text(c0, label, bold=True, font_size=8.5, color=COLOR_MODERN_NAVY)
        _write_cell_text(c1, str(val), font_size=8.5)

    sp2 = doc.add_paragraph()
    sp2.paragraph_format.space_before = Pt(0)
    sp2.paragraph_format.space_after = Pt(4)

    # -----------------------------------------------------------------------
    # BLOCK 3: 2x2 OBJECTIVES & ANTICIPATED PROBLEMS / SOLUTIONS CARD
    # -----------------------------------------------------------------------
    card_tbl = doc.add_table(rows=2, cols=3)
    card_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    card_tbl.autofit = False
    _set_table_borders(
        card_tbl,
        outer_color=HEX_MODERN_BORDER,
        inner_color=HEX_MODERN_SLATE_BG,
        outer_sz=6,
        inner_sz=0,
    )
    card_widths = [89.3, 6.0, 89.3]  # sums to 184.6 mm

    for r_idx in range(2):
        row = card_tbl.rows[r_idx]
        _prevent_row_split(row)
        for c_idx in range(3):
            cell = row.cells[c_idx]
            _set_cell_width_mm(cell, card_widths[c_idx])
            _set_cell_shading(cell, HEX_MODERN_SLATE_BG)
            _set_cell_margins(cell, top_dxa=95, bottom_dxa=95, left_dxa=110, right_dxa=110)
            if r_idx == 0:
                _set_cell_borders(
                    cell,
                    top=(HEX_MODERN_BORDER, 6, "single"),
                    bottom=(HEX_MODERN_BORDER, 4, "dashed"),
                    left=(HEX_MODERN_BORDER, 6, "single") if c_idx == 0 else (HEX_MODERN_SLATE_BG, 0, "none"),
                    right=(HEX_MODERN_BORDER, 6, "single") if c_idx == 2 else (HEX_MODERN_SLATE_BG, 0, "none"),
                )
            else:
                _set_cell_borders(
                    cell,
                    top=(HEX_MODERN_BORDER, 4, "dashed"),
                    bottom=(HEX_MODERN_BORDER, 6, "single"),
                    left=(HEX_MODERN_BORDER, 6, "single") if c_idx == 0 else (HEX_MODERN_SLATE_BG, 0, "none"),
                    right=(HEX_MODERN_BORDER, 6, "single") if c_idx == 2 else (HEX_MODERN_SLATE_BG, 0, "none"),
                )

    _write_modern_card_block(
        card_tbl.rows[0].cells[0],
        "SESSION OBJECTIVES",
        _split_bullet_items(header.get("session_objectives", ""), max_items=2),
    )
    _write_modern_card_block(
        card_tbl.rows[0].cells[2],
        "SUBSIDIARY OBJECTIVES",
        _split_bullet_items(
            f"{header.get('subsidiary_objectives', '')}; Phonics: {header.get('phonics_focus', '')}",
            max_items=2,
        ),
    )
    _write_modern_card_block(
        card_tbl.rows[1].cells[0],
        "ANTICIPATED PROBLEMS",
        _split_bullet_items(header.get("anticipated_problems", ""), max_items=2),
    )
    _write_modern_card_block(
        card_tbl.rows[1].cells[2],
        "SOLUTIONS",
        _split_bullet_items(header.get("solutions_plan_b", ""), max_items=2),
    )

    # -----------------------------------------------------------------------
    # BLOCK 4: CROSS-CURRICULAR & 21ST-CENTURY SKILLS (4CS)
    # -----------------------------------------------------------------------
    _add_modern_section_heading(doc, "CROSS-CURRICULAR & 21ST-CENTURY SKILLS (4CS)")

    skills_tbl = doc.add_table(rows=1, cols=7)
    skills_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    skills_tbl.autofit = False
    _clear_table_borders(skills_tbl)
    _prevent_row_split(skills_tbl.rows[0])

    skill_w = [43.9, 3.0, 43.9, 3.0, 43.9, 3.0, 43.9]  # sums to 184.6 mm
    skills_4cs = [
        ("COMMUNICATION", "Oral & written message sharing"),
        ("COLLABORATION", "Pair & small-group teamwork"),
        ("CRITICAL THINKING", "Noticing patterns & guessing"),
        ("CREATIVITY", "Role-play, games & projects"),
    ]
    for idx, width in enumerate(skill_w):
        cell = skills_tbl.rows[0].cells[idx]
        _set_cell_width_mm(cell, width)
        if idx % 2 == 1:
            _set_cell_margins(cell, top_dxa=20, bottom_dxa=20, left_dxa=0, right_dxa=0)
            _write_cell_text(cell, "", font_size=6.0)
        else:
            title_4c, desc_4c = skills_4cs[idx // 2]
            _set_cell_shading(cell, HEX_WHITE)
            _set_cell_all_borders(cell, HEX_MODERN_BORDER, sz=6, val="single")
            _set_cell_margins(cell, top_dxa=75, bottom_dxa=75, left_dxa=75, right_dxa=75)
            p_s = cell.paragraphs[0]
            p_s.paragraph_format.space_before = Pt(0)
            p_s.paragraph_format.space_after = Pt(2)
            rs1 = p_s.add_run(title_4c)
            rs1.bold = True
            rs1.font.name = FONT_FAMILY
            rs1.font.size = Pt(7.8)
            rs1.font.color.rgb = COLOR_MODERN_LINK
            p_d = cell.add_paragraph()
            p_d.paragraph_format.space_before = Pt(0)
            p_d.paragraph_format.space_after = Pt(0)
            rs2 = p_d.add_run(desc_4c)
            rs2.font.name = FONT_FAMILY
            rs2.font.size = Pt(7.5)
            rs2.font.color.rgb = COLOR_TEXT_MUTED

    # -----------------------------------------------------------------------
    # BLOCK 5: LESSON EXECUTION STAGES TABLE
    # -----------------------------------------------------------------------
    _add_modern_section_heading(doc, "LESSON EXECUTION STAGES")

    exec_widths = [25.0, 31.0, 84.6, 22.0, 22.0]  # sums to 184.6 mm
    exec_headers = ["Stage", "Sub-Objectives", "Procedure Tasks", "Interaction", "Time / VARK"]

    exec_tbl = doc.add_table(rows=6, cols=5)
    exec_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    exec_tbl.autofit = False
    _set_table_borders(
        exec_tbl,
        outer_color=HEX_MODERN_BORDER,
        inner_color=HEX_MODERN_BORDER,
        outer_sz=8,
        inner_sz=4,
    )

    # Header row
    hdr_row = exec_tbl.rows[0]
    _repeat_header_row(hdr_row)
    _prevent_row_split(hdr_row)
    for c_idx, col_title in enumerate(exec_headers):
        cell = hdr_row.cells[c_idx]
        _set_cell_width_mm(cell, exec_widths[c_idx])
        _set_cell_shading(cell, HEX_MODERN_NAVY)
        _set_cell_margins(cell, top_dxa=90, bottom_dxa=90, left_dxa=80, right_dxa=80)
        _write_cell_text(
            cell,
            col_title,
            bold=True,
            font_size=8.5,
            color=COLOR_WHITE,
            align=WD_ALIGN_PARAGRAPH.CENTER if c_idx >= 3 else WD_ALIGN_PARAGRAPH.LEFT,
        )

    mapped = _map_stages_to_modern_execution(stages, duration_minutes)
    topic_label = meta.get("topic") or header.get("section", "the topic")
    sub_obj_map = {
        "warmer": f"Activate prior knowledge & warm up for {topic_label}",
        "presentation": f"Introduce context, vocabulary & sounds for {topic_label}",
        "practice": "Drill and reinforce target chunks & phonics accurately",
        "production": "Apply learned language in guided/communicative tasks",
        "assessment": f"Check mastery of {topic_label} & Exit Ticket reflection",
    }

    row_specs = [
        (1, "Warming up\n(Preparation)", "", mapped["warmer"], sub_obj_map["warmer"]),
        (2, "Installing\nresources", "Presentation", mapped["presentation"], sub_obj_map["presentation"]),
        (3, "", "Practice", mapped["practice"], sub_obj_map["practice"]),
        (4, "", "Production", mapped["production"], sub_obj_map["production"]),
        (5, "Assessment", "", mapped["assessment"], sub_obj_map["assessment"]),
    ]

    for row_idx, stage_lbl, sub_heading, data, sub_obj in row_specs:
        row = exec_tbl.rows[row_idx]
        proc_body = data["procedure"]
        if row_idx == 5 and exit_ticket and "ticket" not in proc_body.lower():
            proc_body = f"{proc_body}\n{exit_ticket}".strip()

        full_proc = f"{sub_heading}\n{proc_body}".strip() if sub_heading else proc_body
        if len(full_proc.splitlines()) <= 16:
            _prevent_row_split(row)

        for c_idx in range(5):
            _set_cell_width_mm(row.cells[c_idx], exec_widths[c_idx])
            _set_cell_shading(row.cells[c_idx], HEX_WHITE)
            _set_cell_margins(row.cells[c_idx], top_dxa=75, bottom_dxa=75, left_dxa=80, right_dxa=80)

        if stage_lbl:
            _write_cell_text(
                row.cells[0],
                stage_lbl,
                bold=True,
                font_size=8.5,
                color=COLOR_MODERN_NAVY,
                valign=WD_ALIGN_VERTICAL.TOP,
            )

        _write_cell_text(
            row.cells[1],
            sub_obj,
            font_size=8.2,
            color=COLOR_TEXT_DARK,
            valign=WD_ALIGN_VERTICAL.TOP,
        )

        # Render optional bold sub-heading (Presentation / Practice / Production) + rich prefixes
        p_cell = row.cells[2]
        p_cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        if sub_heading:
            p0 = p_cell.paragraphs[0]
            p0.paragraph_format.space_before = Pt(0)
            p0.paragraph_format.space_after = Pt(2.5)
            rh = p0.add_run(sub_heading)
            rh.bold = True
            rh.font.name = FONT_FAMILY
            rh.font.size = Pt(8.8)
            rh.font.color.rgb = COLOR_MODERN_NAVY
            for ln in proc_body.splitlines():
                if not ln.strip():
                    continue
                pl = p_cell.add_paragraph()
                pl.paragraph_format.space_before = Pt(0)
                pl.paragraph_format.space_after = Pt(1.8)
                pl.paragraph_format.line_spacing = 1.12
                m = _RICH_PREFIX_RE.match(ln)
                if m:
                    pr = pl.add_run(m.group(1) + (" " if m.group(2) else ""))
                    pr.bold = True
                    pr.font.name = FONT_FAMILY
                    pr.font.size = Pt(8.3)
                    pr.font.color.rgb = COLOR_MODERN_ROYAL
                    if m.group(2):
                        rr = pl.add_run(m.group(2))
                        rr.font.name = FONT_FAMILY
                        rr.font.size = Pt(8.3)
                        rr.font.color.rgb = COLOR_TEXT_DARK
                else:
                    rr = pl.add_run(ln)
                    rr.font.name = FONT_FAMILY
                    rr.font.size = Pt(8.3)
                    rr.font.color.rgb = COLOR_TEXT_DARK
        else:
            _write_cell_text(
                p_cell,
                proc_body,
                font_size=8.3,
                color=COLOR_TEXT_DARK,
                valign=WD_ALIGN_VERTICAL.TOP,
                space_after=1.8,
                rich_prefixes=True,
            )

        _write_cell_text(
            row.cells[3],
            data["interaction"],
            font_size=8.2,
            color=COLOR_TEXT_DARK,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            valign=WD_ALIGN_VERTICAL.TOP,
        )

        vark = _infer_vark_tags(proc_body)
        _write_cell_text(
            row.cells[4],
            f"{data['minutes']} mn\n{vark}",
            bold=True,
            font_size=8.2,
            color=COLOR_MODERN_ROYAL,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            valign=WD_ALIGN_VERTICAL.TOP,
        )

    # Vertically merge rows 2..4 in Stage column ("Installing resources")
    exec_tbl.rows[2].cells[0].merge(exec_tbl.rows[4].cells[0])

    # -----------------------------------------------------------------------
    # BLOCK 6: TEACHER SELF-REFLECTION / ACTION POINTS (DASHED BOXES)
    # -----------------------------------------------------------------------
    _add_modern_section_heading(doc, "TEACHER SELF-REFLECTION / ACTION POINTS")

    ref_tbl = doc.add_table(rows=1, cols=3)
    ref_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    ref_tbl.autofit = False
    _clear_table_borders(ref_tbl)
    _prevent_row_split(ref_tbl.rows[0])
    _set_row_min_height(ref_tbl.rows[0], 16.0)

    ref_widths = [89.8, 5.0, 89.8]  # sums to 184.6 mm
    for idx, w in enumerate(ref_widths):
        cell = ref_tbl.rows[0].cells[idx]
        _set_cell_width_mm(cell, w)
        if idx == 1:
            _set_cell_margins(cell, top_dxa=20, bottom_dxa=20, left_dxa=0, right_dxa=0)
            _write_cell_text(cell, "", font_size=6.0)
        else:
            _set_cell_shading(cell, HEX_WHITE)
            _set_cell_all_borders(cell, HEX_MODERN_DASHED, sz=6, val="dashed")
            _set_cell_margins(cell, top_dxa=85, bottom_dxa=85, left_dxa=100, right_dxa=100)
            title_r = "What Worked Well?" if idx == 0 else "What Hindered? / Action Points"
            val_r = (
                reflection.get("what_worked", "")
                if idx == 0
                else f"{reflection.get('what_hindered', '')}\n{reflection.get('action_plan', '')}".strip()
            )
            p_rf = cell.paragraphs[0]
            p_rf.paragraph_format.space_before = Pt(0)
            p_rf.paragraph_format.space_after = Pt(4)
            r_hdr = p_rf.add_run(title_r)
            r_hdr.bold = True
            r_hdr.font.name = FONT_FAMILY
            r_hdr.font.size = Pt(8.5)
            r_hdr.font.color.rgb = COLOR_MODERN_NAVY
            if val_r and "[To be completed" not in val_r:
                p_rv = cell.add_paragraph()
                r_val = p_rv.add_run(val_r)
                r_val.font.name = FONT_FAMILY
                r_val.font.size = Pt(8.2)
                r_val.font.color.rgb = COLOR_TEXT_MUTED

    # -----------------------------------------------------------------------
    # BLOCK 7: STANDARD 3-PART FOOTER
    # -----------------------------------------------------------------------
    footer = section.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
    fp.paragraph_format.space_before = Pt(3)
    fp.paragraph_format.space_after = Pt(0)

    from docx.enum.text import WD_TAB_ALIGNMENT  # local import keeps top imports clean

    fp.paragraph_format.tab_stops.add_tab_stop(Mm(USABLE_WIDTH_MM / 2), WD_TAB_ALIGNMENT.CENTER)
    fp.paragraph_format.tab_stops.add_tab_stop(Mm(USABLE_WIDTH_MM), WD_TAB_ALIGNMENT.RIGHT)

    fp_pr = fp._p.get_or_add_pPr()
    fp_pr.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'  <w:top w:val="single" w:sz="6" w:space="4" w:color="{HEX_MODERN_BORDER}"/>'
            f"</w:pBdr>"
        )
    )

    r_f1 = fp.add_run("Primary Education Standard Document\tLesson Plan Template\tPage ")
    r_f1.font.name = FONT_FAMILY
    r_f1.font.size = Pt(8.0)
    r_f1.font.color.rgb = COLOR_TEXT_MUTED

    _add_field(fp, "PAGE", font_size=8.0, color=COLOR_TEXT_MUTED)

    r_f2 = fp.add_run(" of ")
    r_f2.font.name = FONT_FAMILY
    r_f2.font.size = Pt(8.0)
    r_f2.font.color.rgb = COLOR_TEXT_MUTED

    _add_field(fp, "NUMPAGES", font_size=8.0, color=COLOR_TEXT_MUTED)

    # -----------------------------------------------------------------------
    # SAVE TO DISK
    # -----------------------------------------------------------------------
    if output_path is None:
        tmp_dir = tempfile.mkdtemp(prefix="aitadz_docx_")
        filename = generate_clean_filename(
            meta.get("grade", "3PS"),
            int(meta.get("sequence_number", 1) or 1),
            meta.get("session_title", "LessonPlan"),
        )
        output_path = os.path.join(tmp_dir, filename)
    else:
        parent = os.path.dirname(os.path.abspath(output_path))
        if parent:
            os.makedirs(parent, exist_ok=True)

    doc.save(output_path)
    return output_path


def build_lesson_plan_docx(
    plan_data: Dict[str, Any],
    output_path: Optional[str] = None,
    template_id: Optional[str] = None,
) -> str:
    """
    Dispatch lesson plan DOCX generation to either:
      - 'classic' -> AITADZ Classic Didactic template
      - 'modern'  -> Executive Standard (4Cs & VARK) template
    """
    resolved = normalize_template_id(
        template_id or plan_data.get("meta", {}).get("template_id") or "classic"
    )
    if resolved == "modern":
        return build_modern_lesson_plan_docx(plan_data, output_path=output_path)
    return build_classic_lesson_plan_docx(plan_data, output_path=output_path)
