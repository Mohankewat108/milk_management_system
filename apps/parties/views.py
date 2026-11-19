from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.collections.models import MilkCollection
from apps.finance.models import Payment

from .models import Customer


@login_required
def customer_portal(request):
    customer = (
        Customer.objects.filter(user=request.user, is_active=True)
        .select_related("organization", "branch", "user")
        .first()
    )
    if customer is None:
        return render(request, "customer/not_linked.html", status=403)

    # A customer only sees records belonging to their own linked customer profile.
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

    today = date.today()
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
    recent_collections = collections[:50]
    recent_payments = payments[:25]
    context = {
        "customer": customer,
        "organization": customer.organization,
        "collections": recent_collections,
        "payments": recent_payments,
        "month_summary": month_summary,
        "lifetime_summary": lifetime_summary,
        "currency": customer.organization.currency,
    }
    return render(request, "customer/portal.html", context)
