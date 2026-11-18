from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from .forms import PaymentEntryForm
from .models import Payment
from .services import record_payment


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT)
def payment_list(request, organization_slug):
    records = Payment.objects.filter(organization=request.organization).select_related(
        "branch", "customer", "farmer", "recorded_by"
    ).order_by("-created_at")
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "finance/list.html", {
        "organization": request.organization, "page_obj": page,
    })


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT)
@require_http_methods(["GET", "POST"])
def payment_create(request, organization_slug):
    organization = request.organization
    form = PaymentEntryForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            payment = record_payment(
                organization=organization, branch=data["branch"], actor=request.user,
                direction=data["direction"], amount=data["amount"], method=data["method"],
                customer=data["customer"], farmer=data["farmer"],
                transaction_reference=data["transaction_reference"], notes=data["notes"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            record_event(actor=request.user, organization=organization,
                         action="payment.recorded", target=payment, request=request)
            messages.success(request, f"Payment {payment.reference} saved as pending verification.")
            return redirect("finance:list", organization_slug=organization_slug)
    return render(request, "finance/form.html", {"organization": organization, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ACCOUNTANT)
@require_POST
def payment_complete(request, organization_slug, payment_id):
    payment = Payment.objects.get(pk=payment_id, organization=request.organization)
    if payment.status == Payment.Status.PENDING:
        payment.status = Payment.Status.COMPLETED
        payment.paid_at = __import__("django.utils.timezone", fromlist=["now"]).now()
        payment.save(update_fields=["status", "paid_at", "updated_at"])
        record_event(actor=request.user, organization=request.organization,
                     action="payment.completed", target=payment, request=request)
        messages.success(request, "Payment marked as completed.")
    else:
        messages.error(request, "Only pending payments can be completed.")
    return redirect("finance:list", organization_slug=organization_slug)
