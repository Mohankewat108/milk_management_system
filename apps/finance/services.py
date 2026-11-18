from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Payment


@transaction.atomic
def record_payment(*, organization, branch, actor, direction, amount, method,
                   customer=None, farmer=None, status=Payment.Status.PENDING, notes="",
                   transaction_reference=""):
    if branch.organization_id != organization.id or not branch.is_active:
        raise ValidationError("Select an active branch belonging to this organisation.")
    if bool(customer) == bool(farmer):
        raise ValidationError("Select exactly one customer or farmer.")
    party = customer or farmer
    if party.organization_id != organization.id or not party.is_active:
        raise ValidationError("The selected party is not active in this organisation.")
    value = Decimal(str(amount))
    if value <= 0:
        raise ValidationError("Payment amount must be greater than zero.")
    paid_at = timezone.now() if status == Payment.Status.COMPLETED else None
    return Payment.objects.create(
        organization=organization, branch=branch,
        reference=f"PAY-{uuid4().hex[:12].upper()}", direction=direction,
        customer=customer, farmer=farmer, amount=value, currency=organization.currency,
        method=method, status=status, paid_at=paid_at,
        transaction_reference=transaction_reference, notes=notes, recorded_by=actor,
    )
