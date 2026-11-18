from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Customer


@login_required
def customer_portal(request):
    customer = Customer.objects.filter(user=request.user, is_active=True).first()
    if customer is None:
        return render(request, "customer/not_linked.html", status=403)
    collections = customer.collections.order_by("-collected_at")[:50]
    payments = customer.payments.order_by("-paid_at")[:25]
    return render(request, "customer/portal.html", {
        "customer": customer,
        "collections": collections,
        "payments": payments,
    })
