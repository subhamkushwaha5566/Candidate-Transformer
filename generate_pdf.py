import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def build_pdf():
    pdf_filename = "SubhamKushwaha_subhamkushwaha5566@gmail.com_Eightfold.pdf"
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        leftMargin=30,
        rightMargin=30,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    
    # Custom compact styles for slate theme
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#1A202C")
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#4A5568")
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=6,
        spaceAfter=2
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.2,
        leading=9.5,
        textColor=colors.HexColor("#2D3748")
    )

    story = []

    # Title & Metadata block
    story.append(Paragraph("TECHNICAL DESIGN: MULTI-SOURCE CANDIDATE DATA TRANSFORMER", title_style))
    story.append(Paragraph("Author: Subham Kushwaha &nbsp;|&nbsp; Email: subhamkushwaha5566@gmail.com &nbsp;|&nbsp; Target: Eightfold Engineering Intern Assignment", subtitle_style))
    story.append(Spacer(1, 4))

    # Section 1: Ingestion & Processing Pipeline
    story.append(Paragraph("1. Ingestion & Transformation Pipeline", h1_style))
    p1_text = (
        "The transformer operates as a deterministic, multi-stage processing pipeline built on Clean Architecture principles:<br/>"
        "<b>• Ingest & Parse:</b> Raw byte streams are read by file type (Pandas for recruiter CSV exports; pdfplumber and regex for unstructured PDF resumes) and extracted into intermediate dictionary records.<br/>"
        "<b>• Cleanse & Normalize:</b> Normalizes phone numbers (E.164 via phonenumbers library), country names/codes (ISO-3166-1 alpha-2 via pycountry), date fields (standardizes 'Jan 2024' or 'Present' to YYYY-MM), and canonicalizes skills.<br/>"
        "<b>• Merge & Deduplicate:</b> Unifies overlapping candidate records based on source confidence weights (CSV = 0.95, Resume = 0.85, Notes = 0.60). Arrays are unioned, and nested object trees are recursively merged.<br/>"
        "<b>• Score Confidence:</b> Computes profile completeness based on presence of key profile attributes weighted by the source's trust score.<br/>"
        "<b>• Project to Schema:</b> Filters, renames paths, and formats the output dynamically at runtime based on the projection configuration.<br/>"
        "<b>• Validate:</b> Ensures final structural integrity and JSON serializability, degrading gracefully on missing optional fields."
    )
    story.append(Paragraph(p1_text, body_style))
    story.append(Spacer(1, 3))

    # Section 2: Canonical Output Schema
    story.append(Paragraph("2. Canonical Output Schema & Normalizations", h1_style))
    p2_text = (
        "The pipeline resolves messy inputs into a single canonical candidate profile adhering to standard schemas:<br/>"
        "<b>• candidate_id</b> (string) & <b>full_name</b> (string) & <b>headline</b> (string or null). &nbsp;<b>• emails</b> (list of lowercase strings) & <b>phones</b> (E.164 strings).<br/>"
        "<b>• location:</b> Structured city, region, and ISO alpha-2 country code. &nbsp;<b>• links:</b> Structure with linkedin, github, portfolio, and other list.<br/>"
        "<b>• skills:</b> Structured as <font face='Courier'>[ { name, confidence, sources[] } ]</font> representing canonical skill names, max confidence, and contributing sources.<br/>"
        "<b>• experience:</b> Structured as <font face='Courier'>[ { company, title, start, end, summary } ]</font> (dates formatted as YYYY-MM).<br/>"
        "<b>• education:</b> Structured as <font face='Courier'>[ { institution, degree, field, end_year } ]</font> (graduation year formatted as YYYY).<br/>"
        "<b>• provenance:</b> Structured as <font face='Courier'>[ { field, source, method } ]</font> to track precisely where each field value came from and the extraction method used.<br/>"
        "<b>• overall_confidence:</b> Calculated completeness metric based on presence of key profile attributes weighted by the source's trust score."
    )
    story.append(Paragraph(p2_text, body_style))
    story.append(Spacer(1, 3))

    # Section 3: Merge, Conflict Resolution & Trust Assignment
    story.append(Paragraph("3. Merge, Conflict Resolution & Trust Policy", h1_style))
    p3_text = (
        "Candidate duplicates are resolved across sources by sorting the raw candidate segments in descending order of source confidence. "
        "For scalar values (e.g. name, headline, location), the highest-trust source value is selected, and its origin is logged in the provenance tracker. "
        "Arrays (emails, phones, other links) are deduplicated and combined. Overlapping experience and education entries are matched by key (e.g., company+title) "
        "and non-empty values are merged.<br/>"
        "<b>Core Philosophy: 'Wrong-but-confident is worse than honestly-empty.'</b><br/>"
        "To protect downstream hiring systems, empty/null values are preferred over guessed or default-filled records. "
        "The Normalizer enforces strict validation: phone numbers that are impossible are set to null; date strings that cannot be formatted are left empty; "
        "and unmapped countries are set to null instead of loading dummy placehoders. Invalid data segments are discarded early rather than polluting downstream profiles."
    )
    story.append(Paragraph(p3_text, body_style))
    story.append(Spacer(1, 3))

    # Section 4: Runtime Config & Projection Layer
    story.append(Paragraph("4. Runtime Custom-Output Configuration", h1_style))
    p4_text = (
        "The pipeline supports a projection config payload that reshapes output structures without altering code logic:<br/>"
        "<b>• Subsetting & Renaming:</b> Resolves field selections, including list indicators (<font face='Courier'>emails[0]</font>) and wildcards (<font face='Courier'>skills[].name</font>). "
        "Paths are resolved into target keys (e.g., mapping <font face='Courier'>phones[0]</font> to <font face='Courier'>phone</font>).<br/>"
        "<b>• Metadata Toggles:</b> The config toggle can strip or retain the <font face='Courier'>provenance</font> and <font face='Courier'>overall_confidence</font> sections dynamically.<br/>"
        "<b>• Missing Values:</b> Controls behavior when selected fields are empty. <font face='Courier'>on_missing</font> enum options are: "
        "<i>null</i> (retains field with null value), <i>omit</i> (removes key from output dictionary), or <i>error</i> (raises HTTP 400 validation error)."
    )
    story.append(Paragraph(p4_text, body_style))
    story.append(Spacer(1, 3))

    # Section 5: Edge Cases & Descoping
    story.append(Paragraph("5. Handled Edge Cases & Scope Limits", h1_style))
    p5_text = (
        "<b>• Malformed/Corrupt Uploads:</b> Blank files or bad CSV columns are intercepted via try-except guards inside pandas, degrading to empty records.<br/>"
        "<b>• Impossible Phone Formats:</b> Multi-region format parsing catches invalid length strings, returning None to satisfy the honestly-empty principle.<br/>"
        "<b>• Ambiguous Dates:</b> Standalone years and sentinel values ('Present', 'Current') are normalized uniformly without crashing calculations.<br/>"
        "<b>• List Wildcard Path Projects:</b> Resolves list-comprehension paths dynamically (e.g., mapping lists of skill objects to flat string arrays).<br/>"
        "<b>• Deliberately Descoped under Time Constraints:</b> GitHub and LinkedIn live API calls were descoped in favor of robust local PDF resume "
        "parsing. The ingestion of complex DOCX files was also postponed, with all text parser engines designed around standard PDF structures."
    )
    story.append(Paragraph(p5_text, body_style))

    # Build the document
    doc.build(story)
    print(f"Successfully generated PDF: {pdf_filename}")

if __name__ == "__main__":
    build_pdf()
