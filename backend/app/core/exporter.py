"""
POSH/POCSO Complaint DOCX Exporter
====================================
Generates a formally-formatted Word document that matches the POSH complaint
template (posh_complaint_template.pdf).  POCSO complaints use their own mirror
layout; this module is shared but the POSH-specific rules only apply when
category == "POSH".

Design decisions (maps to user requirements)
--------------------------------------------
Req 1  – ONE title: bold Arial 14pt centred + grey 9pt subtitle.
          Never cross-contaminate Acts.
Req 2  – No typed separator lines (====, ----).  Real spacing / borders only.
Req 3  – Section headings: bold navy (#1F3864), Arial 11pt,
          space-before 10pt, space-after 4pt, keep-with-next.
Req 4  – Body: Arial 10pt, 1.15 line spacing, 1-inch margins.
Req 5  – Fields as borderless 2-column table (bold label | value + bottom border).
Req 6  – Missing value -> blank underlined cell.  Never print sentinel strings.
Req 7  – Section order: Addressed To, Date, 1-Complainant (split fields),
          2-Respondent, 3-Incident, 4-Witnesses (3-col table, light-blue
          header, >=3 rows), 5-Evidence, 6-Relief, 7-Declaration.
Req 8  – Canonical declaration: Section 16 wording + Section 14 warning +
          ONE signature block.
Req 9  – Disclaimer: 8pt grey italic, no bold heading, end of last page.
Req 10 – keep-with-next on headings; declaration + sig kept together.
Req 11 – (Post-generation PDF check: no wrapped separators / orphaned headings.)
"""

import io
import re
from datetime import date as _date
from typing import List, Optional

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
NAVY      = RGBColor(0x1F, 0x38, 0x64)   # req 3 heading colour
GREY_SUB  = RGBColor(0x59, 0x56, 0x59)   # req 1 grey subtitle
GREY_DISC = RGBColor(0x59, 0x59, 0x59)   # req 9 disclaimer text
BLACK     = RGBColor(0x00, 0x00, 0x00)


# ---------------------------------------------------------------------------
# Sentinel suppression (req 6)
# ---------------------------------------------------------------------------
_EMPTY_VALS = {
    "", "none", "null", "unknown", "not provided", "not specified",
    "unspecified", "none specified", "none provided", "none mentioned",
    "not applicable", "n/a",
    "[not provided / unspecified]", "[none specified]", "[none provided]",
    "[none mentioned]", "[not applicable]",
    "unspecified incident description.",
}


def _is_blank(val: Optional[str]) -> bool:
    """True when the value should be rendered as a blank underlined cell (req 6)."""
    if val is None:
        return True
    return val.strip().lower() in _EMPTY_VALS


def _clean(val: Optional[str]) -> str:
    """Return meaningful value or empty string."""
    if _is_blank(val):
        return ""
    return val.strip()


# ---------------------------------------------------------------------------
# Low-level XML helpers
# ---------------------------------------------------------------------------

def _set_cell_fill(cell, hex_color: str):
    """Solid background fill on a table cell (e.g. 'BDD7EE')."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


def _set_cell_border(cell, **kwargs):
    """
    Set individual borders on a table cell.
    kwargs keys: top, bottom, left, right — each a dict with
      sz (eighths-of-pt), val (border style), color.
    """
    tc       = cell._tc
    tcPr     = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side, attrs in kwargs.items():
        border = OxmlElement(f"w:{side}")
        border.set(qn("w:val"),   attrs.get("val", "single"))
        border.set(qn("w:sz"),    str(attrs.get("sz", 4)))
        border.set(qn("w:space"), "0")
        border.set(qn("w:color"), attrs.get("color", "000000"))
        tcBorders.append(border)
    tcPr.append(tcBorders)


def _no_table_borders(table):
    """Strip all outer/inner borders (borderless look)."""
    tbl  = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "none")
        el.set(qn("w:sz"),    "0")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "auto")
        tblBorders.append(el)
    existing = tblPr.find(qn("w:tblBorders"))
    if existing is not None:
        tblPr.remove(existing)
    tblPr.append(tblBorders)


def _light_table_borders(table):
    """Light grey borders for the witness table."""
    tbl   = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "AAAAAA")
        tblBorders.append(el)
    existing = tblPr.find(qn("w:tblBorders"))
    if existing is not None:
        tblPr.remove(existing)
    tblPr.append(tblBorders)


def _set_col_width(table, col_idx: int, width_inches: float):
    """Set preferred width for every cell in a column (in twips)."""
    twips = int(width_inches * 1440)
    for row in table.rows:
        cell = row.cells[col_idx]
        tc   = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcW  = OxmlElement("w:tcW")
        tcW.set(qn("w:w"),    str(twips))
        tcW.set(qn("w:type"), "dxa")
        existing = tcPr.find(qn("w:tcW"))
        if existing is not None:
            tcPr.remove(existing)
        tcPr.append(tcW)


def _keep_with_next(paragraph):
    """keepWithNext — heading stays with the first line of content (req 10)."""
    pPr = paragraph._p.get_or_add_pPr()
    pPr.append(OxmlElement("w:keepWithNext"))


def _keep_lines_together(paragraph):
    """keepLines — prevents a block from splitting across pages (req 10)."""
    pPr = paragraph._p.get_or_add_pPr()
    pPr.append(OxmlElement("w:keepLines"))


# ---------------------------------------------------------------------------
# Document-level setup
# ---------------------------------------------------------------------------

def _set_margins(doc, top=1.0, bottom=1.0, left=1.0, right=1.0):
    """1-inch margins all round (req 4)."""
    for section in doc.sections:
        section.top_margin    = Inches(top)
        section.bottom_margin = Inches(bottom)
        section.left_margin   = Inches(left)
        section.right_margin  = Inches(right)


def _setup_normal_style(doc):
    """
    Override Normal style: Arial 10pt, black, 1.15 line spacing (req 4).
    This cascades to all paragraphs that don't override it explicitly.
    """
    style = doc.styles["Normal"]
    f     = style.font
    f.name       = "Arial"
    f.size       = Pt(10)
    f.color.rgb  = BLACK
    pf = style.paragraph_format
    pf.line_spacing = Pt(11.5)   # 1.15 * 10 pt


# ---------------------------------------------------------------------------
# Paragraph builders
# ---------------------------------------------------------------------------

def _add_title(doc, category: str):
    """
    Req 1: ONE title block.
      Line 1 – bold, centred, Arial 14pt.
      Line 2 – full Act name, grey 9pt, centred.
    Never cross-contaminate POSH / POCSO.
    """
    if category == "POSH":
        title_text    = "FORMAL COMPLAINT UNDER THE POSH ACT, 2013"
        subtitle_text = (
            "Prevention of Sexual Harassment of Women at Workplace "
            "(Prevention, Prohibition and Redressal) Act, 2013"
        )
    else:
        title_text    = "FORMAL COMPLAINT UNDER THE POCSO ACT, 2012"
        subtitle_text = "Protection of Children from Sexual Offences Act, 2012"

    p1 = doc.add_paragraph()
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p1.add_run(title_text)
    r1.bold           = True
    r1.font.name      = "Arial"
    r1.font.size      = Pt(14)
    r1.font.color.rgb = BLACK
    p1.paragraph_format.space_before = Pt(0)
    p1.paragraph_format.space_after  = Pt(3)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(subtitle_text)
    r2.font.name      = "Arial"
    r2.font.size      = Pt(9)
    r2.font.color.rgb = GREY_SUB
    p2.paragraph_format.space_after = Pt(10)


def _add_section_heading(doc, text: str):
    """
    Req 3: bold, navy #1F3864, Arial 11pt,
    space-before 10pt, space-after 4pt, keep-with-next.
    """
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold           = True
    r.font.name      = "Arial"
    r.font.size      = Pt(11)
    r.font.color.rgb = NAVY
    pf = p.paragraph_format
    pf.space_before = Pt(10)
    pf.space_after  = Pt(4)
    _keep_with_next(p)
    return p


def _add_spacer(doc, pts: int = 4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(pts)
    return p


# ---------------------------------------------------------------------------
# Addressed-to / date block
# ---------------------------------------------------------------------------

def _add_addressed_to(doc, addressed_to: str):
    p1 = doc.add_paragraph()
    r1 = p1.add_run("To,")
    r1.bold      = True
    r1.font.name = "Arial"
    r1.font.size = Pt(10)
    p1.paragraph_format.space_after = Pt(2)

    p2 = doc.add_paragraph()
    r2 = p2.add_run(addressed_to or "")
    r2.bold      = True
    r2.font.name = "Arial"
    r2.font.size = Pt(10)
    p2.paragraph_format.space_after = Pt(6)


def _add_date_line(doc, date_str: str):
    p  = doc.add_paragraph()
    rb = p.add_run("Date of Complaint:  ")
    rb.bold      = True
    rb.font.name = "Arial"
    rb.font.size = Pt(10)
    rv = p.add_run(date_str)
    rv.font.name = "Arial"
    rv.font.size = Pt(10)
    p.paragraph_format.space_after = Pt(6)


# ---------------------------------------------------------------------------
# Field table builder (req 5, 6)
# ---------------------------------------------------------------------------

def _add_field_table(doc, rows: List[tuple]):
    """
    Borderless 2-column table (req 5).
    Col 0 (2.2 in): bold label.
    Col 1 (4.3 in): value or blank cell with bottom-border underline (req 6).
    """
    if not rows:
        return

    table = doc.add_table(rows=len(rows), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    _no_table_borders(table)
    _set_col_width(table, 0, 2.2)
    _set_col_width(table, 1, 4.3)

    for row_idx, (label, value) in enumerate(rows):
        row = table.rows[row_idx]
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        row.height      = Pt(18)

        # Label cell — no border
        lc = row.cells[0]
        lp = lc.paragraphs[0]
        lr = lp.add_run(label)
        lr.bold           = True
        lr.font.name      = "Arial"
        lr.font.size      = Pt(10)
        lr.font.color.rgb = BLACK
        lp.paragraph_format.space_before = Pt(2)
        lp.paragraph_format.space_after  = Pt(2)
        _set_cell_border(lc, bottom={"val": "none", "sz": 0, "color": "auto"})

        # Value cell — bottom border = underline effect (blank if no value)
        vc = row.cells[1]
        vp = vc.paragraphs[0]
        vr = vp.add_run(_clean(value))
        vr.font.name      = "Arial"
        vr.font.size      = Pt(10)
        vr.font.color.rgb = BLACK
        vp.paragraph_format.space_before = Pt(2)
        vp.paragraph_format.space_after  = Pt(2)
        _set_cell_border(vc, bottom={"val": "single", "sz": 4, "color": "AAAAAA"})

    _add_spacer(doc, 4)


# ---------------------------------------------------------------------------
# Witness table builder (req 4 / 7)
# ---------------------------------------------------------------------------

def _add_witness_table(doc, witnesses: List[str]):
    """
    3-column table (Name | Contact Details | Relevance) with a light-blue
    header row and at least 3 data rows (req 7).
    Populated witness names go in the Name column; the other cells are blank
    underlined rows for manual completion.
    """
    clean_wits = [w for w in witnesses if not _is_blank(w)]
    num_data   = max(len(clean_wits), 3)    # always >= 3 rows (req 7)

    table = doc.add_table(rows=1 + num_data, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    _light_table_borders(table)
    _set_col_width(table, 0, 2.0)
    _set_col_width(table, 1, 2.0)
    _set_col_width(table, 2, 2.5)

    # Header row — light-blue fill
    hdr = table.rows[0]
    for ci, col_name in enumerate(["Name", "Contact Details", "Relevance"]):
        cell = hdr.cells[ci]
        _set_cell_fill(cell, "BDD7EE")
        p = cell.paragraphs[0]
        r = p.add_run(col_name)
        r.bold           = True
        r.font.name      = "Arial"
        r.font.size      = Pt(10)
        r.font.color.rgb = NAVY
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after  = Pt(2)

    # Data rows
    for ri in range(num_data):
        row      = table.rows[ri + 1]
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        row.height      = Pt(20)
        name_val = clean_wits[ri] if ri < len(clean_wits) else ""
        for ci, val in enumerate([name_val, "", ""]):
            cell = row.cells[ci]
            p    = cell.paragraphs[0]
            r    = p.add_run(val)
            r.font.name = "Arial"
            r.font.size = Pt(10)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after  = Pt(2)

    _add_spacer(doc, 4)


# ---------------------------------------------------------------------------
# Declaration block (req 8)
# ---------------------------------------------------------------------------

DECLARATION_TEXT = (
    "I, the undersigned, hereby solemnly affirm and declare that:\n\n"
    "1.\u2003The information provided in this complaint is true and correct to the best of my "
    "knowledge, belief, and information, and nothing material has been concealed therefrom.\n\n"
    "2.\u2003I understand that under Section 16 of the Sexual Harassment of Women at Workplace "
    "(Prevention, Prohibition and Redressal) Act, 2013, the contents of this complaint, the "
    "identity of the complainant, respondent and witnesses, and any information relating to the "
    "conciliation and inquiry proceedings shall be kept strictly confidential and shall not be "
    "published, communicated or made known to the public, press or media in any manner.\n\n"
    "3.\u2003I am aware that if this complaint is found to be false or malicious, I may be liable "
    "for action under Section 14 of the Act, and such action shall not be a bar to any other "
    "remedy available under any law for the time being in force.\n\n"
    "4.\u2003I hereby consent to the Internal Committee conducting inquiry proceedings as per the "
    "provisions of the Act and the rules made thereunder."
)


def _add_declaration(doc):
    """Req 8: canonical declaration + ONE signature block immediately below."""
    _add_section_heading(doc, "7. Declaration")

    p = doc.add_paragraph()
    _keep_lines_together(p)
    r = p.add_run(DECLARATION_TEXT)
    r.font.name = "Arial"
    r.font.size = Pt(10)
    p.paragraph_format.space_after  = Pt(12)
    p.paragraph_format.line_spacing = Pt(13)

    # ONE signature block — borderless 2-column table kept with declaration
    sig_table = doc.add_table(rows=2, cols=2)
    _no_table_borders(sig_table)
    _set_col_width(sig_table, 0, 2.5)
    _set_col_width(sig_table, 1, 4.0)

    labels = [
        ("Signature of Complainant:", "________________________"),
        ("Date:",                     "________________________"),
    ]
    for ri, (lbl, line) in enumerate(labels):
        row = sig_table.rows[ri]
        lc, vc = row.cells[0], row.cells[1]

        lp = lc.paragraphs[0]
        lr = lp.add_run(lbl)
        lr.bold      = True
        lr.font.name = "Arial"
        lr.font.size = Pt(10)
        lp.paragraph_format.space_before = Pt(4)
        lp.paragraph_format.space_after  = Pt(4)
        if ri == 0:
            _keep_lines_together(lp)

        vp = vc.paragraphs[0]
        vr = vp.add_run(line)
        vr.font.name = "Arial"
        vr.font.size = Pt(10)
        vp.paragraph_format.space_before = Pt(4)
        vp.paragraph_format.space_after  = Pt(4)


# ---------------------------------------------------------------------------
# Disclaimer (req 9)
# ---------------------------------------------------------------------------

def _add_disclaimer(doc, disclaimer: str):
    """8pt grey italic text, no bold heading, appended at bottom of last page."""
    _add_spacer(doc, 8)
    p   = doc.add_paragraph()
    run = p.add_run(disclaimer)
    run.font.name      = "Arial"
    run.font.size      = Pt(8)
    run.font.color.rgb = GREY_DISC
    run.italic         = True
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(obj, key, default=None):
    """Safely get attribute or dict key."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class _ParsedFacts:
    """Simple namespace used when falling back to raw text parsing."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _parse_draft_text(text: str) -> "_ParsedFacts":
    """
    Last-resort parser: pull values from the plain-text string produced by
    format_standard_template().  Used only when facts=None is passed to
    export_to_docx().
    """
    def _ex(pattern, src, group=1):
        m = re.search(pattern, src, re.IGNORECASE | re.DOTALL)
        return m.group(group).strip() if m else None

    name     = _ex(r"Full Name[:\s]+(.+?)(?:\n|$)", text)
    resp     = _ex(r"2\..*?Full Name[:\s]+(.+?)(?:\n|$)", text)
    desig    = _ex(r"Designation[^:\n]*:[^\S\n]*(.+?)(?:\n|$)", text)
    inc_date = _ex(r"Date(?:/Time)?[^:\n]*:[^\S\n]*(.+?)(?:\n|$)", text)
    inc_loc  = _ex(r"(?:Place|Location)[^:\n]*:[^\S\n]*(.+?)(?:\n|$)", text)
    nature   = _ex(r"4\.\s*Description[^:]*:\n\s*(.+?)(?:\n\s*\n|\n\d\.)", text)
    wit_raw  = _ex(r"5\.\s*Witnesses[^:]*:\n\s*(.+?)(?:\n\s*\n|\n\d\.)", text)
    evid_raw = _ex(r"6\.\s*Evidence[^:]*:\n\s*(.+?)(?:\n\s*\n|\n\d\.)", text)

    witnesses = [w.strip() for w in wit_raw.split(",")  if w.strip()] if wit_raw  else []
    evidence  = [e.strip() for e in evid_raw.split(",") if e.strip()] if evid_raw else []

    return _ParsedFacts(
        complainant_name=name,
        complainant_age=None,
        complainant_emp_id=None,
        complainant_designation=None,
        complainant_department=None,
        complainant_contact=None,
        relationship_to_respondent=None,
        respondent_name=resp,
        respondent_designation=desig,
        respondent_department=None,
        respondent_organization=None,
        respondent_contact=None,
        incident_date=inc_date,
        incident_time=None,
        incident_location=inc_loc,
        nature_of_incident=nature,
        witnesses=witnesses,
        evidence_description=evidence,
    )


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def export_to_docx(
    draft_text: str,
    category: str,
    addressed_to: str,
    disclaimer: str,
    facts=None,
) -> io.BytesIO:
    """
    Generate a formatted DOCX complaint matching the POSH/POCSO template.

    Parameters
    ----------
    draft_text   : Raw text from format_standard_template().  Used only as
                   a fallback when *facts* is None.
    category     : "POSH" or "POCSO"
    addressed_to : Addressee string (printed after "To,")
    disclaimer   : Disclaimer text
    facts        : ExtractedFacts instance (preferred; avoids re-parsing)
    """
    cf = facts if facts is not None else _parse_draft_text(draft_text)

    doc = Document()
    _set_margins(doc)
    _setup_normal_style(doc)

    # ── Title (req 1) ─────────────────────────────────────────────────────────
    _add_title(doc, category)
    _add_spacer(doc, 6)

    # ── Addressed To ──────────────────────────────────────────────────────────
    _add_addressed_to(doc, addressed_to)

    # ── Date of Complaint ─────────────────────────────────────────────────────
    today = _date.today().strftime("%d %B %Y")
    _add_date_line(doc, today)
    _add_spacer(doc, 4)

    # ── Section 1: Complainant Details (req 7 — split fields) ─────────────────
    _add_section_heading(doc, "1. Complainant Details")

    comp_name    = _clean(_get(cf, "complainant_name"))
    comp_emp_id  = _clean(_get(cf, "complainant_emp_id"))
    comp_desig   = _clean(_get(cf, "complainant_designation"))
    comp_dept    = _clean(_get(cf, "complainant_department"))
    comp_contact = _clean(_get(cf, "complainant_contact"))
    comp_rel     = _clean(_get(cf, "relationship_to_respondent"))

    desig_dept = " / ".join(filter(None, [comp_desig, comp_dept]))

    _add_field_table(doc, [
        ("Full Name:",                    comp_name),
        ("Employee ID / Staff No.:",      comp_emp_id),
        ("Designation / Department:",     desig_dept),
        ("Contact Details:",              comp_contact),
        ("Relationship to Respondent:",   comp_rel),
    ])

    # ── Section 2: Respondent Details (req 7) ─────────────────────────────────
    _add_section_heading(doc, "2. Respondent / Accused Details")

    resp_name    = _clean(_get(cf, "respondent_name"))
    resp_desig   = _clean(_get(cf, "respondent_designation"))
    resp_dept    = _clean(_get(cf, "respondent_department"))
    resp_org     = _clean(_get(cf, "respondent_organization"))
    resp_contact = _clean(_get(cf, "respondent_contact"))

    resp_desig_dept = " / ".join(filter(None, [resp_desig, resp_dept]))

    _add_field_table(doc, [
        ("Full Name:",                resp_name),
        ("Designation / Department:", resp_desig_dept),
        ("Organization:",             resp_org),
        ("Contact Details:",          resp_contact),
    ])

    # ── Section 3: Incident Details (req 7) ───────────────────────────────────
    _add_section_heading(doc, "3. Incident Details")

    inc_date   = _clean(_get(cf, "incident_date"))
    inc_time   = _clean(_get(cf, "incident_time"))
    inc_loc    = _clean(_get(cf, "incident_location"))
    inc_nature = _clean(_get(cf, "nature_of_incident"))

    if inc_date and inc_time:
        date_time_val = f"{inc_date}  at  {inc_time}"
    else:
        date_time_val = inc_date or inc_time or ""

    _add_field_table(doc, [
        ("Date / Time of Incident:", date_time_val),
        ("Location of Incident:",    inc_loc),
        ("Nature of Incident:",      inc_nature),
    ])

    # ── Section 4: Witnesses (req 7 — always 3-column table, >=3 rows) ────────
    _add_section_heading(doc, "4. Witnesses (if any)")

    witnesses_raw = _get(cf, "witnesses") or []
    if isinstance(witnesses_raw, str):
        witnesses_raw = [w.strip() for w in witnesses_raw.split(",") if w.strip()]
    clean_wits = [w for w in witnesses_raw if not _is_blank(w)]
    _add_witness_table(doc, clean_wits)

    # ── Section 5: Evidence (req 7) ───────────────────────────────────────────
    _add_section_heading(doc, "5. Evidence / Supporting Documents")

    evidence_raw = _get(cf, "evidence_description") or []
    if isinstance(evidence_raw, str):
        evidence_raw = [e.strip() for e in evidence_raw.split(",") if e.strip()]
    clean_evid   = [e for e in evidence_raw if not _is_blank(e)]
    evidence_val = "; ".join(clean_evid) if clean_evid else ""

    _add_field_table(doc, [
        ("Evidence / Attachments:", evidence_val),
    ])

    # ── Section 6: Relief / Action Sought (req 7) ─────────────────────────────
    _add_section_heading(doc, "6. Relief / Action Sought")

    relief_items = [
        "Immediate inquiry into the complaint as per the provisions of the Act.",
        "Appropriate interim measures (e.g., transfer, paid leave, restraint order) pending inquiry.",
        "Disciplinary action against the Respondent commensurate with the gravity of the offence.",
        "Any other relief deemed fit and proper in the interest of justice.",
    ]
    for item in relief_items:
        p = doc.add_paragraph(style="List Bullet")
        r = p.add_run(item)
        r.font.name = "Arial"
        r.font.size = Pt(10)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after  = Pt(1)

    _add_spacer(doc, 4)

    # ── Section 7: Declaration + ONE signature block (req 8) ──────────────────
    _add_declaration(doc)

    # ── Disclaimer (req 9) ────────────────────────────────────────────────────
    _add_disclaimer(doc, disclaimer)

    # Serialize
    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)
    return stream
