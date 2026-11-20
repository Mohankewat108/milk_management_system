from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

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

    collections = (
        farmer.collections.filter(status=MilkCollection.Status.APPROVED)
        .select_related("branch", "pricing")
        .order_by("-collected_at")
    )
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
    month_collections = collections.filter(
        collected_at__date__gte=month_start, collected_at__date__lte=today
    )
    month_summary = month_collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    lifetime_summary = collections.aggregate(
        litres=Sum("quantity_litres"), amount=Sum("total_amount")
    )
    payment_summary = payments.aggregate(amount=Sum("amount"))
    pending_summary = pending_payments.aggregate(amount=Sum("amount"))

    return render(
        request,
        "farmer/portal.html",
        {
            "farmer": farmer,
            "organization": farmer.organization,
            "collections": collections[:50],
            "payments": payments[:25],
            "pending_payments": pending_payments[:25],
            "month_summary": month_summary,
            "lifetime_summary": lifetime_summary,
            "payment_summary": payment_summary,
            "pending_summary": pending_summary,
            "currency": farmer.organization.currency,
        },
    )
