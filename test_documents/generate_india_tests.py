"""
India-specific vendor test cases — 5 companies.

TC1  PRISM SOFTWARE SOLUTIONS      APPROVED   — clean submission, zero failures
TC2  BRIGHTWAVE LOGISTICS           PENDING    — Individual PAN (P) submitted for a company
TC3  KIRAN HEALTH SYSTEMS           PENDING    — GSTIN state code (09=UP) ≠ registered state (Delhi)
TC4  FALCON DYNAMICS                REJECTED   — GSTIN/PAN mismatch + bank account belongs to different entity
TC5  SHREE KRISHNA EXPORTS          REJECTED   — Two GSTIN failures (state+PAN mismatch) + foreign Singapore bank

PAN checksum algorithm (verified for every PAN below):
  weights = [2,4,6,8,10,3,5,7,9]
  char_val: A=0…Z=25, digit=face value
  checksum_char = chr(ord('A') + (sum(val*weight) % 26))
"""

import json
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

OUT = os.path.dirname(__file__)

styles = getSampleStyleSheet()
title_style  = ParagraphStyle("T2",    parent=styles["Title"],   fontSize=15, spaceAfter=4)
h2           = ParagraphStyle("H2",    parent=styles["Heading2"],fontSize=11, spaceAfter=3)
normal       = styles["Normal"]
small        = ParagraphStyle("Sm",    parent=styles["Normal"],  fontSize=8,  textColor=colors.grey)
center       = ParagraphStyle("Ctr",   parent=styles["Normal"],  alignment=TA_CENTER)
bold         = ParagraphStyle("Bd",    parent=styles["Normal"],  fontName="Helvetica-Bold")
gov_style    = ParagraphStyle("Gov",   parent=styles["Normal"],  fontSize=9,  alignment=TA_CENTER, textColor=colors.grey)
warn_style   = ParagraphStyle("Warn",  parent=styles["Normal"],  fontSize=8,  textColor=colors.red)


def doc(filename: str):
    return SimpleDocTemplate(
        os.path.join(OUT, filename),
        pagesize=A4,
        rightMargin=20*mm, leftMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )


def kv_table(data, col_widths=(72*mm, 100*mm)):
    t = Table(
        [[Paragraph(f"<b>{k}</b>", normal), Paragraph(v, normal)] for k, v in data],
        colWidths=col_widths,
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4f8")),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ("PADDING",    (0, 0), (-1, -1), 5),
    ]))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# TC1 — PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED
# Expected: APPROVED
# PAN AABCP1234I: sum=242, 242%26=8 → I ✓
# GSTIN 29AABCP1234I1ZK: state=29=Karnataka ✓, embedded PAN=AABCP1234I ✓
# ─────────────────────────────────────────────────────────────────────────────

def gen_tc1_coi():
    d = doc("tc1_prism_coi.pdf")
    d.build([
        Paragraph("MINISTRY OF CORPORATE AFFAIRS — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("(Under the Companies Act, 2013)", center),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 5*mm),
        Paragraph(
            "This is to certify that <b>PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED</b> is duly "
            "incorporated under the Companies Act, 2013 and is limited by shares.",
            normal,
        ),
        Spacer(1, 5*mm),
        kv_table([
            ("Company Name",        "PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED"),
            ("CIN",                 "U72200KA2018PTC098765"),
            ("Date of Incorporation","15/03/2018"),
            ("State of Incorporation","Karnataka"),
            ("Registered Office",   "Plot 12, Electronic City Phase I, Bengaluru, Karnataka - 560100"),
            ("Type of Company",     "Private Company Limited by Shares"),
            ("NIC Activity",        "72200 — Computer Programming, Consultancy"),
            ("Authorised Capital",  "INR 50,00,000"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("Given under my hand at Bengaluru this Fifteenth day of March, Two Thousand and Eighteen.", normal),
        Spacer(1, 10*mm),
        Paragraph("Sd/-", normal),
        Paragraph("<b>Registrar of Companies, Bengaluru</b>", normal),
        Paragraph("Ministry of Corporate Affairs", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Digitally issued. Verify at mca.gov.in  |  CIN: U72200KA2018PTC098765", small),
    ])
    print("  TC1  tc1_prism_coi.pdf")


def gen_tc1_pan_gstin():
    d = doc("tc1_prism_pan_gstin.pdf")
    d.build([
        Paragraph("INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Permanent Account Number (PAN) Card", title_style),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003580")),
        Spacer(1, 4*mm),
        kv_table([
            ("Name of Assessee",              "PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED"),
            ("PAN",                           "AABCP1234I"),
            ("Date of Incorporation",         "15/03/2018"),
            ("Status",                        "COMPANY"),
            ("Father's / Founder's Name",     "ARJUN SHARMA"),
        ]),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 5*mm),
        Paragraph("GST NETWORK (GSTN) — GOVERNMENT OF INDIA", gov_style),
        Paragraph("GST Registration Certificate", h2),
        Spacer(1, 3*mm),
        kv_table([
            ("Legal Name of Business",        "PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED"),
            ("GSTIN",                         "29AABCP1234I1ZK"),
            ("PAN",                           "AABCP1234I"),
            ("State",                         "Karnataka"),
            ("GST State Code",                "29"),
            ("Registration Type",             "Regular"),
            ("Date of Registration",          "01/08/2018"),
            ("Place of Business",             "Plot 12, Electronic City Phase I, Bengaluru - 560100"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued by GST Council. Verify at gst.gov.in  |  GSTIN: 29AABCP1234I1ZK", small),
    ])
    print("  TC1  tc1_prism_pan_gstin.pdf")


def gen_tc1_bank():
    d = doc("tc1_prism_bank_letter.pdf")
    d.build([
        Paragraph("HDFC BANK LIMITED", title_style),
        Paragraph("Branch: Electronic City, Bengaluru — IFSC: HDFC0001234", center),
        Paragraph("CIN: L65920MH1994PLC080618  |  Regd. Office: HDFC Bank House, Mumbai 400013", small),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003087")),
        Spacer(1, 5*mm),
        Paragraph("<b>TO WHOMSOEVER IT MAY CONCERN</b>", center),
        Paragraph("<b>BANK ACCOUNT CONFIRMATION LETTER</b>",
                  ParagraphStyle("bh", parent=styles["Normal"], alignment=TA_CENTER, fontSize=12, fontName="Helvetica-Bold")),
        Spacer(1, 5*mm),
        Paragraph("This certifies that the following account is maintained with HDFC Bank Limited, Electronic City Branch, Bengaluru:", normal),
        Spacer(1, 3*mm),
        kv_table([
            ("Account Holder Name",   "PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED"),
            ("Account Number",        "50200012345678"),
            ("Account Type",          "Current Account"),
            ("Bank Name",             "HDFC Bank Limited"),
            ("Branch",                "Electronic City, Bengaluru"),
            ("IFSC Code",             "HDFC0001234"),
            ("MICR Code",             "560240005"),
            ("Date of Opening",       "20/03/2018"),
            ("Account Status",        "Active"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued at the request of the account holder for vendor registration purposes.", normal),
        Spacer(1, 10*mm),
        Paragraph("Authorised Signatory", normal),
        Paragraph("<b>Branch Manager — HDFC Bank, Electronic City Branch</b>", normal),
        Paragraph("Date: 01/05/2026", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("HDFC Bank is regulated by the Reserve Bank of India. This letter is system-generated.", small),
    ])
    print("  TC1  tc1_prism_bank_letter.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# TC2 — BRIGHTWAVE LOGISTICS PRIVATE LIMITED
# Expected: PENDING  (reason: PAN_ENTITY_INDIVIDUAL)
# PAN AABPB5678Q: 4th char P = Individual. sum=302, 302%26=16 → Q ✓
# GSTIN 27AABPB5678Q1ZJ: state=27=Maharashtra ✓, embedded PAN=AABPB5678Q ✓
# Failure: pan_entity_type = fail (14 pts → severity < 25 → PENDING)
# ─────────────────────────────────────────────────────────────────────────────

def gen_tc2_coi():
    d = doc("tc2_brightwave_coi.pdf")
    d.build([
        Paragraph("MINISTRY OF CORPORATE AFFAIRS — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("(Under the Companies Act, 2013)", center),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 5*mm),
        Paragraph(
            "This is to certify that <b>BRIGHTWAVE LOGISTICS PRIVATE LIMITED</b> is duly "
            "incorporated under the Companies Act, 2013 and is limited by shares.",
            normal,
        ),
        Spacer(1, 5*mm),
        kv_table([
            ("Company Name",         "BRIGHTWAVE LOGISTICS PRIVATE LIMITED"),
            ("CIN",                  "U63000MH2021PTC346789"),
            ("Date of Incorporation","10/09/2021"),
            ("State of Incorporation","Maharashtra"),
            ("Registered Office",    "301, Logistics Park, Pune, Maharashtra - 411014"),
            ("Type of Company",      "Private Company Limited by Shares"),
            ("NIC Activity",         "63000 — Support Activities for Transportation"),
            ("Authorised Capital",   "INR 20,00,000"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("Given under my hand at Pune this Tenth day of September, Two Thousand and Twenty-One.", normal),
        Spacer(1, 10*mm),
        Paragraph("Sd/-", normal),
        Paragraph("<b>Registrar of Companies, Pune</b>", normal),
        Paragraph("Ministry of Corporate Affairs", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Digitally issued. Verify at mca.gov.in  |  CIN: U63000MH2021PTC346789", small),
    ])
    print("  TC2  tc2_brightwave_coi.pdf")


def gen_tc2_pan_gstin():
    d = doc("tc2_brightwave_pan_gstin.pdf")
    d.build([
        Paragraph("INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Permanent Account Number (PAN) Card", title_style),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003580")),
        Spacer(1, 4*mm),
        Paragraph(
            "<b>⚠ NOTE FOR REVIEWERS:</b> The 4th character of this PAN is 'P' (Individual). "
            "Business vendors must hold a Company PAN (4th char = C/F/H). "
            "This triggers PAN_ENTITY_INDIVIDUAL validation failure.",
            warn_style,
        ),
        Spacer(1, 4*mm),
        kv_table([
            ("Name of Assessee",              "BRIGHTWAVE LOGISTICS PRIVATE LIMITED"),
            ("PAN",                           "AABPB5678Q"),
            ("Date of Incorporation",         "10/09/2021"),
            ("Status",                        "INDIVIDUAL"),
            ("Father's / Founder's Name",     "KAVITA MENON"),
        ]),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 5*mm),
        Paragraph("GST NETWORK (GSTN) — GOVERNMENT OF INDIA", gov_style),
        Paragraph("GST Registration Certificate", h2),
        Spacer(1, 3*mm),
        kv_table([
            ("Legal Name of Business",        "BRIGHTWAVE LOGISTICS PRIVATE LIMITED"),
            ("GSTIN",                         "27AABPB5678Q1ZJ"),
            ("PAN",                           "AABPB5678Q"),
            ("State",                         "Maharashtra"),
            ("GST State Code",                "27"),
            ("Registration Type",             "Regular"),
            ("Date of Registration",          "01/12/2021"),
            ("Place of Business",             "301, Logistics Park, Pune - 411014"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued by GST Council. Verify at gst.gov.in  |  GSTIN: 27AABPB5678Q1ZJ", small),
    ])
    print("  TC2  tc2_brightwave_pan_gstin.pdf")


def gen_tc2_bank():
    d = doc("tc2_brightwave_bank_letter.pdf")
    d.build([
        Paragraph("ICICI BANK LIMITED", title_style),
        Paragraph("Branch: Hadapsar, Pune — IFSC: ICIC0004567", center),
        Paragraph("CIN: L65190GJ1994PLC021012  |  Regd. Office: ICICI Bank Tower, Mumbai 400051", small),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#f26522")),
        Spacer(1, 5*mm),
        Paragraph("<b>TO WHOMSOEVER IT MAY CONCERN</b>", center),
        Paragraph("<b>BANK ACCOUNT CONFIRMATION LETTER</b>",
                  ParagraphStyle("bh", parent=styles["Normal"], alignment=TA_CENTER, fontSize=12, fontName="Helvetica-Bold")),
        Spacer(1, 5*mm),
        Paragraph("This certifies that the following account is maintained with ICICI Bank Limited, Hadapsar Branch, Pune:", normal),
        Spacer(1, 3*mm),
        kv_table([
            ("Account Holder Name",   "BRIGHTWAVE LOGISTICS PRIVATE LIMITED"),
            ("Account Number",        "001201234567890"),
            ("Account Type",          "Current Account"),
            ("Bank Name",             "ICICI Bank Limited"),
            ("Branch",                "Hadapsar, Pune"),
            ("IFSC Code",             "ICIC0004567"),
            ("MICR Code",             "411230012"),
            ("Date of Opening",       "15/10/2021"),
            ("Account Status",        "Active"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued at the request of the account holder for vendor registration purposes.", normal),
        Spacer(1, 10*mm),
        Paragraph("Authorised Signatory", normal),
        Paragraph("<b>Relationship Manager — ICICI Bank, Hadapsar</b>", normal),
        Paragraph("Date: 01/05/2026", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("ICICI Bank is regulated by the Reserve Bank of India.", small),
    ])
    print("  TC2  tc2_brightwave_bank_letter.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# TC3 — KIRAN HEALTH SYSTEMS PRIVATE LIMITED
# Expected: PENDING  (reason: GSTIN_STATE_MISMATCH)
# PAN AABCK5678C: 4th char C = Company ✓. sum=288, 288%26=2 → C ✓
# GSTIN 09AABCK5678C1ZJ: state=09=Uttar Pradesh, but registered_state=Delhi (07) → MISMATCH
# Failure: gstin_state_vs_registered_state = fail (14 pts → severity < 25 → PENDING)
# ─────────────────────────────────────────────────────────────────────────────

def gen_tc3_coi():
    d = doc("tc3_kiran_coi.pdf")
    d.build([
        Paragraph("MINISTRY OF CORPORATE AFFAIRS — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("(Under the Companies Act, 2013)", center),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 5*mm),
        Paragraph(
            "This is to certify that <b>KIRAN HEALTH SYSTEMS PRIVATE LIMITED</b> is duly "
            "incorporated under the Companies Act, 2013 and is limited by shares.",
            normal,
        ),
        Spacer(1, 5*mm),
        kv_table([
            ("Company Name",         "KIRAN HEALTH SYSTEMS PRIVATE LIMITED"),
            ("CIN",                  "U85100DL2019PTC352001"),
            ("Date of Incorporation","22/06/2019"),
            ("State of Incorporation","Delhi"),
            ("Registered Office",    "14, Nehru Place, South Delhi, New Delhi - 110019"),
            ("Type of Company",      "Private Company Limited by Shares"),
            ("NIC Activity",         "85100 — Human Health Activities"),
            ("Authorised Capital",   "INR 1,00,00,000"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("Given under my hand at New Delhi this Twenty-Second day of June, Two Thousand and Nineteen.", normal),
        Spacer(1, 10*mm),
        Paragraph("Sd/-", normal),
        Paragraph("<b>Registrar of Companies, Delhi</b>", normal),
        Paragraph("Ministry of Corporate Affairs", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Digitally issued. Verify at mca.gov.in  |  CIN: U85100DL2019PTC352001", small),
    ])
    print("  TC3  tc3_kiran_coi.pdf")


def gen_tc3_pan_gstin():
    d = doc("tc3_kiran_pan_gstin.pdf")
    d.build([
        Paragraph("INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Permanent Account Number (PAN) Card", title_style),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003580")),
        Spacer(1, 4*mm),
        kv_table([
            ("Name of Assessee",              "KIRAN HEALTH SYSTEMS PRIVATE LIMITED"),
            ("PAN",                           "AABCK5678C"),
            ("Date of Incorporation",         "22/06/2019"),
            ("Status",                        "COMPANY"),
            ("Father's / Founder's Name",     "DR. RAJIV KIRAN"),
        ]),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 5*mm),
        Paragraph("GST NETWORK (GSTN) — GOVERNMENT OF INDIA", gov_style),
        Paragraph("GST Registration Certificate", h2),
        Spacer(1, 3*mm),
        Paragraph(
            "<b>⚠ NOTE FOR REVIEWERS:</b> GSTIN state code 09 = Uttar Pradesh, "
            "but the company is registered in Delhi (state code 07). "
            "This triggers GSTIN_STATE_MISMATCH validation failure.",
            warn_style,
        ),
        Spacer(1, 4*mm),
        kv_table([
            ("Legal Name of Business",        "KIRAN HEALTH SYSTEMS PRIVATE LIMITED"),
            ("GSTIN",                         "09AABCK5678C1ZJ"),
            ("PAN",                           "AABCK5678C"),
            ("State",                         "Uttar Pradesh"),
            ("GST State Code",                "09"),
            ("Registration Type",             "Regular"),
            ("Date of Registration",          "01/09/2019"),
            ("Place of Business",             "14, Nehru Place, New Delhi - 110019"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued by GST Council. Verify at gst.gov.in  |  GSTIN: 09AABCK5678C1ZJ", small),
    ])
    print("  TC3  tc3_kiran_pan_gstin.pdf")


def gen_tc3_bank():
    d = doc("tc3_kiran_bank_letter.pdf")
    d.build([
        Paragraph("STATE BANK OF INDIA", title_style),
        Paragraph("Branch: Nehru Place, New Delhi — IFSC: SBIN0011567", center),
        Paragraph("Corporate CIN: L40040MH1955GOI009108  |  Central Office: Madame Cama Road, Mumbai 400021", small),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#22a0e0")),
        Spacer(1, 5*mm),
        Paragraph("<b>TO WHOMSOEVER IT MAY CONCERN</b>", center),
        Paragraph("<b>BANK ACCOUNT CONFIRMATION LETTER</b>",
                  ParagraphStyle("bh", parent=styles["Normal"], alignment=TA_CENTER, fontSize=12, fontName="Helvetica-Bold")),
        Spacer(1, 5*mm),
        Paragraph("This certifies that the following account is maintained with State Bank of India, Nehru Place Branch, New Delhi:", normal),
        Spacer(1, 3*mm),
        kv_table([
            ("Account Holder Name",   "KIRAN HEALTH SYSTEMS PRIVATE LIMITED"),
            ("Account Number",        "30012345678901"),
            ("Account Type",          "Current Account"),
            ("Bank Name",             "State Bank of India"),
            ("Branch",                "Nehru Place, New Delhi"),
            ("IFSC Code",             "SBIN0011567"),
            ("MICR Code",             "110002009"),
            ("Date of Opening",       "05/08/2019"),
            ("Account Status",        "Active"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued at the request of the account holder for vendor registration purposes.", normal),
        Spacer(1, 10*mm),
        Paragraph("Authorised Signatory", normal),
        Paragraph("<b>Branch Manager — State Bank of India, Nehru Place</b>", normal),
        Paragraph("Date: 01/05/2026", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("State Bank of India is regulated by the Reserve Bank of India.", small),
    ])
    print("  TC3  tc3_kiran_bank_letter.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# TC4 — FALCON DYNAMICS PRIVATE LIMITED
# Expected: REJECTED (severity >> 25)
# PAN AABCF3691B: sum=183, 183%26=1 → B ✓
# GSTIN 07AABCX9999Q1ZK: embedded PAN=AABCX9999Q ≠ AABCF3691B → GSTIN_PAN_MISMATCH (14 pts)
# Bank account holder = "VIKAS ENTERPRISES" ≠ "FALCON DYNAMICS PRIVATE LIMITED"
#   → company_name_vs_bank_doc fail (14 pts)
#   → coi_vs_bank_name fail (14 pts)
#   → pan_vs_bank_name fail (14 pts)
#   → gstin_embedded_pan_vs_pan_doc fail (14 pts)  [PAN doc: AABCF3691B ≠ GSTIN-embedded AABCX9999Q]
# Total severity: 70 pts → REJECTED
# ─────────────────────────────────────────────────────────────────────────────

def gen_tc4_coi():
    d = doc("tc4_falcon_coi.pdf")
    d.build([
        Paragraph("MINISTRY OF CORPORATE AFFAIRS — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("(Under the Companies Act, 2013)", center),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 5*mm),
        Paragraph(
            "This is to certify that <b>FALCON DYNAMICS PRIVATE LIMITED</b> is duly "
            "incorporated under the Companies Act, 2013 and is limited by shares.",
            normal,
        ),
        Spacer(1, 5*mm),
        kv_table([
            ("Company Name",         "FALCON DYNAMICS PRIVATE LIMITED"),
            ("CIN",                  "U62090DL2020PTC298765"),
            ("Date of Incorporation","10/01/2020"),
            ("State of Incorporation","Delhi"),
            ("Registered Office",    "88, Okhla Industrial Estate Phase III, New Delhi - 110020"),
            ("Type of Company",      "Private Company Limited by Shares"),
            ("NIC Activity",         "62090 — Other Information Technology Activities"),
            ("Authorised Capital",   "INR 25,00,000"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("Given under my hand at New Delhi this Tenth day of January, Two Thousand and Twenty.", normal),
        Spacer(1, 10*mm),
        Paragraph("Sd/-", normal),
        Paragraph("<b>Registrar of Companies, Delhi</b>", normal),
        Paragraph("Ministry of Corporate Affairs", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Digitally issued. Verify at mca.gov.in  |  CIN: U62090DL2020PTC298765", small),
    ])
    print("  TC4  tc4_falcon_coi.pdf")


def gen_tc4_pan_gstin():
    d = doc("tc4_falcon_pan_gstin.pdf")
    d.build([
        Paragraph("INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Permanent Account Number (PAN) Card", title_style),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003580")),
        Spacer(1, 4*mm),
        kv_table([
            ("Name of Assessee",              "FALCON DYNAMICS PRIVATE LIMITED"),
            ("PAN",                           "AABCF3691B"),
            ("Date of Incorporation",         "10/01/2020"),
            ("Status",                        "COMPANY"),
            ("Father's / Founder's Name",     "SURESH KAPOOR"),
        ]),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 5*mm),
        Paragraph("GST NETWORK (GSTN) — GOVERNMENT OF INDIA", gov_style),
        Paragraph("GST Registration Certificate", h2),
        Spacer(1, 3*mm),
        Paragraph(
            "<b>⚠ FRAUD INDICATOR:</b> The GSTIN below belongs to a DIFFERENT entity "
            "(VIKAS ENTERPRISES, PAN AABCX9999Q). The PAN above (AABCF3691B) and the "
            "embedded PAN in the GSTIN (AABCX9999Q) do not match — triggering "
            "GSTIN_PAN_MISMATCH and gstin_embedded_pan_vs_pan_doc failures.",
            warn_style,
        ),
        Spacer(1, 4*mm),
        kv_table([
            ("Legal Name of Business",        "VIKAS ENTERPRISES"),
            ("GSTIN",                         "07AABCX9999Q1ZK"),
            ("PAN",                           "AABCX9999Q"),
            ("State",                         "Delhi"),
            ("GST State Code",                "07"),
            ("Registration Type",             "Regular"),
            ("Date of Registration",          "01/04/2020"),
            ("Place of Business",             "45, Kashmere Gate, Delhi - 110006"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued by GST Council. Verify at gst.gov.in  |  GSTIN: 07AABCX9999Q1ZK", small),
    ])
    print("  TC4  tc4_falcon_pan_gstin.pdf")


def gen_tc4_bank():
    d = doc("tc4_falcon_bank_letter.pdf")
    d.build([
        Paragraph("AXIS BANK LIMITED", title_style),
        Paragraph("Branch: Okhla Industrial Estate, New Delhi — IFSC: UTIB0001234", center),
        Paragraph("CIN: L65110GJ1993PLC020769  |  Regd. Office: Axis House, Mumbai 400025", small),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#97144d")),
        Spacer(1, 5*mm),
        Paragraph("<b>TO WHOMSOEVER IT MAY CONCERN</b>", center),
        Paragraph("<b>BANK ACCOUNT CONFIRMATION LETTER</b>",
                  ParagraphStyle("bh", parent=styles["Normal"], alignment=TA_CENTER, fontSize=12, fontName="Helvetica-Bold")),
        Spacer(1, 5*mm),
        Paragraph(
            "<b>⚠ FRAUD INDICATOR:</b> Account holder name is VIKAS ENTERPRISES, "
            "not FALCON DYNAMICS PRIVATE LIMITED as claimed. This triggers "
            "company_name_vs_bank_doc, coi_vs_bank_name, and pan_vs_bank_name failures.",
            warn_style,
        ),
        Spacer(1, 4*mm),
        Paragraph("This certifies that the following account is maintained with Axis Bank Limited, Okhla Industrial Branch, New Delhi:", normal),
        Spacer(1, 3*mm),
        kv_table([
            ("Account Holder Name",   "VIKAS ENTERPRISES"),
            ("Account Number",        "917010012345678"),
            ("Account Type",          "Current Account"),
            ("Bank Name",             "Axis Bank Limited"),
            ("Branch",                "Okhla Industrial Estate, New Delhi"),
            ("IFSC Code",             "UTIB0001234"),
            ("MICR Code",             "110211006"),
            ("Date of Opening",       "15/02/2020"),
            ("Account Status",        "Active"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued at the request of the account holder for vendor registration purposes.", normal),
        Spacer(1, 10*mm),
        Paragraph("Authorised Signatory", normal),
        Paragraph("<b>Relationship Manager — Axis Bank, Okhla Branch</b>", normal),
        Paragraph("Date: 01/05/2026", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Axis Bank is regulated by the Reserve Bank of India.", small),
    ])
    print("  TC4  tc4_falcon_bank_letter.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# TC5 — SHREE KRISHNA EXPORTS PRIVATE LIMITED
# Expected: REJECTED (severity >= 25 + credibility high flag)
# PAN AABCS4523U: sum=280, 280%26=20 → U ✓
# GSTIN 07AABCX5555P1ZM: state=07=Delhi ≠ Tamil Nadu (GSTIN_STATE_MISMATCH, 14 pts)
#                         embedded PAN=AABCX5555P ≠ AABCS4523U (GSTIN_PAN_MISMATCH, 14 pts)
# Bank: DBS Bank Singapore (bank_country=SG for IN company → credibility high flag)
# Total deterministic severity: 28 pts → REJECTED; plus likely high credibility flag
# ─────────────────────────────────────────────────────────────────────────────

def gen_tc5_coi():
    d = doc("tc5_krishna_coi.pdf")
    d.build([
        Paragraph("MINISTRY OF CORPORATE AFFAIRS — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Certificate of Incorporation", title_style),
        Paragraph("(Under the Companies Act, 2013)", center),
        Spacer(1, 6*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a3c6e")),
        Spacer(1, 5*mm),
        Paragraph(
            "This is to certify that <b>SHREE KRISHNA EXPORTS PRIVATE LIMITED</b> is duly "
            "incorporated under the Companies Act, 2013 and is limited by shares.",
            normal,
        ),
        Spacer(1, 5*mm),
        kv_table([
            ("Company Name",         "SHREE KRISHNA EXPORTS PRIVATE LIMITED"),
            ("CIN",                  "U51909TN2022PTC401234"),
            ("Date of Incorporation","15/02/2022"),
            ("State of Incorporation","Tamil Nadu"),
            ("Registered Office",    "22, Anna Salai, Chennai, Tamil Nadu - 600002"),
            ("Type of Company",      "Private Company Limited by Shares"),
            ("NIC Activity",         "51909 — Other Wholesale Trade Not Elsewhere Classified"),
            ("Authorised Capital",   "INR 75,00,000"),
        ]),
        Spacer(1, 8*mm),
        Paragraph("Given under my hand at Chennai this Fifteenth day of February, Two Thousand and Twenty-Two.", normal),
        Spacer(1, 10*mm),
        Paragraph("Sd/-", normal),
        Paragraph("<b>Registrar of Companies, Chennai</b>", normal),
        Paragraph("Ministry of Corporate Affairs", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("Digitally issued. Verify at mca.gov.in  |  CIN: U51909TN2022PTC401234", small),
    ])
    print("  TC5  tc5_krishna_coi.pdf")


def gen_tc5_pan_gstin():
    d = doc("tc5_krishna_pan_gstin.pdf")
    d.build([
        Paragraph("INCOME TAX DEPARTMENT — GOVERNMENT OF INDIA", gov_style),
        Paragraph("Permanent Account Number (PAN) Card", title_style),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#003580")),
        Spacer(1, 4*mm),
        kv_table([
            ("Name of Assessee",              "SHREE KRISHNA EXPORTS PRIVATE LIMITED"),
            ("PAN",                           "AABCS4523U"),
            ("Date of Incorporation",         "15/02/2022"),
            ("Status",                        "COMPANY"),
            ("Father's / Founder's Name",     "KRISHNASWAMY IYER"),
        ]),
        Spacer(1, 8*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Spacer(1, 5*mm),
        Paragraph("GST NETWORK (GSTN) — GOVERNMENT OF INDIA", gov_style),
        Paragraph("GST Registration Certificate", h2),
        Spacer(1, 3*mm),
        Paragraph(
            "<b>⚠ TWO FRAUD INDICATORS:</b> (1) GSTIN state code 07 = Delhi, but company is "
            "registered in Tamil Nadu (state 33) → GSTIN_STATE_MISMATCH. "
            "(2) Embedded PAN in GSTIN (AABCX5555P) ≠ submitted PAN (AABCS4523U) → "
            "GSTIN_PAN_MISMATCH. Combined severity: 28 pts → REJECTED.",
            warn_style,
        ),
        Spacer(1, 4*mm),
        kv_table([
            ("Legal Name of Business",        "SHREE KRISHNA EXPORTS PRIVATE LIMITED"),
            ("GSTIN",                         "07AABCX5555P1ZM"),
            ("PAN",                           "AABCX5555P"),
            ("State",                         "Delhi"),
            ("GST State Code",                "07"),
            ("Registration Type",             "Regular"),
            ("Date of Registration",          "01/05/2022"),
            ("Place of Business",             "22, Anna Salai, Chennai - 600002"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("Issued by GST Council. Verify at gst.gov.in  |  GSTIN: 07AABCX5555P1ZM", small),
    ])
    print("  TC5  tc5_krishna_pan_gstin.pdf")


def gen_tc5_bank():
    d = doc("tc5_krishna_bank_letter.pdf")
    d.build([
        Paragraph("DBS BANK LTD — SINGAPORE BRANCH", title_style),
        Paragraph("12 Marina Boulevard, DBS Asia Central, Singapore 018982", center),
        Paragraph("UEN: 196800306E  |  SWIFT/BIC: DBSSSGSG", small),
        Spacer(1, 3*mm),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#da1b2e")),
        Spacer(1, 5*mm),
        Paragraph("<b>TO WHOMSOEVER IT MAY CONCERN</b>", center),
        Paragraph("<b>BANK ACCOUNT CONFIRMATION LETTER</b>",
                  ParagraphStyle("bh", parent=styles["Normal"], alignment=TA_CENTER, fontSize=12, fontName="Helvetica-Bold")),
        Spacer(1, 5*mm),
        Paragraph(
            "<b>⚠ FRAUD INDICATOR:</b> This is a Singapore bank account for a company "
            "registered in India (Tamil Nadu). Indian vendor payments must use an Indian "
            "bank account. Triggers FOREIGN_BANK_ACCOUNT credibility high-severity flag.",
            warn_style,
        ),
        Spacer(1, 4*mm),
        Paragraph("This certifies that the following account is maintained with DBS Bank Ltd, Singapore:", normal),
        Spacer(1, 3*mm),
        kv_table([
            ("Account Holder Name",   "SHREE KRISHNA EXPORTS PRIVATE LIMITED"),
            ("Account Number",        "0720123456789"),
            ("Account Type",          "Current Account"),
            ("Bank Name",             "DBS Bank Ltd"),
            ("Branch",                "Marina Boulevard, Singapore"),
            ("SWIFT Code",            "DBSSSGSG"),
            ("IBAN / IFSC",           "Not Applicable — Singapore Bank"),
            ("Currency",              "SGD"),
            ("Country",               "Singapore"),
            ("Date of Opening",       "01/04/2022"),
            ("Account Status",        "Active"),
        ]),
        Spacer(1, 6*mm),
        Paragraph("This letter is issued at the request of the account holder.", normal),
        Spacer(1, 10*mm),
        Paragraph("Authorised Signatory", normal),
        Paragraph("<b>Relationship Manager — DBS Bank, Singapore</b>", normal),
        Paragraph("Date: 01/05/2026", small),
        Spacer(1, 4*mm),
        HRFlowable(width="100%", thickness=0.5, color=colors.grey),
        Paragraph("DBS Bank Ltd is licensed by the Monetary Authority of Singapore. This letter is valid for 90 days.", small),
    ])
    print("  TC5  tc5_krishna_bank_letter.pdf")


# ─────────────────────────────────────────────────────────────────────────────
# Form data JSON — copy-paste ready submission payloads for each test case
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES = {
    "tc1_prism_approved": {
        "_scenario": "APPROVED — clean submission, all checks pass",
        "_expected_status": "approved",
        "_expected_reason_codes": [],
        "_failing_checks": [],
        "company_name": "PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED",
        "country": "IN",
        "incorporation_date": "2018-03-15",
        "contact_name": "Arjun Sharma",
        "contact_email": "arjun.sharma@prismsoftware.in",
        "cin_number": "U72200KA2018PTC098765",
        "pan_number": "AABCP1234I",
        "gstin_number": "29AABCP1234I1ZK",
        "ifsc_code": "HDFC0001234",
        "account_type": "Current Account",
        "registered_state": "Karnataka",
        "bank_account_name": "PRISM SOFTWARE SOLUTIONS PRIVATE LIMITED",
        "account_number": "50200012345678",
        "bank_name": "HDFC Bank",
        "bank_country": "IN",
        "_docs": {
            "coi": "tc1_prism_coi.pdf",
            "pan_gstin": "tc1_prism_pan_gstin.pdf",
            "bank_letter": "tc1_prism_bank_letter.pdf",
        },
    },

    "tc2_brightwave_pending_individual_pan": {
        "_scenario": "PENDING — Individual PAN (4th char P) submitted for a company",
        "_expected_status": "pending",
        "_expected_reason_codes": ["PAN_ENTITY_INDIVIDUAL"],
        "_failing_checks": ["pan_entity_type"],
        "_severity_score": 14,
        "company_name": "BRIGHTWAVE LOGISTICS PRIVATE LIMITED",
        "country": "IN",
        "incorporation_date": "2021-09-10",
        "contact_name": "Kavita Menon",
        "contact_email": "kavita@brightwavelogistics.in",
        "cin_number": "U63000MH2021PTC346789",
        "pan_number": "AABPB5678Q",
        "gstin_number": "27AABPB5678Q1ZJ",
        "ifsc_code": "ICIC0004567",
        "account_type": "Current Account",
        "registered_state": "Maharashtra",
        "bank_account_name": "BRIGHTWAVE LOGISTICS PRIVATE LIMITED",
        "account_number": "001201234567890",
        "bank_name": "ICICI Bank",
        "bank_country": "IN",
        "_docs": {
            "coi": "tc2_brightwave_coi.pdf",
            "pan_gstin": "tc2_brightwave_pan_gstin.pdf",
            "bank_letter": "tc2_brightwave_bank_letter.pdf",
        },
    },

    "tc3_kiran_pending_gstin_state_mismatch": {
        "_scenario": "PENDING — GSTIN state code 09 (UP) ≠ registered state Delhi (07)",
        "_expected_status": "pending",
        "_expected_reason_codes": ["GSTIN_STATE_MISMATCH"],
        "_failing_checks": ["gstin_state_vs_registered_state"],
        "_severity_score": 14,
        "company_name": "KIRAN HEALTH SYSTEMS PRIVATE LIMITED",
        "country": "IN",
        "incorporation_date": "2019-06-22",
        "contact_name": "Dr. Rajiv Kiran",
        "contact_email": "rajiv@kiranhealthsystems.in",
        "cin_number": "U85100DL2019PTC352001",
        "pan_number": "AABCK5678C",
        "gstin_number": "09AABCK5678C1ZJ",
        "ifsc_code": "SBIN0011567",
        "account_type": "Current Account",
        "registered_state": "Delhi",
        "bank_account_name": "KIRAN HEALTH SYSTEMS PRIVATE LIMITED",
        "account_number": "30012345678901",
        "bank_name": "State Bank of India",
        "bank_country": "IN",
        "_docs": {
            "coi": "tc3_kiran_coi.pdf",
            "pan_gstin": "tc3_kiran_pan_gstin.pdf",
            "bank_letter": "tc3_kiran_bank_letter.pdf",
        },
    },

    "tc4_falcon_rejected_multiple_fraud": {
        "_scenario": "REJECTED — GSTIN PAN mismatch + bank account belongs to different entity (VIKAS ENTERPRISES)",
        "_expected_status": "rejected",
        "_expected_reason_codes": ["GSTIN_PAN_MISMATCH", "COMPANY_NAME_BANK_MISMATCH", "COI_VS_BANK_NAME_MISMATCH", "PAN_VS_BANK_NAME_MISMATCH"],
        "_failing_checks": [
            "gstin_pan_match",
            "company_name_vs_bank_doc",
            "coi_vs_bank_name",
            "pan_vs_bank_name",
            "gstin_embedded_pan_vs_pan_doc",
        ],
        "_severity_score": 70,
        "company_name": "FALCON DYNAMICS PRIVATE LIMITED",
        "country": "IN",
        "incorporation_date": "2020-01-10",
        "contact_name": "Suresh Kapoor",
        "contact_email": "suresh@falcondynamics.in",
        "cin_number": "U62090DL2020PTC298765",
        "pan_number": "AABCF3691B",
        "gstin_number": "07AABCX9999Q1ZK",
        "ifsc_code": "UTIB0001234",
        "account_type": "Current Account",
        "registered_state": "Delhi",
        "bank_account_name": "VIKAS ENTERPRISES",
        "account_number": "917010012345678",
        "bank_name": "Axis Bank",
        "bank_country": "IN",
        "_docs": {
            "coi": "tc4_falcon_coi.pdf",
            "pan_gstin": "tc4_falcon_pan_gstin.pdf",
            "bank_letter": "tc4_falcon_bank_letter.pdf",
        },
    },

    "tc5_krishna_rejected_foreign_bank": {
        "_scenario": "REJECTED — GSTIN state+PAN double mismatch + foreign Singapore bank account for Indian company",
        "_expected_status": "rejected",
        "_expected_reason_codes": ["GSTIN_PAN_MISMATCH", "GSTIN_STATE_MISMATCH", "FOREIGN_BANK_ACCOUNT"],
        "_failing_checks": [
            "gstin_pan_match",
            "gstin_state_vs_registered_state",
            "gstin_embedded_pan_vs_pan_doc",
        ],
        "_severity_score": 42,
        "company_name": "SHREE KRISHNA EXPORTS PRIVATE LIMITED",
        "country": "IN",
        "incorporation_date": "2022-02-15",
        "contact_name": "Krishnaswamy Iyer",
        "contact_email": "krishnaswamy.iyer@shreekrishna.com",
        "cin_number": "U51909TN2022PTC401234",
        "pan_number": "AABCS4523U",
        "gstin_number": "07AABCX5555P1ZM",
        "ifsc_code": "",
        "account_type": "Current Account",
        "registered_state": "Tamil Nadu",
        "bank_account_name": "SHREE KRISHNA EXPORTS PRIVATE LIMITED",
        "account_number": "0720123456789",
        "bank_name": "DBS Bank Singapore",
        "bank_country": "SG",
        "_docs": {
            "coi": "tc5_krishna_coi.pdf",
            "pan_gstin": "tc5_krishna_pan_gstin.pdf",
            "bank_letter": "tc5_krishna_bank_letter.pdf",
        },
    },
}


def write_test_data_json():
    path = os.path.join(OUT, "india_test_cases.json")
    with open(path, "w") as f:
        json.dump(TEST_CASES, f, indent=2)
    print(f"\n  JSON  india_test_cases.json  ({len(TEST_CASES)} test cases)")


if __name__ == "__main__":
    print("\n=== Generating India Test Case PDFs ===\n")

    print("TC1 — PRISM SOFTWARE SOLUTIONS (APPROVED)")
    gen_tc1_coi()
    gen_tc1_pan_gstin()
    gen_tc1_bank()

    print("\nTC2 — BRIGHTWAVE LOGISTICS (PENDING: individual PAN)")
    gen_tc2_coi()
    gen_tc2_pan_gstin()
    gen_tc2_bank()

    print("\nTC3 — KIRAN HEALTH SYSTEMS (PENDING: GSTIN state mismatch)")
    gen_tc3_coi()
    gen_tc3_pan_gstin()
    gen_tc3_bank()

    print("\nTC4 — FALCON DYNAMICS (REJECTED: GSTIN/PAN mismatch + wrong bank entity)")
    gen_tc4_coi()
    gen_tc4_pan_gstin()
    gen_tc4_bank()

    print("\nTC5 — SHREE KRISHNA EXPORTS (REJECTED: double GSTIN failure + foreign bank)")
    gen_tc5_coi()
    gen_tc5_pan_gstin()
    gen_tc5_bank()

    print("\n=== Form Data ===")
    write_test_data_json()

    print(f"\nAll 15 PDFs + JSON written to: {OUT}")
    print("\nExpected outcomes:")
    print("  TC1  PRISM SOFTWARE SOLUTIONS    → APPROVED")
    print("  TC2  BRIGHTWAVE LOGISTICS         → PENDING  (PAN_ENTITY_INDIVIDUAL,     severity=14)")
    print("  TC3  KIRAN HEALTH SYSTEMS         → PENDING  (GSTIN_STATE_MISMATCH,      severity=14)")
    print("  TC4  FALCON DYNAMICS              → REJECTED (score=70: GSTIN/PAN mismatch + wrong bank entity)")
    print("  TC5  SHREE KRISHNA EXPORTS        → REJECTED (score=42: 2×GSTIN failures + Singapore bank)")
