import io
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

def export_to_docx(draft_text: str, category: str, addressed_to: str, disclaimer: str) -> io.BytesIO:
    """
    Generate a formatted Word document from the draft complaint and return as a bytes stream.
    """
    doc = Document()

    # Style definitions
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Times New Roman'
    font.size = Pt(12)

    # Document Header
    title = doc.add_paragraph()
    title_run = title.add_run("FORMAL COMPLAINT DRAFT")
    title_run.bold = True
    title_run.font.size = Pt(16)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f"Category: {category} Act Advisory").alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph().add_run("-" * 50).font.color.rgb = None

    # Addressed To Section
    doc.add_paragraph("TO,").runs[0].bold = True
    addr = doc.add_paragraph()
    addr_run = addr.add_run(addressed_to)
    addr_run.bold = True
    
    # Space before body
    doc.add_paragraph()

    # Body text
    body = doc.add_paragraph()
    body.add_run(draft_text)

    # Space before sign-off
    doc.add_paragraph()
    doc.add_paragraph()
    
    # Signature placeholder
    sig = doc.add_paragraph()
    sig.add_run("Dated: ____________________\n\nSignature of Complainant: ____________________")
    sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Page Break for Disclaimer
    doc.add_page_break()

    # Disclaimer Section
    disc_title = doc.add_paragraph()
    disc_title_run = disc_title.add_run("IMPORTANT LEGAL NOTICE")
    disc_title_run.bold = True
    disc_title_run.font.size = Pt(10)
    disc_title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    disc_p = doc.add_paragraph()
    disc_run = disc_p.add_run(disclaimer)
    disc_run.italic = True
    disc_run.font.size = Pt(10)
    disc_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Save to memory stream
    file_stream = io.BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    
    return file_stream
