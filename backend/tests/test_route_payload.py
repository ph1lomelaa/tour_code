import unittest

from app.api.v1.tours import _get_departure_city
from app.google_sheet_parser.google_sheets_service import GoogleSheetsService
from app.services.partner_payload_builder import build_partner_payload
from app.services.route_utils import route_endpoints


class RoutePayloadTests(unittest.TestCase):
    def test_cit_jed_sheet_route_and_departure_city(self):
        service = GoogleSheetsService()
        for route in ("CIT-JED", "cit-jed"):
            with self.subTest(route=route):
                tour = service._parse_sheet_name(f"17.02.2026-24.02.2026 {route}")
                self.assertIsNotNone(tour)
                self.assertEqual(tour["route"], "CIT-JED")
                self.assertEqual(_get_departure_city(tour["route"]), "Shymkent")

    def test_cit_jed_payload_preserves_selected_hotel(self):
        for hotel in ("Dar Al Taqwa Madinah 5*", "Courtyard by Marriott"):
            with self.subTest(hotel=hotel):
                prepared = build_partner_payload(
                    {
                        "tour": {"route": "CIT-JED", "days": 8},
                        "selection": {"hotel": hotel},
                        "results": {"matched": [{"document": "N00000001"}]},
                    }
                )
                payload = prepared["json_items"][0]["payload"]
                self.assertEqual(payload["q_airport_start"], "CIT")
                self.assertEqual(payload["q_airport"], "JED")
                self.assertEqual(payload["q_hotel"], hotel)

    def test_route_endpoints_support_connection(self):
        self.assertEqual(route_endpoints("ALA-DOH-JED"), ("ALA", "JED"))
        self.assertEqual(route_endpoints("JED-DOH-ALA"), ("JED", "ALA"))

    def test_partner_payload_uses_endpoints_and_qatar_airways(self):
        prepared = build_partner_payload(
            {
                "tour": {
                    "route": "ALA-DOH-JED",
                    "airlines": "qr",
                    "date_start": "15.10.2026",
                    "date_end": "22.10.2026",
                    "days": 8,
                },
                "selection": {"country": "Саудовская Аравия"},
                "results": {"matched": [{"document": "N08462365"}]},
            }
        )

        payload = prepared["json_items"][0]["payload"]
        self.assertEqual(payload["q_airport_start"], "ALA")
        self.assertEqual(payload["q_airport"], "JED")
        self.assertEqual(payload["q_airlines"], "QR")

    def test_partner_payload_uses_kamkor_country_names(self):
        countries = {
            "Казахстан": "Kazakhstan",
            "Катар": "Qatar",
            "Объединенные Арабские Эмираты": "United Arab Emirates",
            "ОАЭ": "United Arab Emirates",
            "Саудовская Аравия": "Saudi Arabia",
            "Турция": "Turkey",
        }

        for country, country_en in countries.items():
            with self.subTest(country=country):
                prepared = build_partner_payload(
                    {
                        "tour": {"route": "ALA-JED", "days": 1},
                        "selection": {"country": country},
                        "results": {"matched": [{"document": "N08462365"}]},
                    }
                )
                payload = prepared["json_items"][0]["payload"]
                self.assertEqual(payload["q_country"], country)
                self.assertEqual(payload["q_countryen"], country_en)


if __name__ == "__main__":
    unittest.main()
