from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.organizations.permissions import require_actor_branch_access
from apps.pricing.services import (
    calculate_milk_rate,
    pricing_for_collection,
    quality_configuration_for,
    validate_quality_measurements,
)

from .models import MilkCollection


@transaction.atomic
def create_collection(
    *,
    organization,
    branch,
    actor,
    collected_at,
    shift="morning",
    quantity_litres,
    snf,
    fat,
    lactose,
    farmer=None,
    customer=None,
    notes="",
    lactometer_reading=None,
    milk_temperature_c=None,
    sample_reference="",
    quality_test_method="",
    tested_by=None,
    idempotency_key="",
):
    if branch.organization_id != organization.id or not branch.is_active:
        raise ValidationError("Select an active branch belonging to this organisation.")
    require_actor_branch_access(actor=actor, organization=organization, branch=branch)
    if bool(farmer) == bool(customer):
        raise ValidationError("Select exactly one farmer or customer.")
    party = farmer or customer
    if (
        party.organization_id != organization.id
        or not party.is_active
        or getattr(party, "deleted_at", None) is not None
    ):
        raise ValidationError("The selected party is not active in this organisation.")
    if party.branch_id and party.branch_id != branch.id:
        raise ValidationError("The selected farmer/customer belongs to a different branch.")
    quantity = Decimal(str(quantity_litres))
    quality = [Decimal(str(value)) for value in (snf, fat, lactose)]
    if quantity <= 0:
        raise ValidationError("Milk quantity must be greater than zero.")
    if any(value < 0 for value in quality):
        raise ValidationError("Quality measurements cannot be negative.")
    lactometer = Decimal(str(lactometer_reading)) if lactometer_reading not in (None, "") else None
    temperature = Decimal(str(milk_temperature_c)) if milk_temperature_c not in (None, "") else None
    if lactometer is not None and lactometer < 0:
        raise ValidationError("Lactometer reading cannot be negative.")
    if len(idempotency_key) > 64:
        raise ValidationError("The submission key is invalid.")

    def matches_submission(collection):
        return all(
            (
                collection.branch_id == branch.id,
                collection.farmer_id == getattr(farmer, "id", None),
                collection.customer_id == getattr(customer, "id", None),
                collection.recorded_by_id == actor.id,
                collection.collected_at == collected_at,
                collection.shift == shift,
                collection.quantity_litres == quantity,
                collection.snf == quality[0],
                collection.fat == quality[1],
                collection.lactose == quality[2],
                collection.lactometer_reading == lactometer,
                collection.milk_temperature_c == temperature,
                collection.sample_reference == sample_reference,
                collection.quality_test_method == quality_test_method,
                collection.tested_by_id == getattr(tested_by or actor, "id", None),
                collection.notes == notes,
            )
        )

    def existing_submission():
        if not idempotency_key:
            return None
        existing = MilkCollection.objects.filter(
            organization=organization, idempotency_key=idempotency_key
        ).first()
        if existing and not matches_submission(existing):
            raise ValidationError("This submission key was already used for different data.")
        return existing

    existing = existing_submission()
    if existing:
        return existing

    # Resolve the applicable price using the dairy's local business date, not
    # the server's UTC date. This matters for late-night collections near midnight.
    try:
        tenant_tz = ZoneInfo(organization.timezone or timezone.get_current_timezone_name())
    except ZoneInfoNotFoundError:
        tenant_tz = timezone.get_current_timezone()
    local_collected_at = (
        timezone.localtime(collected_at, tenant_tz)
        if timezone.is_aware(collected_at)
        else timezone.make_aware(collected_at, tenant_tz)
    )
    collection_date = local_collected_at.date()
    pricing = pricing_for_collection(
        organization=organization, branch=branch, collection_date=collection_date
    )
    quality_config = quality_configuration_for(
        organization=organization, branch=branch, collection_date=collection_date
    )
    quality_snapshot = validate_quality_measurements(
        snf=quality[0], fat=quality[1], lactose=quality[2], configuration=quality_config
    )
    rate = calculate_milk_rate(snf=quality[0], fat=quality[1], lactose=quality[2], pricing=pricing)
    total = (quantity * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    components = {
        "snf_component": str(
            (quality[0] * pricing.snf_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
        "fat_component": str(
            (quality[1] * pricing.fat_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
        "lactose_component": str(
            (quality[2] * pricing.lactose_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
    }
    snapshot = {
        "version": pricing.version,
        "effective_from": pricing.effective_from.isoformat(),
        "effective_to": pricing.effective_to.isoformat() if pricing.effective_to else None,
        "snf_rate": str(pricing.snf_rate),
        "fat_rate": str(pricing.fat_rate),
        "lactose_rate": str(pricing.lactose_rate),
        **components,
        "formula": "(SNF × SNF rate) + (FAT × FAT rate) + (Lactose × Lactose rate)",
        "currency": organization.currency,
        "quality_profile": quality_snapshot,
    }
    try:
        with transaction.atomic():
            entry = MilkCollection.objects.create(
                status=MilkCollection.Status.APPROVED,
                organization=organization,
                branch=branch,
                reference=f"MC-{local_collected_at:%Y%m%d}-{uuid4().hex[:8].upper()}",
                farmer=farmer,
                customer=customer,
                recorded_by=actor,
                collected_at=collected_at,
                shift=shift,
                quantity_litres=quantity,
                snf=quality[0],
                fat=quality[1],
                lactose=quality[2],
                lactometer_reading=lactometer,
                milk_temperature_c=temperature,
                sample_reference=sample_reference,
                quality_test_method=quality_test_method,
                tested_by=tested_by or actor,
                milk_rate=rate,
                total_amount=total,
                pricing=pricing,
                pricing_snapshot=snapshot,
                notes=notes,
                idempotency_key=idempotency_key,
            )
            from apps.finance.ledger_services import (
                post_approved_customer_collection_sale,
                post_approved_farmer_collection,
            )
            if entry.farmer_id:
                post_approved_farmer_collection(collection=entry, actor=actor)
            elif entry.customer_id:
                post_approved_customer_collection_sale(collection=entry, actor=actor)
            return entry
    except IntegrityError:
        existing = existing_submission()
        if existing:
            return existing
        raise


@transaction.atomic
def approve_collection(*, collection_id, organization, actor):
    """Approve a submitted collection and post its configured accounting effect atomically."""
    from apps.finance.ledger_services import (
        post_approved_customer_collection_sale,
        post_approved_farmer_collection,
    )
    from apps.organizations.permissions import require_actor_branch_access

    entry = MilkCollection.objects.select_for_update().get(
        pk=collection_id, organization=organization
    )
    require_actor_branch_access(actor=actor, organization=organization, branch=entry.branch)
    if entry.status != MilkCollection.Status.SUBMITTED:
        raise ValidationError("Only submitted collections can be approved.")
    entry.status = MilkCollection.Status.APPROVED
    entry.save(update_fields=["status", "updated_at"])
    if entry.farmer_id:
        post_approved_farmer_collection(collection=entry, actor=actor)
    elif entry.customer_id:
        post_approved_customer_collection_sale(collection=entry, actor=actor)
    return entry


@transaction.atomic
def reverse_collection(*, collection_id, organization, actor, reason):
    """Reverse a collection and any associated posted ledger journal atomically."""
    from apps.finance.ledger_services import reverse_journal_entry
    from apps.finance.models import JournalEntry

    from .models import MilkCollection

    entry = MilkCollection.objects.select_for_update().get(
        pk=collection_id, organization=organization
    )
    require_actor_branch_access(actor=actor, organization=organization, branch=entry.branch)
    if entry.status == MilkCollection.Status.REVERSED:
        return entry
    if len((reason or "").strip()) < 8:
        raise ValidationError("Provide a clear reversal reason (at least 8 characters).")

    if entry.status == MilkCollection.Status.APPROVED:
        source_types = []
        if entry.farmer_id:
            source_types.append("milk_collection")
        elif entry.customer_id:
            source_types.append("customer_milk_sale")

        journals = JournalEntry.objects.filter(
            organization=organization,
            source_type__in=source_types,
            source_id=str(entry.pk),
            status=JournalEntry.Status.POSTED,
            reversal__isnull=True,
        ).select_related("period", "branch")

        for journal in journals:
            reversal_date = timezone.localdate()
            try:
                tenant_tz = ZoneInfo(organization.timezone or timezone.get_current_timezone_name())
            except ZoneInfoNotFoundError:
                tenant_tz = timezone.get_current_timezone()
            reversal_date = timezone.now().astimezone(tenant_tz).date()
            reverse_journal_entry(
                entry_id=journal.pk,
                organization=organization,
                actor=actor,
                reversal_date=reversal_date,
                reason=reason.strip(),
            )

    entry.status = MilkCollection.Status.REVERSED
    entry.notes = (entry.notes + "\\n" if entry.notes else "") + f"REVERSAL: {reason.strip()}"
    entry.save(update_fields=["status", "notes", "updated_at"])
    return entry
