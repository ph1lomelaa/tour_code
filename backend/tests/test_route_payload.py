import unittest

from app.services.partner_payload_builder import build_partner_payload
from app.services.route_utils import route_endpoints


class RoutePayloadTests(unittest.TestCase):
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
