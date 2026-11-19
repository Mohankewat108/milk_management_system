from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.organizations.permissions import require_actor_branch_access

from .models import Expense, Payment


@transaction.atomic
def record_expense(
    *,
    organization,
    branch,
    actor,
    category,
    description,
    amount,
    expense_date,
    method,
    supplier_name="",
    notes="",
):
    if branch.organization_id != organization.id or not branch.is_active:
        raise ValidationError("Select an active branch belonging to this organisation.")
    require_actor_branch_access(actor=actor, organization=organization, branch=branch)
    value = Decimal(str(amount))
    if value <= 0:
        raise ValidationError("Expense amount must be greater than zero.")
    return Expense.objects.create(
        organization=organization,
        branch=branch,
        reference=f"EXP-{uuid4().hex[:12].upper()}",
        category=category,
        description=description,
        supplier_name=supplier_name,
        amount=value,
        currency=organization.currency,
        expense_date=expense_date,
        method=method,
        recorded_by=actor,
        notes=notes,
    )


@transaction.atomic
def approve_expense(*, expense_id, organization, actor):
    expense = Expense.objects.select_for_update().get(pk=expense_id, organization=organization)
    require_actor_branch_access(actor=actor, organization=organization, branch=expense.branch)
    if expense.status != Expense.Status.PENDING:
        raise ValidationError("Only pending expenses can be approved.")
    expense.status = Expense.Status.APPROVED
    expense.approved_by = actor
    expense.approved_at = timezone.now()
    expense.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    from .ledger_services import post_approved_expense

    post_approved_expense(expense=expense, actor=actor)
    return expense


@transaction.atomic
def record_payment(
    *,
    organization,
    branch,
    actor,
    direction,
    amount,
    method,
    customer=None,
    farmer=None,
    status=Payment.Status.PENDING,
    notes="",
    transaction_reference="",
):
    if branch.organization_id != organization.id or not branch.is_active:
        raise ValidationError("Select an active branch belonging to this organisation.")
    require_actor_branch_access(actor=actor, organization=organization, branch=branch)
    if bool(customer) == bool(farmer):
        raise ValidationError("Select exactly one customer or farmer.")
    party = customer or farmer
    if party.organization_id != organization.id or not party.is_active:
        raise ValidationError("The selected party is not active in this organisation.")
    value = Decimal(str(amount))
    if value <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    if customer and direction != Payment.Direction.INCOMING:
        raise ValidationError("Customer payments must be incoming.")
    if farmer and direction != Payment.Direction.OUTGOING:
        raise ValidationError("Farmer payments must be outgoing.")
    paid_at = timezone.now() if status == Payment.Status.COMPLETED else None
    return Payment.objects.create(
        organization=organization,
        branch=branch,
        reference=f"PAY-{uuid4().hex[:12].upper()}",
        direction=direction,
        customer=customer,
        farmer=farmer,
        amount=value,
        currency=organization.currency,
        method=method,
        status=status,
        paid_at=paid_at,
        transaction_reference=transaction_reference,
        notes=notes,
        recorded_by=actor,
    )


@transaction.atomic
def complete_payment(*, payment_id, organization, actor):
    payment = Payment.objects.select_for_update().get(
        pk=payment_id, organization=organization, deleted_at__isnull=True
    )
    require_actor_branch_access(actor=actor, organization=organization, branch=payment.branch)
    if payment.status != Payment.Status.PENDING:
        raise ValidationError("Only pending payments can be completed.")
    payment.status = Payment.Status.COMPLETED
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "paid_at", "updated_at"])
    from .ledger_services import post_completed_payment

    post_completed_payment(payment=payment, actor=actor)
    return payment
