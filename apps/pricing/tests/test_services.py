from decimal import Decimal
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.pricing.services import calculate_milk_rate


class MilkPricingTests(SimpleTestCase):
    def setUp(self):
        self.pricing = SimpleNamespace(
            snf_rate=Decimal("5.2500"),
            fat_rate=Decimal("7.1000"),
            lactose_rate=Decimal("1.2500"),
        )

    def test_uses_documented_formula_and_decimal_rounding(self):
        result = calculate_milk_rate(
            snf=Decimal("8.500"), fat=Decimal("3.800"),
            lactose=Decimal("4.600"), pricing=self.pricing,
        )
        expected = (
            Decimal("8.500") * Decimal("5.2500")
            + Decimal("3.800") * Decimal("7.1000")
            + Decimal("4.600") * Decimal("1.2500")
        ).quantize(Decimal("0.01"))
        self.assertEqual(result, expected)
        self.assertIsInstance(result, Decimal)

    def test_negative_quality_is_rejected(self):
        with self.assertRaises(ValidationError):
            calculate_milk_rate(
                snf="-0.1", fat="3.8", lactose="4.6", pricing=self.pricing
            )
