from datetime import date

from django.test import SimpleTestCase

from apps.core.nepali_dates import format_local_date, parse_local_date


class LocaleDateTests(SimpleTestCase):
    def test_nepali_date_round_trip(self):
        gregorian = date(2024, 4, 13)
        nepali_value = format_local_date(gregorian, "ne")
        self.assertEqual(parse_local_date(nepali_value, "ne"), gregorian)

    def test_english_date_remains_gregorian(self):
        gregorian = date(2024, 4, 13)
        self.assertEqual(format_local_date(gregorian, "en"), "2024-04-13")
        self.assertEqual(parse_local_date("2024-04-13", "en"), gregorian)

    def test_hindi_uses_gregorian_calendar(self):
        gregorian = date(2024, 4, 13)
        self.assertEqual(format_local_date(gregorian, "hi"), "2024-04-13")
        self.assertEqual(parse_local_date("2024-04-13", "hi"), gregorian)

    def test_invalid_nepali_date_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_local_date("2081-99-99", "ne")


class NepaliCalendarEndpointTests(SimpleTestCase):
    def test_current_month_endpoint_returns_calendar_grid_metadata(self):
        from django.urls import reverse

        response = self.client.get(reverse("nepali_calendar_month"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("month_name", payload)
        self.assertGreaterEqual(payload["days_in_month"], 29)
        self.assertLessEqual(payload["days_in_month"], 32)
        self.assertEqual(len(payload["days"]), payload["days_in_month"])
        self.assertGreaterEqual(payload["first_weekday"], 0)
        self.assertLessEqual(payload["first_weekday"], 6)

    def test_invalid_month_is_rejected(self):
        from django.urls import reverse

        response = self.client.get(reverse("nepali_calendar_month"), {"year": 2081, "month": 13})
        self.assertEqual(response.status_code, 400)

    def test_calendar_endpoint_rejects_post(self):
        from django.urls import reverse

        response = self.client.post(reverse("nepali_calendar_month"))
        self.assertEqual(response.status_code, 405)
