from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.audit.services import record_event
from apps.organizations.decorators import organization_access
from apps.organizations.models import Membership
from apps.organizations.permissions import accessible_branch_ids, can_access_branch

from .forms import ExpenseEntryForm, PaymentEditForm, PaymentEntryForm
from .models import Expense, Payment
from .services import approve_expense, complete_payment, record_expense, record_payment


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.view")
def payment_list(request, organization_slug):
    records = (
        Payment.objects.filter(organization=request.organization, deleted_at__isnull=True)
        .select_related("branch", "customer", "farmer", "recorded_by")
        .order_by("-created_at")
    )
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "finance/list.html",
        {
            "organization": request.organization,
            "page_obj": page,
            "membership": request.membership,
        },
    )


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.manage")
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
                    organization=organization,
                    branch=data["branch"],
                    actor=request.user,
                    direction=data["direction"],
                    amount=data["amount"],
                    method=data["method"],
                    customer=data["customer"],
                    farmer=data["farmer"],
                    transaction_reference=data["transaction_reference"],
                    notes=data["notes"],
                    idempotency_key=data["idempotency_key"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                record_event(
                    actor=request.user,
                    organization=organization,
                    action="payment.recorded",
                    target=payment,
                    request=request,
                )
                messages.success(
                    request, f"Payment {payment.reference} saved as pending verification."
                )
                return redirect("finance:list", organization_slug=organization_slug)
    return render(request, "finance/form.html", {"organization": organization, "form": form})


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.manage")
@require_POST
def payment_complete(request, organization_slug, payment_id):
    try:
        payment = complete_payment(
            payment_id=payment_id, organization=request.organization, actor=request.user
        )
    except (Payment.DoesNotExist, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        record_event(
            actor=request.user,
            organization=request.organization,
            action="payment.completed",
            target=payment,
            request=request,
        )
        messages.success(request, "Payment marked as completed.")
    return redirect("finance:list", organization_slug=organization_slug)


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.view")
def expense_list(request, organization_slug):
    records = (
        Expense.objects.filter(organization=request.organization, deleted_at__isnull=True)
        .select_related("branch", "recorded_by", "approved_by")
        .order_by("-expense_date", "-created_at")
    )
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None:
        records = records.filter(branch_id__in=branch_ids)
    page = Paginator(records, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "finance/expenses.html",
        {
            "organization": request.organization,
            "page_obj": page,
            "membership": request.membership,
        },
    )


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.manage")
@require_http_methods(["GET", "POST"])
def expense_create(request, organization_slug):
    organization = request.organization
    form = ExpenseEntryForm(
        request.POST or None, organization=organization, membership=request.membership
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            expense = record_expense(
                organization=organization,
                branch=data["branch"],
                actor=request.user,
                category=data["category"],
                description=data["description"],
                supplier_name=data["supplier_name"],
                amount=data["amount"],
                expense_date=data["expense_date"],
                method=data["method"],
                notes=data["notes"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            record_event(
                actor=request.user,
                organization=organization,
                action="expense.recorded",
                target=expense,
                request=request,
            )
            messages.success(request, f"Expense {expense.reference} recorded pending approval.")
            return redirect("finance:expenses", organization_slug=organization_slug)
    return render(
        request, "finance/expense_form.html", {"organization": organization, "form": form}
    )


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.manage")
@require_POST
def expense_approve(request, organization_slug, expense_id):
    try:
        expense = approve_expense(
            expense_id=expense_id, organization=request.organization, actor=request.user
        )
    except (Expense.DoesNotExist, ValidationError) as exc:
        messages.error(request, str(exc))
    else:
        record_event(
            actor=request.user,
            organization=request.organization,
            action="expense.approved",
            target=expense,
            request=request,
        )
        messages.success(request, "Expense approved.")
    return redirect("finance:expenses", organization_slug=organization_slug)


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.view")
@require_http_methods(["GET", "POST"])
def payment_edit(request, organization_slug, payment_id):
    payment = get_object_or_404(
        Payment,
        pk=payment_id,
        organization=request.organization,
        deleted_at__isnull=True,
        status=Payment.Status.PENDING,
    )
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None and payment.branch_id not in branch_ids:
        messages.error(request, "You cannot edit a payment outside your assigned branches.")
        return redirect("finance:list", organization_slug=organization_slug)
    form = PaymentEditForm(
        request.POST or None,
        instance=payment,
        organization=request.organization,
        membership=request.membership,
    )
    if request.method == "POST" and form.is_valid():
        updated = form.save()
        record_event(
            actor=request.user,
            organization=request.organization,
            action="payment.updated",
            target=updated,
            changes={"updated_fields": list(form.changed_data)},
            request=request,
        )
        messages.success(request, f"Payment {updated.reference} updated.")
        return redirect("finance:list", organization_slug=organization_slug)
    return render(
        request,
        "finance/edit.html",
        {
            "organization": request.organization,
            "form": form,
            "record": payment,
            "record_type": "Payment",
        },
    )


@login_required
@organization_access(Membership.Role.OWNER, Membership.Role.ADMIN, Membership.Role.DAIRY_MANAGER, Membership.Role.ACCOUNTANT, permission="finance.view")
@require_http_methods(["GET", "POST"])
def expense_edit(request, organization_slug, expense_id):
    expense = get_object_or_404(
        Expense,
        pk=expense_id,
        organization=request.organization,
        deleted_at__isnull=True,
        status__in=[Expense.Status.PENDING, Expense.Status.REJECTED],
    )
    branch_ids = accessible_branch_ids(request.membership)
    if branch_ids is not None and expense.branch_id not in branch_ids:
        messages.error(request, "You cannot edit an expense outside your assigned branches.")
        return redirect("finance:expenses", organization_slug=organization_slug)
    form = ExpenseEntryForm(
        request.POST or None,
        instance=expense,
        organization=request.organization,
        membership=request.membership,
    )
    if request.method == "POST" and form.is_valid():
        updated = form.save()
        record_event(
            actor=request.user,
            organization=request.organization,
            action="expense.updated",
            target=updated,
            changes={"updated_fields": list(form.changed_data)},
            request=request,
        )
        messages.success(request, f"Expense {updated.reference} updated.")
        return redirect("finance:expenses", organization_slug=organization_slug)
    return render(
        request,
        "finance/edit.html",
        {
            "organization": request.organization,
            "form": form,
            "record": expense,
            "record_type": "Expense",
        },
    )
