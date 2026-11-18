from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction

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
    farmer=None, customer=None, notes="",
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

    collection_date = collected_at.date()
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
    snapshot = {
        "version": pricing.version,
        "snf_rate": str(pricing.snf_rate),
        "fat_rate": str(pricing.fat_rate),
        "lactose_rate": str(pricing.lactose_rate),
        "formula": "(SNF × SNF rate) + (FAT × FAT rate) + (Lactose × Lactose rate)",
        "currency": organization.currency,
        "quality_profile": quality_snapshot,
    }
    return MilkCollection.objects.create(
        organization=organization, branch=branch,
        reference=f"MC-{collected_at:%Y%m%d}-{uuid4().hex[:8].upper()}",
        farmer=farmer, customer=customer, recorded_by=actor, collected_at=collected_at,
        quantity_litres=quantity, snf=quality[0], fat=quality[1], lactose=quality[2],
        milk_rate=rate, total_amount=total, pricing=pricing,
        pricing_snapshot=snapshot, notes=notes,
    )
