import os
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


def generate_letter_content(complaint: Dict[str, Any], citizen_info: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Generates standard formal grievance letter content based on complaint details.
    """
    citizen_info = citizen_info or {}
    citizen_name = citizen_info.get("name") or complaint.get("citizen_name") or "Concerned Citizen"
    citizen_phone = citizen_info.get("phone") or complaint.get("citizen_phone") or "Not provided"
    citizen_email = citizen_info.get("email") or complaint.get("citizen_email") or "Not provided"
    
    complaint_no = complaint.get("complaint_no", "CF-PENDING")
    category = complaint.get("category", "Public Grievance")
    location = complaint.get("location", "Local Area")
    description = complaint.get("description", "")
    department_name = complaint.get("department_name") or "Municipal Authority"
    today_str = datetime.now().strftime("%B %d, %Y")

    subject = f"URGENT GRIEVANCE: Rectification of {category} at {location} [Grievance Ref: {complaint_no}]"

    recipient = f"To,\nThe Competent Officer / Executive Engineer,\n{department_name},\nLocal Municipal Administration / Ward Authority"

    body = (
        f"Respected Sir / Madam,\n\n"
        f"I am writing as a resident and taxpayer to formally lodge a public grievance regarding a severe "
        f"issue of '{category}' prevailing at {location}.\n\n"
        f"Detailed Description of the Issue:\n"
        f"\"{description}\"\n\n"
        f"This civic condition is causing significant hardship, safety hazards, and inconvenience to pedestrians, "
        f"motorists, and local residents. As per municipal service standards and citizen charter guidelines, "
        f"it falls within the operational scope of your department to inspect and rectify this matter promptly.\n\n"
        f"I kindly request an on-site inspection and immediate corrective action at the earliest possible time. "
        f"Please provide an update or acknowledgement citing the reference number mentioned above.\n\n"
        f"Thank you for your dedication to public welfare.\n\n"
        f"Yours sincerely,\n"
        f"{citizen_name}\n"
        f"Contact: {citizen_phone} | Email: {citizen_email}\n"
        f"Location of Grievance: {location}"
    )

    return {
        "complaint_no": complaint_no,
        "date": today_str,
        "subject": subject,
        "recipient": recipient,
        "body": body,
        "citizen_name": citizen_name,
        "citizen_phone": citizen_phone,
        "citizen_email": citizen_email,
        "department_name": department_name,
        "category": category,
        "location": location
    }


def generate_letter_pdf(letter_data: Dict[str, Any], output_path: str) -> str:
    """
    Renders an official, beautifully styled PDF grievance letter using ReportLab.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1E3A8A')  # Dark Blue
    )

    sub_header_style = ParagraphStyle(
        'SubHeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#4B5563')
    )

    meta_style = ParagraphStyle(
        'MetaStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#374151')
    )

    meta_right = ParagraphStyle(
        'MetaRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#1E3A8A')
    )

    subject_style = ParagraphStyle(
        'SubjectStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=10
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=16,
        alignment=TA_LEFT,
        textColor=colors.HexColor('#1F2937'),
        spaceAfter=8
    )

    disclaimer_style = ParagraphStyle(
        'DisclaimerStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#6B7280')
    )

    elements = []

    # Title & Subtitle
    elements.append(Paragraph("CIVICFIX AI — OFFICIAL GRIEVANCE LETTER", header_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Smart Public Grievance Guidance System | Citizen Redressal Document", sub_header_style))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#1E3A8A'), spaceBefore=2, spaceAfter=14))

    # Reference Number & Date Table
    meta_table_data = [
        [
            Paragraph(f"<b>Grievance Ref No:</b> {letter_data.get('complaint_no', 'N/A')}", meta_style),
            Paragraph(f"<b>Date:</b> {letter_data.get('date', datetime.now().strftime('%B %d, %Y'))}", meta_right)
        ]
    ]
    meta_table = Table(meta_table_data, colWidths=[300, 204])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 14))

    # Recipient
    recipient_lines = letter_data.get("recipient", "").split("\n")
    for line in recipient_lines:
        if line.strip():
            elements.append(Paragraph(f"<b>{line.strip()}</b>" if line.startswith("To,") else line.strip(), meta_style))
    elements.append(Spacer(1, 14))

    # Subject line box
    subject_text = f"<b>SUBJECT:</b> {letter_data.get('subject', 'Civic Grievance')}"
    subject_table = Table([[Paragraph(subject_text, subject_style)]], colWidths=[504])
    subject_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(subject_table)
    elements.append(Spacer(1, 14))

    # Letter Body (render paragraph by paragraph)
    body_text = letter_data.get("body", "")
    paragraphs = body_text.split("\n\n")
    for p in paragraphs:
        cleaned_p = p.strip().replace("\n", "<br/>")
        if cleaned_p:
            elements.append(Paragraph(cleaned_p, body_style))
            elements.append(Spacer(1, 6))

    elements.append(Spacer(1, 16))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E5E7EB'), spaceBefore=10, spaceAfter=8))
    
    # Disclaimer
    elements.append(Paragraph(
        "Note: Generated via CivicFix AI. Department recommendations are rule-based and subject to verification by your local municipal corporation or ward authority jurisdiction.",
        disclaimer_style
    ))

    doc.build(elements)
    return output_path
