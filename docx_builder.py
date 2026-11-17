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


def build_lesson_plan_docx(
    plan_data: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """
    Generate a print-ready branded A4 .docx lesson plan following the AITADZ
    brand palette and official Algerian Didactic Guide layout.

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
