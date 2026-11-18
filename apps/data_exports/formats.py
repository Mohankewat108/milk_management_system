from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .services import MAX_SYNC_EXPORT_ROWS, _rows, _safe_cell


def build_xlsx(module, queryset):
    headers, rows = _rows(module, queryset)
    workbook = Workbook(write_only=False)
    sheet = workbook.active
    sheet.title = module.replace("_", " ").title()[:31]
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = "A1"
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
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=10*mm, leftMargin=10*mm, topMargin=12*mm, bottomMargin=12*mm)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"{organization_name} — {module.replace('_', ' ').title()}", styles["Title"]),
             Paragraph("Confidential organisation data export", styles["Normal"]), Spacer(1, 5*mm)]
    table_data = [[Paragraph(str(value), styles["BodyText"]) for value in headers]]
    count = 0
    for row in rows:
        count += 1
        if count > 2500:
            raise ValueError("PDF exports are limited to 2,500 rows. Use Excel for larger exports.")
        table_data.append([Paragraph(str(_safe_cell(value)), styles["BodyText"]) for value in row])
    widths = [doc.width / len(headers)] * len(headers)
    table = Table(table_data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
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
