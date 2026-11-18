from io import BytesIO
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import MAX_SYNC_EXPORT_ROWS, _rows, _safe_cell


def build_xlsx(module, queryset):
    headers, rows = _rows(module, queryset)
    workbook = Workbook(write_only=False)
    sheet = workbook.active
    sheet.title = module.replace("_", " ").title()[:31]
    sheet.freeze_panes = "A2"
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17324D")
    count = 0
    for row in rows:
        count += 1
        if count > MAX_SYNC_EXPORT_ROWS:
            raise ValueError("Export exceeds the 20,000-row instant export limit.")
        sheet.append([_safe_cell(value) for value in row])
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = min(max(max(len(str(cell.value or "")) for cell in column[:200]) + 2, 12), 36)
        sheet.column_dimensions[get_column_letter(column[0].column)].width = width
    output = BytesIO()
    workbook.save(output)
    return output.getvalue(), count


def build_pdf(module, queryset, organization_name):
    headers, rows = _rows(module, queryset)
    output = BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=13 * mm,
        bottomMargin=13 * mm,
        title=f"{organization_name} - {module.replace('_', ' ').title()}",
        author=organization_name,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor("#17324D")
    blue = colors.HexColor("#245B83")
    teal = colors.HexColor("#0F766E")
    muted = colors.HexColor("#64748B")

    title_style = ParagraphStyle(
        "ExportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=navy,
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ExportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=muted,
        alignment=TA_CENTER,
    )
    header_style = ParagraphStyle(
        "ExportTableHeader",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8,
        textColor=colors.white,
        alignment=0,
        wordWrap="CJK",
    )
    cell_style = ParagraphStyle(
        "ExportTableCell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#172B3A"),
        wordWrap="CJK",
    )

    title = f"{escape(str(organization_name))} — {escape(module.replace('_', ' ').title())}"
    story = [
        Paragraph(title, title_style),
        Paragraph("CONFIDENTIAL ORGANISATION DATA EXPORT", subtitle_style),
        Spacer(1, 6 * mm),
    ]

    table_data = [[Paragraph(escape(str(value)), header_style) for value in headers]]
    count = 0
    for row in rows:
        count += 1
        if count > 2500:
            raise ValueError("PDF exports are limited to 2,500 rows. Use Excel for larger exports.")
        table_data.append([
            Paragraph(escape(str(_safe_cell(value))), cell_style)
            for value in row
        ])

    widths = [doc.width / len(headers)] * len(headers)
    table = Table(
        table_data,
        colWidths=widths,
        repeatRows=1,
        hAlign="LEFT",
        splitByRow=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("LINEBELOW", (0, 0), (-1, 0), 1.2, teal),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F7FB")]),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    doc.build(story)
    return output.getvalue(), count


def build_export_file(module, queryset, file_format, organization_name):
    if file_format == "xlsx":
        return build_xlsx(module, queryset)
    if file_format == "pdf":
        return build_pdf(module, queryset, organization_name)
    if file_format == "csv":
        from .services import build_csv
        content, count = build_csv(module, queryset)
        return content.encode("utf-8"), count
    raise ValueError("Unsupported export format.")
