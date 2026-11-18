from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.collections.models import MilkCollection
from apps.finance.models import Payment

from .models import Customer


@login_required
def customer_portal(request):
    customer = Customer.objects.filter(user=request.user, is_active=True).select_related(
        "organization"
    ).first()
    if customer is None:
        return render(request, "customer/not_linked.html", status=403)
    # Customers only see published/approved collection values and completed payments.
    collections = customer.collections.filter(
        status=MilkCollection.Status.APPROVED
    ).order_by("-collected_at")[:50]
    payments = customer.payments.filter(
        status=Payment.Status.COMPLETED
    ).order_by("-paid_at")[:25]
    return render(request, "customer/portal.html", {
        "customer": customer,
        "collections": collections,
        "payments": payments,
    })
