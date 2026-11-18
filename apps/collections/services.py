from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.pricing.services import (
    calculate_milk_rate,
    pricing_for_collection,
    quality_configuration_for,
    validate_quality_measurements,
)

from .models import MilkCollection


@transaction.atomic
def create_collection(
    *, organization, branch, actor, collected_at, quantity_litres, snf, fat, lactose,
    farmer=None, customer=None, notes="", lactometer_reading=None,
    milk_temperature_c=None, sample_reference="", quality_test_method="", tested_by=None,
):
    if branch.organization_id != organization.id or not branch.is_active:
        raise ValidationError("Select an active branch belonging to this organisation.")
    if bool(farmer) == bool(customer):
        raise ValidationError("Select exactly one farmer or customer.")
    party = farmer or customer
    if party.organization_id != organization.id or not party.is_active:
        raise ValidationError("The selected party is not active in this organisation.")
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

    # Resolve the applicable price using the dairy's local business date, not
    # the server's UTC date. This matters for late-night collections near midnight.
    try:
        tenant_tz = ZoneInfo(organization.timezone or timezone.get_current_timezone_name())
    except ZoneInfoNotFoundError:
        tenant_tz = timezone.get_current_timezone()
    local_collected_at = timezone.localtime(collected_at, tenant_tz) if timezone.is_aware(collected_at) else timezone.make_aware(collected_at, tenant_tz)
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
        "snf_component": str((quality[0] * pricing.snf_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "fat_component": str((quality[1] * pricing.fat_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "lactose_component": str((quality[2] * pricing.lactose_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
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
    return MilkCollection.objects.create(
        organization=organization, branch=branch,
        reference=f"MC-{local_collected_at:%Y%m%d}-{uuid4().hex[:8].upper()}",
        farmer=farmer, customer=customer, recorded_by=actor, collected_at=collected_at,
        quantity_litres=quantity, snf=quality[0], fat=quality[1], lactose=quality[2],
        lactometer_reading=lactometer, milk_temperature_c=temperature,
        sample_reference=sample_reference, quality_test_method=quality_test_method,
        tested_by=tested_by or actor,
        milk_rate=rate, total_amount=total, pricing=pricing,
        pricing_snapshot=snapshot, notes=notes,
    )
