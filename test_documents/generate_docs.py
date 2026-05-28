"""Generate sample vendor test documents as PDFs using reportlab."""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import os

OUT = os.path.dirname(__file__)

styles = getSampleStyleSheet()
title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=16, spaceAfter=6)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceAfter=4)
normal = styles["Normal"]
small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)
center = ParagraphStyle("Center", parent=styles["Normal"], alignment=TA_CENTER)
bold = ParagraphStyle("Bold", parent=styles["Normal"], fontName="Helvetica-Bold")


def doc(filename):
    return SimpleDocTemplate(
        os.path.join(OUT, filename),
        pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )


def kv_table(data, col_widths=(70*mm, 100*mm)):
    t = Table([[Paragraph(f"<b>{k}</b>", normal), Paragraph(v, normal)] for k, v in data], colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


# ─── India: Certificate of Incorporation ─────────────────────────────────────
def gen_coi_india():
    d = doc("india_coi.pdf")
    story = [
        Paragraph("MINISTRY OF CORPORATE AFFAIRS", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("(Under the Companies Act, 2013)", center),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=1, color=colors.navy),
        Spacer(1, 6*mm),
        Paragraph("This is to certify that <b>NEXOVA TECHNOLOGIES PRIVATE LIMITED</b> is incorporated under the Companies Act, 2013 and the company is limited by shares.", normal),
        Spacer(1, 6*mm),
        kv_table([
            ("Company Name", "NEXOVA TECHNOLOGIES PRIVATE LIMITED"),
            ("CIN", "U72200MH2015PTC267736"),
            ("Date of Incorporation", "15/03/2015"),
            ("State of Incorporation", "Maharashtra"),
            ("Registered Office", "404, Tech Park, Andheri East, Mumbai, Maharashtra - 400069"),
            ("Type of Company", "Private Company Limited by Shares"),
            ("Authorised Capital", "INR 10,00,000"),
        ]),
        Spacer(1, 10*mm),
        Paragraph("Given under my hand at Mumbai, this Fifteenth day of March, Two Thousand and Fifteen.", normal),
        Spacer(1, 14*mm),
        Paragraph("Sd/-", normal),
        Paragraph("<b>Registrar of Companies, Mumbai</b>", normal),
        Paragraph("Ministry of Corporate Affairs", small),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 4*mm),
        Paragraph("This document is digitally issued. Verify at mca.gov.in. CIN: U72200MH2015PTC267736", small),
    ]
    d.build(story)
    print("Generated india_coi.pdf")


# ─── India: PAN + GSTIN Certificate ──────────────────────────────────────────
def gen_pan_gstin_india():
    d = doc("india_pan_gstin.pdf")
    story = [
        Paragraph("INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("Permanent Account Number (PAN) Card", title_style),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.darkblue),
        Spacer(1, 6*mm),
        kv_table([
            ("Name of Assessee", "NEXOVA TECHNOLOGIES PRIVATE LIMITED"),
            ("PAN", "AABCT3518Q"),
            ("Date of Birth / Incorporation", "15/03/2015"),
            ("Father's / Founder's Name", "RAJESH KUMAR SHARMA"),
            ("Status", "COMPANY"),
        ]),
        Spacer(1, 10*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 6*mm),
        Paragraph("GST NETWORK (GSTN) — GOVERNMENT OF INDIA", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("GST Registration Certificate", h2),
        Spacer(1, 4*mm),
        kv_table([
            ("Legal Name of Business", "NEXOVA TECHNOLOGIES PRIVATE LIMITED"),
            ("GSTIN", "27AABCT3518Q1ZK"),
            ("PAN", "AABCT3518Q"),
            ("State", "Maharashtra"),
            ("GST State Code", "27"),
            ("Registration Type", "Regular"),
            ("Date of Registration", "01/04/2017"),
            ("Place of Business", "404, Tech Park, Andheri East, Mumbai - 400069"),
        ]),
        Spacer(1, 10*mm),
        Paragraph("Issued by GST Council. Verify at gst.gov.in using GSTIN: 27AABCT3518Q1ZK", small),
    ]
    d.build(story)
    print("Generated india_pan_gstin.pdf")


# ─── India: Bank Letter ───────────────────────────────────────────────────────
def gen_bank_letter_india():
    d = doc("india_bank_letter.pdf")
    story = [
        Paragraph("HDFC BANK LIMITED", title_style),
        Paragraph("Branch: Andheri East, Mumbai — IFSC: HDFC0000007", center),
        Paragraph("CIN: L65920MH1994PLC080618 | Registered Office: HDFC Bank House, Senapati Bapat Marg, Mumbai 400013", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003087")),
        Spacer(1, 6*mm),
        Paragraph("<b>TO WHOMSOEVER IT MAY CONCERN</b>", center),
        Paragraph("<b>BANK ACCOUNT CONFIRMATION LETTER</b>", ParagraphStyle("ch", parent=styles["Normal"], alignment=TA_CENTER, fontSize=13, fontName="Helvetica-Bold")),
        Spacer(1, 6*mm),
        Paragraph("This is to certify that the following bank account is maintained with HDFC Bank Limited, Andheri East Branch:", normal),
        Spacer(1, 4*mm),
        kv_table([
            ("Account Holder Name", "NEXOVA TECHNOLOGIES PRIVATE LIMITED"),
            ("Account Number", "50200045678901"),
            ("Account Type", "Current Account"),
            ("Bank Name", "HDFC Bank Limited"),
            ("Branch", "Andheri East, Mumbai"),
            ("IFSC Code", "HDFC0000007"),
            ("MICR Code", "400240019"),
            ("Date of Opening", "20/03/2015"),
            ("Account Status", "Active"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("This letter is issued at the request of the account holder for vendor registration purposes.", normal),
        Spacer(1, 14*mm),
        Paragraph("Authorised Signatory", normal),
        Paragraph("<b>Branch Manager — HDFC Bank, Andheri East</b>", normal),
        Paragraph("Date: 10/05/2026", small),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("HDFC Bank is regulated by the Reserve Bank of India. This letter is computer-generated and valid without a physical signature.", small),
    ]
    d.build(story)
    print("Generated india_bank_letter.pdf")


# ─── UK: Company Registration Certificate ────────────────────────────────────
def gen_registration_uk():
    d = doc("uk_registration.pdf")
    story = [
        Paragraph("COMPANIES HOUSE — HM GOVERNMENT", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("on formation of a private limited company", center),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#00703c")),
        Spacer(1, 6*mm),
        Paragraph("The Registrar of Companies for England and Wales hereby certifies that <b>MERIDIAN CONSULTING LIMITED</b> is this day incorporated under the Companies Act 2006.", normal),
        Spacer(1, 6*mm),
        kv_table([
            ("Company Name", "MERIDIAN CONSULTING LIMITED"),
            ("Company Number", "09876543"),
            ("Date of Incorporation", "20 June 2018"),
            ("Country of Registration", "England and Wales"),
            ("Registered Office", "15 King Street, London, EC2V 8EA"),
            ("Company Type", "Private Limited Company"),
            ("SIC Code", "70229 — Management consultancy activities"),
        ]),
        Spacer(1, 10*mm),
        Paragraph("Given at Companies House, Cardiff, on 20 June 2018.", normal),
        Spacer(1, 14*mm),
        Paragraph("The Registrar of Companies", normal),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Verify this document at find-and-update.company-information.service.gov.uk. Company No: 09876543", small),
    ]
    d.build(story)
    print("Generated uk_registration.pdf")


# ─── UK: Bank Letter ──────────────────────────────────────────────────────────
def gen_bank_letter_uk():
    d = doc("uk_bank_letter.pdf")
    story = [
        Paragraph("NATWEST BANK PLC", title_style),
        Paragraph("250 Bishopsgate, London EC2M 4AA", center),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#501e60")),
        Spacer(1, 6*mm),
        Paragraph("<b>Bank Confirmation Letter</b>", ParagraphStyle("ch", parent=styles["Normal"], fontSize=13, fontName="Helvetica-Bold")),
        Spacer(1, 6*mm),
        Paragraph("To Whom It May Concern,", normal),
        Spacer(1, 4*mm),
        Paragraph("We confirm that the following account is held with NatWest Bank Plc:", normal),
        Spacer(1, 4*mm),
        kv_table([
            ("Account Name", "MERIDIAN CONSULTING LIMITED"),
            ("IBAN", "GB29NWBK60161331926819"),
            ("Sort Code", "60-16-13"),
            ("Account Number", "31926819"),
            ("Account Type", "Business Current Account"),
            ("Bank", "NatWest Bank Plc"),
            ("Branch", "City of London"),
            ("BIC / SWIFT", "NWBKGB2L"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("This letter is issued for vendor onboarding purposes only.", normal),
        Spacer(1, 14*mm),
        Paragraph("Relationship Manager, Business Banking", normal),
        Paragraph("<b>NatWest Bank Plc</b>", normal),
        Paragraph("Date: 12/05/2026", small),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("NatWest Bank Plc is authorised by the Prudential Regulation Authority and regulated by the FCA and PRA. Registered in England No. 929027.", small),
    ]
    d.build(story)
    print("Generated uk_bank_letter.pdf")


# ─── UK: VAT Certificate ──────────────────────────────────────────────────────
def gen_tax_uk():
    d = doc("uk_vat_certificate.pdf")
    story = [
        Paragraph("HM REVENUE & CUSTOMS", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("VAT Registration Certificate", title_style),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1d70b8")),
        Spacer(1, 6*mm),
        Paragraph("This certificate confirms that the business named below is registered for Value Added Tax (VAT) in the United Kingdom.", normal),
        Spacer(1, 6*mm),
        kv_table([
            ("Business Name", "MERIDIAN CONSULTING LIMITED"),
            ("VAT Registration Number", "GB294587123"),
            ("Company Number", "09876543"),
            ("Effective Date of Registration", "01/01/2019"),
            ("Tax Period", "Monthly"),
            ("Registered Address", "15 King Street, London, EC2V 8EA"),
            ("Business Activity", "Management Consultancy Services"),
            ("Scheme", "Standard VAT Accounting"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("This certificate is issued by HM Revenue & Customs. Please retain it for your records.", normal),
        Spacer(1, 14*mm),
        Paragraph("Controller of Her Majesty's Stationery Office", normal),
        Paragraph("<b>HM Revenue & Customs</b>", normal),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Verify VAT numbers at ec.europa.eu/vies or call HMRC on 0300 200 3700. VAT No: GB294587123", small),
    ]
    d.build(story)
    print("Generated uk_vat_certificate.pdf")


# ─── REJECTED CASE: GlobalTech Solutions (recently incorporated + foreign bank) ─
# Triggers rejection: company is 2 months old (< 6 months) AND bank is in UAE
# The credibility LLM will flag both as high-severity signals → risk_level = high → rejected

def gen_coi_globaltech():
    """GlobalTech Solutions: incorporated 2 months ago → recently incorporated flag."""
    d = doc("rejected_coi.pdf")
    story = [
        Paragraph("MINISTRY OF CORPORATE AFFAIRS", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("(Under the Companies Act, 2013)", center),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=1, color=colors.navy),
        Spacer(1, 6*mm),
        Paragraph("This is to certify that <b>GLOBALTECH SOLUTIONS PRIVATE LIMITED</b> is incorporated under the Companies Act, 2013 and the company is limited by shares.", normal),
        Spacer(1, 6*mm),
        kv_table([
            ("Company Name", "GLOBALTECH SOLUTIONS PRIVATE LIMITED"),
            ("CIN", "U74999DL2026PTC412001"),
            ("Date of Incorporation", "20/03/2026"),      # 2 months ago
            ("State of Incorporation", "Delhi"),
            ("Registered Office", "201, Connaught Place, New Delhi - 110001"),
            ("Type of Company", "Private Company Limited by Shares"),
            ("Authorised Capital", "INR 1,00,000"),
        ]),
        Spacer(1, 10*mm),
        Paragraph("Given under my hand at New Delhi, this Twentieth day of March, Two Thousand and Twenty-Six.", normal),
        Spacer(1, 14*mm),
        Paragraph("Sd/-", normal),
        Paragraph("<b>Registrar of Companies, Delhi</b>", normal),
        Paragraph("Ministry of Corporate Affairs", small),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("This document is digitally issued. Verify at mca.gov.in. CIN: U74999DL2026PTC412001", small),
    ]
    d.build(story)
    print("Generated rejected_coi.pdf")


def gen_pan_gstin_globaltech():
    """GlobalTech Solutions PAN and GSTIN certificate."""
    d = doc("rejected_pan_gstin.pdf")
    story = [
        Paragraph("INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("Permanent Account Number (PAN) Card", title_style),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.darkblue),
        Spacer(1, 6*mm),
        kv_table([
            ("Name of Assessee", "GLOBALTECH SOLUTIONS PRIVATE LIMITED"),
            ("PAN", "AABCG1234Q"),
            ("Date of Birth / Incorporation", "20/03/2026"),
            ("Father's / Founder's Name", "PRIYA MEHTA"),
            ("Status", "COMPANY"),
        ]),
        Spacer(1, 10*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 6*mm),
        Paragraph("GST NETWORK (GSTN) — GOVERNMENT OF INDIA", ParagraphStyle("gov", parent=styles["Normal"], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)),
        Paragraph("GST Registration Certificate", h2),
        Spacer(1, 4*mm),
        kv_table([
            ("Legal Name of Business", "GLOBALTECH SOLUTIONS PRIVATE LIMITED"),
            ("GSTIN", "07AABCG1234Q1ZD"),
            ("PAN", "AABCG1234Q"),
            ("State", "Delhi"),
            ("GST State Code", "07"),
            ("Registration Type", "Regular"),
            ("Date of Registration", "01/04/2026"),
            ("Place of Business", "201, Connaught Place, New Delhi - 110001"),
        ]),
        Spacer(1, 10*mm),
        Paragraph("Issued by GST Council. Verify at gst.gov.in using GSTIN: 07AABCG1234Q1ZD", small),
    ]
    d.build(story)
    print("Generated rejected_pan_gstin.pdf")


def gen_bank_letter_globaltech():
    """GlobalTech bank letter: UAE bank account → foreign bank flag."""
    d = doc("rejected_bank_letter.pdf")
    story = [
        Paragraph("EMIRATES NBD BANK P.J.S.C.", title_style),
        Paragraph("Baniyas Road, Deira, Dubai, UAE — SWIFT: EBILAEAD", center),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#c8971b")),
        Spacer(1, 6*mm),
        Paragraph("<b>TO WHOMSOEVER IT MAY CONCERN</b>", center),
        Paragraph("<b>BANK ACCOUNT CONFIRMATION LETTER</b>", ParagraphStyle("ch", parent=styles["Normal"], alignment=TA_CENTER, fontSize=13, fontName="Helvetica-Bold")),
        Spacer(1, 6*mm),
        Paragraph("This is to certify that the following bank account is maintained with Emirates NBD Bank P.J.S.C., Dubai Branch:", normal),
        Spacer(1, 4*mm),
        kv_table([
            ("Account Holder Name", "GLOBALTECH SOLUTIONS PRIVATE LIMITED"),
            ("Account Number", "1014844587001"),
            ("Account Type", "Current Account"),
            ("Bank Name", "Emirates NBD Bank P.J.S.C."),
            ("Branch", "Deira Corporate, Dubai, UAE"),
            ("IBAN", "AE070331234567890123456"),
            ("SWIFT / BIC", "EBILAEAD"),
            ("Currency", "AED"),
            ("Date of Opening", "10/04/2026"),
            ("Account Status", "Active"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("This letter is issued at the request of the account holder for vendor registration purposes.", normal),
        Spacer(1, 14*mm),
        Paragraph("Authorised Signatory", normal),
        Paragraph("<b>Business Banking — Emirates NBD, Deira Branch</b>", normal),
        Paragraph("Date: 15/05/2026", small),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Emirates NBD Bank is licensed by the UAE Central Bank. This letter is valid for 90 days from date of issue.", small),
    ]
    d.build(story)
    print("Generated rejected_bank_letter.pdf")


if __name__ == "__main__":
    gen_coi_india()
    gen_pan_gstin_india()
    gen_bank_letter_india()
    gen_registration_uk()
    gen_bank_letter_uk()
    gen_tax_uk()
    # Rejected test case: recently incorporated + foreign (UAE) bank
    gen_coi_globaltech()
    gen_pan_gstin_globaltech()
    gen_bank_letter_globaltech()
    print("\nAll documents generated in:", OUT)
