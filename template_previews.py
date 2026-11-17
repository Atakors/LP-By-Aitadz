"""
template_previews.py
====================
Generates crisp visual PNG preview cards for the two AITADZ lesson plan
templates ('classic' and 'modern') and a side-by-side comparison sheet so
teachers can preview both layouts directly inside Telegram before generating
their .docx file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent / "assets"

PREVIEW_PATHS = {
    "classic": ASSETS_DIR / "preview_classic.png",
    "modern": ASSETS_DIR / "preview_modern.png",
    "both": ASSETS_DIR / "preview_comparison.png",
}


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = (
        [
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _draw_dashed_rect(
    draw: ImageDraw.ImageDraw,
    box: Tuple[int, int, int, int],
    color: str,
    width: int = 2,
    dash: int = 8,
    gap: int = 6,
) -> None:
    x1, y1, x2, y2 = box
    # Top & Bottom
    for x in range(x1, x2, dash + gap):
        draw.line([(x, y1), (min(x + dash, x2), y1)], fill=color, width=width)
        draw.line([(x, y2), (min(x + dash, x2), y2)], fill=color, width=width)
    # Left & Right
    for y in range(y1, y2, dash + gap):
        draw.line([(x1, y), (x1, min(y + dash, y2))], fill=color, width=width)
        draw.line([(x2, y), (x2, min(y + dash, y2))], fill=color, width=width)


def _draw_dashed_hline(
    draw: ImageDraw.ImageDraw,
    x1: int,
    x2: int,
    y: int,
    color: str,
    width: int = 2,
    dash: int = 7,
    gap: int = 5,
) -> None:
    for x in range(x1, x2, dash + gap):
        draw.line([(x, y), (min(x + dash, x2), y)], fill=color, width=width)


def render_classic_preview(out_path: Path) -> Path:
    """Render A4 PNG mockup of the AITADZ Classic Didactic template."""
    W, H = 900, 1273
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)

    f_title = _load_font(20, bold=True)
    f_sub = _load_font(14, bold=True)
    f_sec = _load_font(15, bold=True)
    f_lbl = _load_font(12, bold=True)
    f_txt = _load_font(12, bold=False)
    f_xs = _load_font(11, bold=False)

    m = 48  # margin
    uw = W - 2 * m

    # Banner
    d.rectangle([m, 42, W - m, 88], fill="#0D1B2A")
    d.text((W // 2, 54), "PEOPLE'S DEMOCRATIC REPUBLIC OF ALGERIA • MINISTRY OF NATIONAL EDUCATION", fill="#FFFFFF", font=f_lbl, anchor="mm")
    d.text((W // 2, 74), "OFFICIAL PRIMARY SCHOOL ENGLISH LESSON PLAN (DIDACTIC GUIDE ALIGNED)", fill="#CBD5E1", font=f_xs, anchor="mm")

    d.rectangle([m, 88, W - m - 175, 146], fill="#0056D2")
    d.rectangle([W - m - 175, 88, W - m, 146], fill="#FF8C42")
    d.text((m + 14, 106), "AITADZ LESSON PLAN GENERATOR (aitadz.pro)", fill="#FFFFFF", font=f_sub)
    d.text((m + 14, 126), "Sequence 1: Jobs, Occupations & Hobbies  |  Section 1: Jobs", fill="#E2E8F0", font=f_xs)
    d.text((W - m - 87, 108), "5PS", fill="#FFFFFF", font=f_title, anchor="mm")
    d.text((W - m - 87, 130), "45 MINUTES", fill="#FFFFFF", font=f_lbl, anchor="mm")

    # Section 1: Metadata Grid
    y = 166
    d.text((m, y), "1. Official Didactic Metadata & Pedagogical Framing", fill="#0D1B2A", font=f_sec)
    d.line([(m, y + 22), (W - m, y + 22)], fill="#0056D2", width=3)
    y += 30
    row_h = 26
    meta_rows = [
        ("Level", "5PS - Year 5 Primary", "Class Profile", "5PS Primary Class"),
        ("Sequence", "Seq 1: Jobs & Hobbies", "Duration", "45 mn"),
        ("Session", "I Listen and Interact", "Domain(s)", "Oral Comp. / Oral Prod."),
    ]
    for idx, (l1, v1, l2, v2) in enumerate(meta_rows):
        bg = "#F5F7FA" if idx % 2 else "#FFFFFF"
        d.rectangle([m, y, W - m, y + row_h], fill=bg, outline="#3FA9F5", width=1)
        d.rectangle([m, y, m + 120, y + row_h], fill="#EDF5FF", outline="#3FA9F5")
        d.rectangle([m + uw // 2, y, m + uw // 2 + 120, y + row_h], fill="#EDF5FF", outline="#3FA9F5")
        d.text((m + 8, y + 7), l1, fill="#0D1B2A", font=f_lbl)
        d.text((m + 128, y + 7), v1, fill="#1E293B", font=f_txt)
        d.text((m + uw // 2 + 8, y + 7), l2, fill="#0D1B2A", font=f_lbl)
        d.text((m + uw // 2 + 128, y + 7), v2, fill="#1E293B", font=f_txt)
        y += row_h

    # Highlighted Objective row
    d.rectangle([m, y, W - m, y + 36], fill="#FFF7F0", outline="#3FA9F5", width=1)
    d.rectangle([m, y, m + 120, y + 36], fill="#0D1B2A")
    d.rectangle([m + 120, y, m + 125, y + 36], fill="#FF8C42")
    d.text((m + 8, y + 11), "Session Objective", fill="#FFFFFF", font=f_lbl)
    d.text((m + 132, y + 11), "By the end of the session, learners will be able to name jobs & ask about them.", fill="#0D1B2A", font=f_lbl)
    y += 36

    for lbl, val in (
        ("Core Values", "National Identity, National Conscience, Citizenship, Openness to the World"),
        ("Materials (VAKT)", "Flashcards, realia, audio script, whiteboard, slates, Gold Stars & Badges"),
    ):
        d.rectangle([m, y, W - m, y + 26], fill="#FFFFFF", outline="#3FA9F5", width=1)
        d.rectangle([m, y, m + 120, y + 26], fill="#EDF5FF", outline="#3FA9F5")
        d.text((m + 8, y + 7), lbl, fill="#0D1B2A", font=f_lbl)
        d.text((m + 128, y + 7), val, fill="#1E293B", font=f_txt)
        y += 26

    # Section 2: 5-Column Procedure Table
    y += 18
    d.text((m, y), "2. Stage-by-Stage Lesson Procedure (5-Column Grid)", fill="#0D1B2A", font=f_sec)
    d.line([(m, y + 22), (W - m, y + 22)], fill="#0056D2", width=3)
    y += 30
    cols = [68, 150, 360, 100, uw - 678]
    headers = ["Time", "Stage", "Procedure / Teacher & Learner Tasks", "Interaction", "Materials"]
    cx = m
    for cw, ht in zip(cols, headers):
        d.rectangle([cx, y, cx + cw, y + 28], fill="#0056D2", outline="#0D1B2A")
        d.text((cx + 8, y + 7), ht, fill="#FFFFFF", font=f_lbl)
        cx += cw
    y += 28

    proc_rows = [
        ("5 mn", "Stage 1: Warm-up", "Activity 1 (Quick Flash): Flash job cards; blend phonics.\nT: 'Look closely!' | Ls: Name jobs chorally.", "T-Ls", "Flashcards", 54),
        ("15 mn", "Stage 2: Install\nResources", "Activity 1 (Visual Context): Present doctor, farmer, teacher.\nListening Script: Amine & Lina dialogue (2 passes).\nActivity 2 (Choral/Ind. Drilling): Finger boundaries.", "T-Ls / Pair", "Audio, Puppets,\nFlashcards", 78),
        ("20 mn", "Stage 3: Practice\n& Production", "Activity 1 (Guided Pair Substitution): Ask & answer.\nActivity 2 (Star Challenge Game): Team Points & Badges.\nT: 'What is his job?' | Ls: 'He is a doctor!'", "Pair / Group", "Cue cards,\nStar Chart", 78),
        ("5 mn", "Stage 4: Exit Ticket", "Activity 1 (Ticket to Leave): Oral check + smiley card.", "Individual", "Stickers", 42),
    ]
    for r_i, (tm, stg, prc, itr, mat, rh) in enumerate(proc_rows):
        bg = "#F5F7FA" if r_i % 2 else "#FFFFFF"
        cx = m
        for cw, txt, col in zip(cols, [tm, stg, prc, itr, mat], ["#0056D2", "#0D1B2A", "#1E293B", "#1E293B", "#475569"]):
            d.rectangle([cx, y, cx + cw, y + rh], fill=bg, outline="#D0D9E6")
            ty = y + 8
            for ln in txt.splitlines():
                d.text((cx + 7, ty), ln, fill=col, font=f_lbl if cx == m or cx == m + cols[0] else f_xs)
                ty += 16
            cx += cw
        y += rh

    # Section 3: Gamification Callout
    y += 16
    d.text((m, y), "3. Formative Exit Ticket & Non-Monetary Classroom Motivation", fill="#0D1B2A", font=f_sec)
    d.line([(m, y + 22), (W - m, y + 22)], fill="#FF8C42", width=3)
    y += 30
    d.rectangle([m, y, m + 185, y + 36], fill="#FF8C42", outline="#FF8C42")
    d.rectangle([m + 185, y, W - m, y + 36], fill="#FFF7F0", outline="#FF8C42")
    d.text((m + 10, y + 11), "Non-Monetary Rewards", fill="#FFFFFF", font=f_lbl)
    d.text((m + 195, y + 11), "Gold Stars, Explorer Badges, Team Points, Stickers (zero monetary tokens).", fill="#0D1B2A", font=f_txt)
    y += 50

    # Section 4: 3-Panel Whiteboard Layout
    d.text((m, y), "4. Visual Whiteboard Layout Box (Left • Center • Right)", fill="#0D1B2A", font=f_sec)
    d.line([(m, y + 22), (W - m, y + 22)], fill="#3FA9F5", width=3)
    y += 30
    wb_w = uw // 3
    for i, (wt, wc) in enumerate([
        ("LEFT BOARD (Context & Lexis)", "Date | Seq 1 | Topic\nFlashcards & Vocabulary"),
        ("CENTER BOARD (Core Model)", "Model Chunks & Prompts\nPhonics / Reading Text"),
        ("RIGHT BOARD (Rewards & Slates)", "Team A: * * * | Team B: * * * (Stars)\nLearner Slate Practice Zone"),
    ]):
        bx = m + i * wb_w
        d.rectangle([bx, y, bx + wb_w, y + 26], fill="#0D1B2A", outline="#3FA9F5")
        d.rectangle([bx, y + 26, bx + wb_w, y + 84], fill="#F5F7FA" if i != 1 else "#FFFFFF", outline="#3FA9F5")
        d.text((bx + wb_w // 2, y + 13), wt, fill="#FFFFFF", font=f_xs, anchor="mm")
        ty = y + 36
        for ln in wc.splitlines():
            d.text((bx + 10, ty), ln, fill="#1E293B", font=f_xs)
            ty += 18
    y += 98

    # Section 5: Self-Reflection
    d.text((m, y), "5. Teacher Self-Reflection", fill="#0D1B2A", font=f_sec)
    y += 22
    for i, sr in enumerate(["What worked", "What hindered", "Action plan"]):
        bx = m + i * wb_w
        d.rectangle([bx, y, bx + wb_w, y + 24], fill="#0056D2", outline="#D0D9E6")
        d.rectangle([bx, y + 24, bx + wb_w, y + 58], fill="#F5F7FA", outline="#D0D9E6")
        d.text((bx + wb_w // 2, y + 12), sr, fill="#FFFFFF", font=f_xs, anchor="mm")

    # Footer
    d.line([(m, H - 50), (W - m, H - 50)], fill="#3FA9F5", width=2)
    d.text((W // 2, H - 32), "Generated by AITADZ Teacher Assistant (aitadz.pro)   •   Page 1 of 1", fill="#475569", font=f_lbl, anchor="mm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def render_modern_preview(out_path: Path) -> Path:
    """Render A4 PNG mockup matching the attached Executive Standard (4Cs & VARK) PDF."""
    W, H = 900, 1273
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)

    f_title = _load_font(22, bold=True)
    f_sec = _load_font(15, bold=True)
    f_lbl = _load_font(12, bold=True)
    f_txt = _load_font(12, bold=False)
    f_xs = _load_font(11, bold=False)

    m = 48
    uw = W - 2 * m

    # Dark Navy Banner with Royal Blue Left Stripe
    d.rounded_rectangle([m, 42, W - m, 118], radius=10, fill="#0F172A")
    d.rectangle([m, 42, m + 9, 118], fill="#2563EB")
    d.text((m + 24, 60), "PRIMARY SCHOOL LESSON PLAN — 5 PS", fill="#FFFFFF", font=f_title)
    d.text((m + 24, 90), "Primary Education Framework | Sequence 1: Jobs, Occupations & Hobbies | Section 1: Jobs", fill="#94A3B8", font=f_txt)

    # 5-Row Metadata Grid
    y = 136
    m_rows = [
        ("Teacher:", "5PS Primary Class", "Level:", "5PS - Year 5 Primary"),
        ("Sequence:", "Seq 1: Jobs & Hobbies", "Section:", "Section 1: Jobs"),
        ("Session:", "I Listen and Interact", "Domains:", "Oral Comp. / Oral Prod."),
    ]
    for l1, v1, l2, v2 in m_rows:
        d.rectangle([m, y, W - m, y + 26], fill="#FFFFFF", outline="#CBD5E1")
        d.rectangle([m, y, m + 120, y + 26], fill="#F8FAFC", outline="#CBD5E1")
        d.rectangle([m + uw // 2, y, m + uw // 2 + 120, y + 26], fill="#F8FAFC", outline="#CBD5E1")
        d.text((m + 10, y + 6), l1, fill="#0F172A", font=f_lbl)
        d.text((m + 128, y + 6), v1, fill="#1E293B", font=f_txt)
        d.text((m + uw // 2 + 10, y + 6), l2, fill="#0F172A", font=f_lbl)
        d.text((m + uw // 2 + 128, y + 6), v2, fill="#1E293B", font=f_txt)
        y += 26
    for lbl, val in (
        ("Target Competency:", "Comprehend short oral passages and interact orally using visual aids."),
        ("Materials:", "Flashcards, realia, audio script, whiteboard, slates, Gold Stars & Badges"),
    ):
        d.rectangle([m, y, W - m, y + 28], fill="#FFFFFF", outline="#CBD5E1")
        d.rectangle([m, y, m + 120, y + 28], fill="#F8FAFC", outline="#CBD5E1")
        d.text((m + 10, y + 7), lbl, fill="#0F172A", font=f_lbl)
        d.text((m + 128, y + 7), val, fill="#1E293B", font=f_txt)
        y += 28

    # 2x2 Objectives / Anticipated Problems & Solutions Card
    y += 14
    card_h = 166
    d.rounded_rectangle([m, y, W - m, y + card_h], radius=8, fill="#F8FAFC", outline="#CBD5E1", width=2)
    half = uw // 2
    # Top headers
    d.text((m + 18, y + 14), "SESSION OBJECTIVES", fill="#1E3A8A", font=f_sec)
    d.line([(m + 18, y + 34), (m + half - 14, y + 34)], fill="#2563EB", width=3)
    d.text((m + 18, y + 44), "• By the end of the session, learners will be able to", fill="#1E293B", font=f_xs)
    d.text((m + 26, y + 60), "name common jobs and ask about family members' jobs.", fill="#1E293B", font=f_xs)

    d.text((m + half + 14, y + 14), "SUBSIDIARY OBJECTIVES", fill="#1E3A8A", font=f_sec)
    d.line([(m + half + 14, y + 34), (W - m - 18, y + 34)], fill="#2563EB", width=3)
    d.text((m + half + 14, y + 44), "• Implicitly notice Present Simple chunks & word order.", fill="#1E293B", font=f_xs)
    d.text((m + half + 14, y + 60), "• Distinguish target phonics /ʒ/ vs /dʒ/ cleanly.", fill="#1E293B", font=f_xs)

    # Dashed mid divider
    _draw_dashed_hline(d, m + 16, W - m - 16, y + 90, "#CBD5E1", width=2)

    d.text((m + 18, y + 102), "ANTICIPATED PROBLEMS", fill="#1E3A8A", font=f_sec)
    d.line([(m + 18, y + 122), (m + half - 14, y + 122)], fill="#2563EB", width=3)
    d.text((m + 18, y + 134), "• Hesitation during pair speaking or L1 interference.", fill="#1E293B", font=f_xs)

    d.text((m + half + 14, y + 102), "SOLUTIONS", fill="#1E3A8A", font=f_sec)
    d.line([(m + half + 14, y + 122), (W - m - 18, y + 122)], fill="#2563EB", width=3)
    d.text((m + half + 14, y + 134), "• Choral-before-individual drills & Think-Pair-Share.", fill="#1E293B", font=f_xs)
    y += card_h + 18

    # Cross-Curricular & 21st-Century Skills (4Cs)
    d.text((m, y), "CROSS-CURRICULAR & 21ST-CENTURY SKILLS (4CS)", fill="#1E3A8A", font=f_sec)
    d.line([(m, y + 22), (W - m, y + 22)], fill="#2563EB", width=3)
    y += 32
    gap = 10
    box_w = (uw - 3 * gap) // 4
    for i, (stitle, sdesc) in enumerate([
        ("COMMUNICATION", "Oral & written exchange"),
        ("COLLABORATION", "Pair & group teamwork"),
        ("CRITICAL THINKING", "Noticing & guessing"),
        ("CREATIVITY", "Role-play & games"),
    ]):
        bx = m + i * (box_w + gap)
        d.rounded_rectangle([bx, y, bx + box_w, y + 48], radius=6, fill="#FFFFFF", outline="#CBD5E1", width=2)
        d.text((bx + 10, y + 10), stitle, fill="#1D4ED8", font=f_lbl)
        d.text((bx + 10, y + 28), sdesc, fill="#475569", font=f_xs)
    y += 66

    # Lesson Execution Stages
    d.text((m, y), "LESSON EXECUTION STAGES", fill="#1E3A8A", font=f_sec)
    d.line([(m, y + 22), (W - m, y + 22)], fill="#2563EB", width=3)
    y += 32
    ecols = [110, 140, 354, 100, uw - 704]
    eheaders = ["Stage", "Sub-Objectives", "Procedure Tasks", "Interaction", "Time / VARK"]
    cx = m
    for cw, ht in zip(ecols, eheaders):
        d.rectangle([cx, y, cx + cw, y + 30], fill="#0F172A", outline="#0F172A")
        d.text((cx + 8, y + 8), ht, fill="#FFFFFF", font=f_lbl)
        cx += cw
    y += 30

    # Warmer row
    rh = 54
    cx = m
    for cw, txt in zip(ecols, ["Warming up\n(Preparation)", "Activate prior lexis", "Activity 1 (Quick Flash): Flash job cards & blend sounds.\nT: 'Who is this?' | Ls: Reply chorally for Team Points.", "T-Ls", "5 mn\nV · A"]):
        d.rectangle([cx, y, cx + cw, y + rh], fill="#FFFFFF", outline="#CBD5E1")
        ty = y + 8
        for ln in txt.splitlines():
            d.text((cx + 7, ty), ln, fill="#0F172A" if cx == m else "#1E293B", font=f_lbl if cx == m else f_xs)
            ty += 16
        cx += cw
    y += rh

    # Installing resources (3 merged sub-rows: Presentation, Practice, Production)
    sub_rows = [
        ("Presentation", "Introduce context &\nlistening input", "Activity 1 (Visuals + Script): Present job flashcards & 4-line script.\nActivity 2 (Meaning Check): Oral Q&A without grammar rules.", "T-Ls / Ls-T", "15 mn\nV · A"),
        ("Practice", "Drill target chunks\n& phonics", "Activity 1 (Controlled Drills): Finger word boundaries & intonation.\nActivity 2 (Substitution Drill): Pairs swap job prompts.", "T-Ls / Pair", "10 mn\nA · K"),
        ("Production", "Communicate in\nreal-life tasks", "Activity 1 (Personalized Role-Play): Ask partner's family jobs.\nActivity 2 (Star Challenge): Earn Gold Stars & Explorer Badges.", "Pair / Group", "10 mn\nV · A · K"),
    ]
    sub_h = 62
    inst_y0 = y
    for sub_title, sobj, sproc, sintr, stv in sub_rows:
        cx = m + ecols[0]
        for cw, txt, has_sub in zip(ecols[1:], [sobj, sproc, sintr, stv], [False, True, False, False]):
            d.rectangle([cx, y, cx + cw, y + sub_h], fill="#FFFFFF", outline="#CBD5E1")
            ty = y + 8
            if has_sub:
                d.text((cx + 7, ty), sub_title, fill="#0F172A", font=f_lbl)
                ty += 17
            for ln in txt.splitlines():
                d.text((cx + 7, ty), ln, fill="#1E293B", font=f_xs)
                ty += 15
            cx += cw
        y += sub_h
    # Merged Stage 0 box
    d.rectangle([m, inst_y0, m + ecols[0], y], fill="#FFFFFF", outline="#CBD5E1")
    d.text((m + 8, inst_y0 + 12), "Installing\nresources", fill="#0F172A", font=f_lbl)

    # Assessment row
    arh = 48
    cx = m
    for cw, txt in zip(ecols, ["Assessment", "Check mastery &\nExit Ticket", "Activity 1 (Ticket to Leave): Share 1 job chunk + smiley card.", "Individual", "5 mn\nV · R"]):
        d.rectangle([cx, y, cx + cw, y + arh], fill="#FFFFFF", outline="#CBD5E1")
        ty = y + 8
        for ln in txt.splitlines():
            d.text((cx + 7, ty), ln, fill="#0F172A" if cx == m else "#1E293B", font=f_lbl if cx == m else f_xs)
            ty += 16
        cx += cw
    y += arh + 18

    # Self-Reflection Dashed Boxes
    d.text((m, y), "TEACHER SELF-REFLECTION / ACTION POINTS", fill="#1E3A8A", font=f_sec)
    d.line([(m, y + 22), (W - m, y + 22)], fill="#2563EB", width=3)
    y += 32
    box2_w = (uw - 16) // 2
    _draw_dashed_rect(d, (m, y, m + box2_w, y + 66), "#94A3B8", width=2)
    _draw_dashed_rect(d, (m + box2_w + 16, y, W - m, y + 66), "#94A3B8", width=2)
    d.text((m + 12, y + 12), "What Worked Well?", fill="#0F172A", font=f_lbl)
    d.text((m + box2_w + 28, y + 12), "What Hindered? / Action Points", fill="#0F172A", font=f_lbl)

    # Standard 3-Part Footer
    d.line([(m, H - 50), (W - m, H - 50)], fill="#CBD5E1", width=2)
    d.text((m, H - 32), "Primary Education Standard Document", fill="#475569", font=f_xs)
    d.text((W // 2, H - 32), "Lesson Plan Template", fill="#475569", font=f_xs, anchor="mm")
    d.text((W - m, H - 32), "Page 1 of 1", fill="#475569", font=f_xs, anchor="rm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def render_comparison_preview(
    classic_path: Path,
    modern_path: Path,
    out_path: Path,
) -> Path:
    """Combine both template previews side-by-side with clear selection headers."""
    c_img = Image.open(classic_path)
    m_img = Image.open(modern_path)

    pad = 36
    header_h = 84
    W = c_img.width + m_img.width + 3 * pad
    H = max(c_img.height, m_img.height) + header_h + 2 * pad
    canvas = Image.new("RGB", (W, H), "#E2E8F0")
    d = ImageDraw.Draw(canvas)

    f_badge = _load_font(24, bold=True)
    f_hint = _load_font(16, bold=False)

    # Left Card Header: Classic
    lx = pad
    d.rounded_rectangle([lx, pad, lx + c_img.width, pad + 56], radius=10, fill="#0056D2")
    d.text((lx + c_img.width // 2, pad + 28), "1. AITADZ CLASSIC DIDACTIC TEMPLATE", fill="#FFFFFF", font=f_badge, anchor="mm")
    d.rectangle([lx - 2, pad + header_h - 2, lx + c_img.width + 2, pad + header_h + c_img.height + 2], outline="#94A3B8", width=2)
    canvas.paste(c_img, (lx, pad + header_h))

    # Right Card Header: Modern
    rx = 2 * pad + c_img.width
    d.rounded_rectangle([rx, pad, rx + m_img.width, pad + 56], radius=10, fill="#0F172A")
    d.rectangle([rx, pad, rx + 10, pad + 56], fill="#2563EB")
    d.text((rx + m_img.width // 2, pad + 28), "2. EXECUTIVE STANDARD (4Cs & VARK) TEMPLATE", fill="#FFFFFF", font=f_badge, anchor="mm")
    d.rectangle([rx - 2, pad + header_h - 2, rx + m_img.width + 2, pad + header_h + m_img.height + 2], outline="#94A3B8", width=2)
    canvas.paste(m_img, (rx, pad + header_h))

    d.text((W // 2, H - 18), "Tap a button below in Telegram to select your preferred A4 DOCX template.", fill="#334155", font=f_hint, anchor="mm")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, format="PNG")
    return out_path


def ensure_preview_assets(force: bool = False) -> None:
    classic_p = PREVIEW_PATHS["classic"]
    modern_p = PREVIEW_PATHS["modern"]
    both_p = PREVIEW_PATHS["both"]

    if force or not classic_p.exists():
        render_classic_preview(classic_p)
    if force or not modern_p.exists():
        render_modern_preview(modern_p)
    if force or not both_p.exists():
        render_comparison_preview(classic_p, modern_p, both_p)


def get_preview_image_path(kind: str = "both") -> str:
    """Return path to 'classic', 'modern', or side-by-side 'both' PNG preview."""
    normalized = (kind or "both").strip().lower()
    if normalized not in PREVIEW_PATHS:
        normalized = "both"
    ensure_preview_assets(force=False)
    return str(PREVIEW_PATHS[normalized])


if __name__ == "__main__":
    ensure_preview_assets(force=True)
    for key, p in PREVIEW_PATHS.items():
        print(f"Generated {key}: {p}")
