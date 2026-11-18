from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids, can_access_branch
from .forms import ExpenseEntryForm, PaymentEntryForm
from .models import Expense, Payment
from .services import approve_expense, record_expense, record_payment


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT)
def payment_list(request, organization_slug):
    records = Payment.objects.filter(organization=request.organization).select_related(
        "branch", "customer", "farmer", "recorded_by"
    ).order_by("-created_at")
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "finance/list.html", {
        "organization": request.organization, "page_obj": page, "membership": request.membership,
    })


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT)
@require_http_methods(["GET", "POST"])
def payment_create(request, organization_slug):
    organization = request.organization
    form = PaymentEntryForm(request.POST or None, organization=organization)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        if not can_access_branch(request.membership, data["branch"]):
            form.add_error("branch", "You are not assigned to this branch.")
        else:
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
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(
            pk=payment_id, organization=request.organization
        )
        branch_ids = accessible_branch_ids(request.membership)
        if branch_ids is not None and payment.branch_id not in branch_ids:
            messages.error(request, "You are not assigned to this branch.")
        elif payment.status == Payment.Status.PENDING:
            payment.status = Payment.Status.COMPLETED
            payment.paid_at = timezone.now()
            payment.save(update_fields=["status", "paid_at", "updated_at"])
            record_event(actor=request.user, organization=request.organization,
                         action="payment.completed", target=payment, request=request)
            messages.success(request, "Payment marked as completed.")
        else:
            messages.error(request, "Only pending payments can be completed.")
    return redirect("finance:list", organization_slug=organization_slug)


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT)
def expense_list(request, organization_slug):
    records = Expense.objects.filter(organization=request.organization).select_related(
        "branch", "recorded_by", "approved_by"
    ).order_by("-expense_date", "-created_at")
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(request, "finance/expenses.html", {
        "organization": request.organization, "page_obj": page, "membership": request.membership,
    })


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.ACCOUNTANT)
@require_http_methods(["GET", "POST"])
def expense_create(request, organization_slug):
    organization = request.organization
    form = ExpenseEntryForm(request.POST or None, organization=organization, membership=request.membership)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            expense = record_expense(
                organization=organization, branch=data["branch"], actor=request.user,
                category=data["category"], description=data["description"], supplier_name=data["supplier_name"],
                amount=data["amount"], expense_date=data["expense_date"], method=data["method"], notes=data["notes"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            record_event(actor=request.user, organization=organization, action="expense.recorded",
                         target=expense, request=request)
            messages.success(request, f"Expense {expense.reference} recorded pending approval.")
            return redirect("finance:expenses", organization_slug=organization_slug)
    return render(request, "finance/expense_form.html", {"organization": organization, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ACCOUNTANT)
@require_POST
def expense_approve(request, organization_slug, expense_id):
    try:
        expense = approve_expense(
            expense_id=expense_id, organization=request.organization, actor=request.user
        )
    except (Expense.DoesNotExist, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        record_event(actor=request.user, organization=request.organization,
                     action="expense.approved", target=expense, request=request)
        messages.success(request, "Expense approved.")
    return redirect("finance:expenses", organization_slug=organization_slug)
