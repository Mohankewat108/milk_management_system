import csv
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.collections.models import MilkCollection
from apps.finance.models import Payment
from apps.pricing.services import active_pricing_on

from .models import Customer


def _customer_date(value, fallback):
    if not value:
        return fallback
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


def _csv_safe(value):
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


@login_required
def customer_portal(request, format=None):
    customer = Customer.objects.filter(user=request.user, is_active=True).select_related(
        "organization", "branch", "user"
    ).first()
    if customer is None:
        return render(request, "customer/not_linked.html", status=403)

    organization = customer.organization
    try:
        tenant_timezone = ZoneInfo(organization.timezone)
    except (ZoneInfoNotFoundError, TypeError):
        tenant_timezone = timezone.get_current_timezone()
    today = timezone.localdate(timezone=tenant_timezone)

    collections = customer.collections.filter(
        status=MilkCollection.Status.APPROVED
    ).select_related("branch", "pricing").order_by("-collected_at", "-created_at")
    payments = customer.payments.filter(
        status=Payment.Status.COMPLETED
    ).select_related("branch").order_by("-paid_at", "-created_at")

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

    start_date = _customer_date(request.GET.get("from"), month_start)
    end_date = _customer_date(request.GET.get("to"), today)
    date_error = ""
    if start_date > end_date:
        date_error = "The start date must be on or before the end date."
        start_date, end_date = month_start, today

    filtered_collections = collections.filter(
        collected_at__date__gte=start_date, collected_at__date__lte=end_date
    )
    filtered_payments = payments.filter(
        paid_at__date__gte=start_date, paid_at__date__lte=end_date
    )

    if format == "csv" or request.GET.get("format") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="customer-statement-{customer.code}-{start_date}-{end_date}.csv"'
        )
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow([
            "Collection date", "Reference", "Branch", "Quantity (L)", "SNF", "Fat",
            "Lactose", "Lactometer", "Rate per litre", "Total amount", "Pricing version",
        ])
        for item in filtered_collections.iterator():
            writer.writerow([
                _csv_safe(timezone.localtime(item.collected_at, tenant_timezone).isoformat()),
                _csv_safe(item.reference), _csv_safe(item.branch.name),
                item.quantity_litres, item.snf, item.fat, item.lactose,
                item.lactometer_reading or "", item.milk_rate, item.total_amount,
                item.pricing_snapshot.get("version", ""),
            ])
        writer.writerow([])
        writer.writerow(["Completed payments"])
        writer.writerow(["Payment date", "Reference", "Method", "Transaction reference", "Amount", "Currency"])
        for payment in filtered_payments.iterator():
            writer.writerow([
                _csv_safe(timezone.localtime(payment.paid_at, tenant_timezone).isoformat()),
                _csv_safe(payment.reference), _csv_safe(payment.get_method_display()),
                _csv_safe(payment.transaction_reference), payment.amount, payment.currency,
            ])
        return response

    collection_page = Paginator(filtered_collections, 25).get_page(request.GET.get("page"))
    payment_page = Paginator(filtered_payments, 15).get_page(request.GET.get("payment_page"))
    active_rate = active_pricing_on(
        organization=organization, pricing_date=today, branch=customer.branch
    )
    context = {
        "customer": customer,
        "organization": organization,
        "collections": collection_page,
        "payments": payment_page,
        "month_summary": month_summary,
        "lifetime_summary": lifetime_summary,
        "currency": organization.currency,
        "active_rate": active_rate,
        "rate_date": today,
        "start_date": start_date,
        "end_date": end_date,
        "date_error": date_error,
        "statement_litres": filtered_collections.aggregate(total=Sum("quantity_litres"))["total"],
        "statement_amount": filtered_collections.aggregate(total=Sum("total_amount"))["total"],
        "statement_payment_total": filtered_payments.aggregate(total=Sum("amount"))["total"],
    }
    return render(request, "customer/portal.html", context)
