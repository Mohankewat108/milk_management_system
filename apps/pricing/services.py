from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import PricingConfiguration, QualityConfiguration

CENT = Decimal("0.01")


def calculate_milk_rate(*, snf, fat, lactose, pricing):
    """Apply the legacy documented formula using Decimal arithmetic."""
    values = [Decimal(str(value)) for value in (snf, fat, lactose)]
    if any(value < 0 for value in values):
        raise ValidationError("Quality measurements cannot be negative.")
    rate = (
        values[0] * pricing.snf_rate
        + values[1] * pricing.fat_rate
        + values[2] * pricing.lactose_rate
    )
    return rate.quantize(CENT, rounding=ROUND_HALF_UP)


def pricing_for_collection(*, organization, branch, collection_date):
    candidates = PricingConfiguration.objects.filter(
        organization=organization, is_approved=True, effective_from__lte=collection_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=collection_date))
    candidates = candidates.filter(Q(branch=branch) | Q(branch__isnull=True))
    specific = candidates.filter(branch=branch).first()
    if specific:
        return specific
    fallback = candidates.filter(branch__isnull=True).first()
    if fallback is None:
        raise ValidationError("No approved pricing configuration is effective for this date.")
    return fallback


def quality_configuration_for(*, organization, branch, collection_date):
    candidates = QualityConfiguration.objects.filter(
        organization=organization, is_approved=True, effective_from__lte=collection_date,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=collection_date))
    candidates = candidates.filter(Q(branch=branch) | Q(branch__isnull=True))
    return candidates.filter(branch=branch).first() or candidates.filter(branch__isnull=True).first()


def validate_quality_measurements(*, snf, fat, lactose, configuration):
    if configuration is None:
        return {"configured": False}
    values = {
        "snf": Decimal(str(snf)),
        "fat": Decimal(str(fat)),
        "lactose": Decimal(str(lactose)),
    }
    snapshot = {"configured": True, "version": configuration.version, "ranges": {}}
    for name, value in values.items():
        minimum = getattr(configuration, f"{name}_min")
        maximum = getattr(configuration, f"{name}_max")
        snapshot["ranges"][name] = {"min": str(minimum), "max": str(maximum)}
        if value < minimum or value > maximum:
            raise ValidationError(
                f"{name.upper()} value must be between {minimum} and {maximum} "
                "for the selected effective quality profile."
            )
    return snapshot
