import csv
import json
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.collections.models import MilkCollection
from apps.finance.models import Payment
from apps.organizations.models import Organization

from .models import Customer, Farmer


@login_required
def customer_portal(request):
    customer = (
        Customer.objects.filter(
            user=request.user,
            is_active=True,
            deleted_at__isnull=True,
            organization__status__in=[Organization.Status.TRIAL, Organization.Status.ACTIVE],
        )
        .select_related("organization", "branch", "user")
        .first()
    )
    if customer is None:
        return render(request, "customer/not_linked.html", status=403)

    collections = (
        customer.collections.filter(status=MilkCollection.Status.APPROVED)
        .select_related("branch", "pricing")
        .order_by("-collected_at")
    )
    payments = (
        customer.payments.filter(status=Payment.Status.COMPLETED)
        .select_related("branch")
        .order_by("-paid_at", "-created_at")
    )

    today = timezone.localdate()
    month_start = today.replace(day=1)
    month_collections = collections.filter(
        collected_at__date__gte=month_start, collected_at__date__lte=today
    )
    month_summary = month_collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    lifetime_summary = collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    context = {
        "customer": customer,
        "organization": customer.organization,
        "collections": collections[:50],
        "payments": payments[:25],
        "month_summary": month_summary,
        "lifetime_summary": lifetime_summary,
        "currency": customer.organization.currency,
    }
    return render(request, "customer/portal.html", context)


@login_required
def farmer_portal(request):
    farmer = (
        Farmer.objects.filter(
            user=request.user,
            is_active=True,
            deleted_at__isnull=True,
            organization__status__in=[Organization.Status.TRIAL, Organization.Status.ACTIVE],
        )
        .select_related("organization", "branch", "user")
        .first()
    )
    if farmer is None:
        return render(request, "farmer/not_linked.html", status=403)

    all_collections = (
        farmer.collections.filter(status=MilkCollection.Status.APPROVED)
        .select_related("branch", "pricing")
        .order_by("-collected_at")
    )
    collections = all_collections
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    shift_filter = request.GET.get("shift", "").strip()
    search = request.GET.get("q", "").strip()
    if date_from:
        collections = collections.filter(collected_at__date__gte=date_from)
    if date_to:
        collections = collections.filter(collected_at__date__lte=date_to)
    if shift_filter in dict(MilkCollection.Shift.choices):
        collections = collections.filter(shift=shift_filter)
    else:
        shift_filter = ""
    if search:
        collections = collections.filter(reference__icontains=search)
    collection_totals = collections.aggregate(
        total_litres=Sum("quantity_litres"),
        total_value=Sum("total_amount"),
        average_fat=Avg("fat"),
        average_snf=Avg("snf"),
        average_lactose=Avg("lactose"),
        record_count=Count("pk"),
    )
    total_litres = collection_totals["total_litres"] or 0
    total_value = collection_totals["total_value"] or 0
    average_rate = (total_value / total_litres) if total_litres else 0
    export_format = request.GET.get("export_format", "pdf").lower()
    if request.GET.get("export") == "1":
        if export_format == "csv":
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = 'attachment; filename="farmer-collections.csv"'
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(
                [
                    "Date",
                    "Reference",
                    "Branch",
                    "Shift",
                    "Litres",
                    "FAT",
                    "SNF",
                    "Lactose",
                    "Rate per litre",
                    "Total amount",
                ]
            )
            for item in collections.iterator(chunk_size=500):
                writer.writerow(
                    [
                        item.collected_at.strftime("%Y-%m-%d %H:%M"),
                        item.reference,
                        item.branch.name if item.branch else "",
                        item.get_shift_display(),
                        item.quantity_litres,
                        item.fat,
                        item.snf,
                        item.lactose,
                        item.milk_rate,
                        item.total_amount,
                    ]
                )
            return response
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=24,
            leftMargin=24,
            topMargin=28,
            bottomMargin=28,
        )
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        title_style.fontName = "Helvetica-Bold"
        title_style.fontSize = 18
        title_style.textColor = colors.HexColor("#17365D")
        info_style = styles["Normal"]
        info_style.fontSize = 9
        info_style.leading = 13
        story = [
            Paragraph("MILK COLLECTION STATEMENT", title_style),
            Spacer(1, 6),
            Paragraph(
                f"<b>Farmer:</b> {farmer.full_name} &nbsp;&nbsp; <b>Farmer ID:</b> {farmer.code}",
                info_style,
            ),
            Paragraph(
                (
                    f"<b>Branch:</b> {farmer.branch.name if farmer.branch else 'Not assigned'} "
                    f"&nbsp;&nbsp; <b>Period:</b> {date_from or 'All dates'} to "
                    f"{date_to or 'All dates'} &nbsp;&nbsp; <b>Shift:</b> "
                    f"{shift_filter or 'All shifts'}"
                ),
                info_style,
            ),
            Spacer(1, 8),
        ]
        avg_fat, avg_snf, avg_lactose = (
            collection_totals["average_fat"],
            collection_totals["average_snf"],
            collection_totals["average_lactose"],
        )

        def avg_fmt(value):
            return f"{value:.3f}" if value is not None else "?"

        summary_data = [
            [
                "RECORDS",
                "TOTAL MILK",
                "AVG FAT",
                "AVG SNF",
                "AVG LACTOSE",
                "WEIGHTED RATE / L",
                "TOTAL VALUE",
            ],
            [
                str(collection_totals["record_count"]),
                f"{total_litres:,.3f} L",
                avg_fmt(avg_fat),
                avg_fmt(avg_snf),
                avg_fmt(avg_lactose),
                f"{farmer.organization.currency} {average_rate:,.2f}",
                f"{farmer.organization.currency} {total_value:,.2f}",
            ],
        ]
        summary_table = Table(summary_data, colWidths=[60, 82, 52, 52, 64, 110, 110], hAlign="LEFT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EAF1F8")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C7D3E0")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.extend([summary_table, Spacer(1, 12)])
        cell_style = ParagraphStyle(
            "MilkReportCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8,
            wordWrap="CJK",
        )
        data = [
            [
                "Date & time",
                "Reference",
                "Branch",
                "Shift",
                "Litres",
                "FAT",
                "SNF",
                "Lactose",
                "Rate/L",
                "Amount",
            ]
        ]
        for item in collections.iterator(chunk_size=500):
            data.append(
                [
                    item.collected_at.strftime("%d %b %Y, %H:%M"),
                    Paragraph(str(item.reference), cell_style),
                    str(item.branch.name if item.branch else "?"),
                    item.get_shift_display(),
                    f"{item.quantity_litres:,.3f}",
                    f"{item.fat:.3f}" if item.fat is not None else "?",
                    f"{item.snf:.3f}" if item.snf is not None else "?",
                    f"{item.lactose:.3f}" if item.lactose is not None else "?",
                    f"{item.milk_rate:,.2f}",
                    f"{item.total_amount:,.2f}",
                ]
            )
        data.append(
            [
                "TOTAL / AVG",
                "",
                "",
                "",
                f"{total_litres:,.3f}",
                avg_fmt(avg_fat),
                avg_fmt(avg_snf),
                avg_fmt(avg_lactose),
                f"{average_rate:,.2f}",
                f"{total_value:,.2f}",
            ]
        )
        table = Table(
            data, repeatRows=1, colWidths=[88, 118, 88, 52, 60, 42, 42, 48, 65, 78], hAlign="LEFT"
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C7D3E0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -2),
                        [colors.white, colors.HexColor("#F3F6FA")],
                    ),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#DCE6F1")),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="farmer-collections.pdf"'
        return response

    payments = (
        farmer.payments.filter(
            direction=Payment.Direction.OUTGOING,
            status=Payment.Status.COMPLETED,
            deleted_at__isnull=True,
        )
        .select_related("branch")
        .order_by("-paid_at", "-created_at")
    )
    pending_payments = (
        farmer.payments.filter(
            direction=Payment.Direction.OUTGOING,
            status=Payment.Status.PENDING,
            deleted_at__isnull=True,
        )
        .select_related("branch")
        .order_by("-created_at")
    )
    today = timezone.localdate()
    month_start = today.replace(day=1)
    week_start = today - timedelta(days=today.weekday())
    previous_month_end = month_start - timedelta(days=1)
    previous_month_start = previous_month_end.replace(day=1)
    month_collections = all_collections.filter(
        collected_at__date__gte=month_start, collected_at__date__lte=today
    )
    today_collections = all_collections.filter(collected_at__date=today)
    week_collections = all_collections.filter(
        collected_at__date__gte=week_start, collected_at__date__lte=today
    )
    previous_month_collections = all_collections.filter(
        collected_at__date__gte=previous_month_start, collected_at__date__lte=previous_month_end
    )
    today_summary = today_collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    today_shift = today_collections.aggregate(
        morning=Sum("quantity_litres", filter=Q(shift=MilkCollection.Shift.MORNING)),
        evening=Sum("quantity_litres", filter=Q(shift=MilkCollection.Shift.EVENING)),
    )
    month_summary = month_collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    lifetime_summary = all_collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    week_summary = week_collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    previous_month_summary = previous_month_collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    month_quality = month_collections.aggregate(
        average_fat=Avg("fat"), average_snf=Avg("snf"), average_lactose=Avg("lactose")
    )
    quality_summary = all_collections.aggregate(
        average_fat=Avg("fat"), average_snf=Avg("snf"), average_lactose=Avg("lactose")
    )
    latest_collection = all_collections.first()
    average_litres = all_collections.aggregate(avg=Avg("quantity_litres"))["avg"]
    active_days = all_collections.dates("collected_at", "day", order="DESC").count()
    lifetime_payment_summary = payments.aggregate(amount=Sum("amount"))
    completed_paid_lifetime = lifetime_payment_summary["amount"] or 0
    lifetime_milk_value = lifetime_summary["amount"] or 0
    outstanding_balance = max(lifetime_milk_value - completed_paid_lifetime, 0)

    # Financial summary follows date filters only (not shift or reference search).
    finance_collections = all_collections
    finance_start = date_from or month_start.isoformat()
    finance_end = date_to or today.isoformat()
    if finance_start:
        finance_collections = finance_collections.filter(collected_at__date__gte=finance_start)
    if finance_end:
        finance_collections = finance_collections.filter(collected_at__date__lte=finance_end)
    selected_period_earnings = (
        finance_collections.aggregate(amount=Sum("total_amount"))["amount"] or 0
    )

    from datetime import date

    start_date = date.fromisoformat(finance_start)
    end_date = date.fromisoformat(finance_end)
    period_days = max((end_date - start_date).days + 1, 1)
    previous_end = start_date - timedelta(days=1)
    previous_start = previous_end - timedelta(days=period_days - 1)
    previous_period_earnings = (
        all_collections.filter(
            collected_at__date__gte=previous_start,
            collected_at__date__lte=previous_end,
        ).aggregate(amount=Sum("total_amount"))["amount"]
        or 0
    )

    finance_payments = payments
    if finance_start:
        finance_payments = finance_payments.filter(paid_at__date__gte=finance_start)
    if finance_end:
        finance_payments = finance_payments.filter(paid_at__date__lte=finance_end)
    payments_selected_period = finance_payments.aggregate(amount=Sum("amount"))["amount"] or 0
    payment_summary = {"amount": payments_selected_period}
    last_payment = finance_payments.first() or payments.first()
    trend_rows = list(
        all_collections.values("collected_at__date")
        .annotate(
            litres=Sum("quantity_litres"),
            morning=Sum("quantity_litres", filter=Q(shift=MilkCollection.Shift.MORNING)),
            evening=Sum("quantity_litres", filter=Q(shift=MilkCollection.Shift.EVENING)),
        )
        .order_by("-collected_at__date")[:7]
    )
    production_trend = [
        {
            "date": row["collected_at__date"].isoformat(),
            "litres": float(row["litres"] or 0),
            "morning": float(row["morning"] or 0),
            "evening": float(row["evening"] or 0),
        }
        for row in reversed(trend_rows)
    ]

    return render(
        request,
        "farmer/portal.html",
        {
            "farmer": farmer,
            "organization": farmer.organization,
            "collections": Paginator(collections, 50).get_page(request.GET.get("page")),
            "collection_count": collection_totals["record_count"],
            "total_litres": total_litres,
            "total_value": total_value,
            "average_rate": average_rate,
            "average_fat_filtered": collection_totals["average_fat"],
            "average_snf_filtered": collection_totals["average_snf"],
            "average_lactose_filtered": collection_totals["average_lactose"],
            "date_from": date_from,
            "date_to": date_to,
            "shift_filter": shift_filter,
            "search_query": search,
            "shift_choices": MilkCollection.Shift.choices,
            "payments": payments[:25],
            "pending_payments": pending_payments[:25],
            "today_summary": today_summary,
            "today_shift": today_shift,
            "month_summary": month_summary,
            "lifetime_summary": lifetime_summary,
            "week_summary": week_summary,
            "previous_month_summary": previous_month_summary,
            "quality_summary": quality_summary,
            "month_quality": month_quality,
            "latest_collection": latest_collection,
            "average_litres": average_litres,
            "active_days": active_days,
            "payment_summary": payment_summary,
            "outstanding_balance": outstanding_balance,
            "current_month_earnings": selected_period_earnings,
            "previous_month_earnings": previous_period_earnings,
            "last_payment": last_payment,
            "payments_current_month": payments_selected_period,
            "lifetime_milk_value": lifetime_milk_value,
            "lifetime_payments_received": completed_paid_lifetime,
            "production_trend": production_trend,
            "trend_max": max((row["litres"] for row in production_trend), default=0) or 1,
            "production_trend_json": json.dumps(production_trend),
            "currency": farmer.organization.currency,
        },
    )
