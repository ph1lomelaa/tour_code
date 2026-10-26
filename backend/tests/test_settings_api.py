import unittest
from unittest import mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.services.dispatch_auth import DispatchAuthError
from app.services.kamkor_reference import KamkorDictionaries, KamkorUnavailable, bin_is_valid, verify
from app.services.partner_payload_builder import build_partner_payload
from db.models import Base, RefTouragent
from db.seed_reference import seed_reference_data


# Ответы справочников Камкора (тестовая платформа, сокращённо).
KAMKOR_DICTS = {
    "airlines": [
        {"iata": "KC", "airline": "Air Astana"},
        {"iata": "TK", "airline": "THY - Turkish Airlines"},
    ],
    "countries": [
        {"country": "Катар", "countryen": "Qatar"},
        {"country": "Турция", "countryen": "Turkey"},
        {"country": "Оман", "countryen": "Oman"},
    ],
    "airports": [{"iata": "ALA", "airport_en": "Almaty"}, {"iata": "JED", "airport_en": "Jeddah"}],
    "portal_agents": [
        {"bin": "080340019818", "orgname": "Хикмет Тревел"},
        {"bin": "100340001237", "orgname": "Тест Тревел"},
    ],
    "hotels": [],
}


def fake_lookup(self, source, column, text):
    # Как на Камкоре: поиск по началу значения в колонке.
    needle = text.casefold()
    return [v for v in KAMKOR_DICTS[source] if str(v.get(column, "")).casefold().startswith(needle)]


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        with self.Session() as db:
            seed_reference_data(db)

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.patches = [
            mock.patch.object(KamkorDictionaries, "_session", return_value=None),
            mock.patch.object(KamkorDictionaries, "lookup", fake_lookup),
            mock.patch.object(settings, "DISPATCH_AUTH_URL", "http://kamkor.test/Voucher/partner/auth"),
        ]
        for p in self.patches:
            p.start()
        self.client = TestClient(app)

    def tearDown(self):
        for p in self.patches:
            p.stop()
        app.dependency_overrides.clear()

    def test_public_reference_lists_seeded_values(self):
        data = self.client.get("/api/v1/settings/reference").json()
        self.assertIn("KC", [a["code"] for a in data["airlines"]])
        self.assertEqual(len(data["touragents"]), 4)
        self.assertNotIn("password", str(data).lower())

    def test_add_airline_checked_on_kamkor(self):
        res = self.client.post("/api/v1/settings/airlines/verify", json={"data": {"code": "zz"}})
        self.assertEqual(res.json()["status"], "not_found")
        blocked = self.client.post("/api/v1/settings/airlines", json={"data": {"code": "zz"}})
        self.assertEqual(blocked.status_code, 422)
        forced = self.client.post("/api/v1/settings/airlines", json={"data": {"code": "zz"}, "force": True})
        self.assertEqual(forced.status_code, 200)
        self.assertEqual(forced.json()["item"]["code"], "ZZ")

        dup = self.client.post("/api/v1/settings/airlines", json={"data": {"code": "kc"}})
        self.assertEqual(dup.status_code, 409)

    def test_suggestions_for_unknown_value(self):
        res = verify("airlines", {"code": "THY", "name": "THY"})
        self.assertEqual(res["status"], "not_found")
        self.assertIn("TK — THY - Turkish Airlines", res["suggestions"])

    def test_country_name_en_filled_from_kamkor(self):
        res = self.client.post("/api/v1/settings/countries", json={"data": {"name_ru": "катар "}})
        self.assertEqual(res.status_code, 409)  # уже есть в начальных данных
        res = self.client.post("/api/v1/settings/countries", json={"data": {"name_ru": "Оман"}})
        self.assertEqual(res.json()["item"]["name_en"], "Oman")
        res = self.client.post("/api/v1/settings/countries", json={"data": {"name_ru": "Турц"}})
        self.assertEqual(res.status_code, 422)
        self.assertIn("Турция", self.client.post("/api/v1/settings/countries/verify",
                                                 json={"data": {"name_ru": "Турц"}}).json()["suggestions"])

    def test_route_and_touragent_checked_in_kamkor(self):
        self.assertEqual(verify("routes", {"code": "ALA-JED"})["status"], "found")
        self.assertEqual(verify("routes", {"code": "ALA-XXX"})["status"], "not_found")
        self.assertEqual(verify("routes", {"code": "ALAJED"})["status"], "invalid")
        found = verify("touragents", {"bin": "080340019818"})
        self.assertEqual(found["extra"]["name"], "Хикмет Тревел")
        self.assertEqual(verify("touragents", {"bin": "240340000277"})["status"], "not_found")

    def test_touragent_name_from_kamkor_registry(self):
        res = self.client.post("/api/v1/settings/touragents", json={"data": {"bin": "100340001237"}})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["item"]["name"], "Тест Тревел")

        # Нет в реестре и название не введено — сохранить нечего.
        res = self.client.post("/api/v1/settings/touragents", json={"data": {"bin": "110340004560"}, "force": True})
        self.assertEqual(res.status_code, 422)
        res = self.client.post("/api/v1/settings/touragents",
                               json={"data": {"bin": "110340004560", "name": "Новый"}, "force": True})
        self.assertEqual(res.status_code, 200)

    def test_unrestricted_field_is_unchecked(self):
        res = self.client.post("/api/v1/settings/hotels", json={"data": {"name": "New Hotel"}})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["verification"]["status"], "unchecked")

    def test_kamkor_unavailable_does_not_block(self):
        with mock.patch.object(KamkorDictionaries, "lookup", side_effect=KamkorUnavailable("bad")):
            res = verify("airlines", {"code": "KC"})
        self.assertEqual(res["status"], "unchecked")

    def test_touragent_bin_validation_and_default_protection(self):
        bad = self.client.post("/api/v1/settings/touragents", json={"data": {"name": "X", "bin": "123456789012"}})
        self.assertEqual(bad.status_code, 422)

        items = self.client.get("/api/v1/settings/touragents").json()["items"]
        default = next(i for i in items if i["is_default"])
        res = self.client.delete(f"/api/v1/settings/touragents/{default['id']}")
        self.assertEqual(res.status_code, 400)

        other = next(i for i in items if not i["is_default"])
        res = self.client.patch(f"/api/v1/settings/touragents/{other['id']}", json={"data": {"is_default": True}})
        self.assertEqual(res.status_code, 200)
        with self.Session() as db:
            defaults = db.query(RefTouragent).filter(RefTouragent.is_default.is_(True)).all()
        self.assertEqual([d.id for d in defaults], [other["id"]])

    def test_soft_delete_and_restore(self):
        items = self.client.get("/api/v1/settings/hotels").json()["items"]
        hotel = items[0]
        self.assertEqual(self.client.delete(f"/api/v1/settings/hotels/{hotel['id']}").status_code, 200)
        public = self.client.get("/api/v1/settings/reference").json()["hotels"]
        self.assertNotIn(hotel["id"], [h["id"] for h in public])

        readd = self.client.post("/api/v1/settings/hotels", json={"data": {"name": hotel["name"]}})
        self.assertEqual(readd.status_code, 409)

        self.client.post(f"/api/v1/settings/hotels/{hotel['id']}/restore")
        public = self.client.get("/api/v1/settings/reference").json()["hotels"]
        self.assertIn(hotel["id"], [h["id"] for h in public])

        audit = self.client.get("/api/v1/settings/audit").json()["items"]
        self.assertEqual([a["action"] for a in audit[:2]], ["restore", "delete"])


class TouragentHelpersTests(unittest.TestCase):
    def test_bin_checksum(self):
        for value in ("080340019818", "240340000277", "230940022228", "030340005591"):
            self.assertTrue(bin_is_valid(value), value)
        self.assertFalse(bin_is_valid("080340019819"))
        self.assertFalse(bin_is_valid("12345"))

    def test_almarwa_without_credentials_fails_loudly(self):
        with mock.patch.object(settings, "DISPATCH_AGENT_LOGIN_ALMARWA", ""):
            with self.assertRaises(DispatchAuthError) as ctx:
                build_partner_payload({"dispatch_overrides": {"agent_key": "almarwa"}, "results": {"matched": []}})
        self.assertFalse(ctx.exception.retryable)


if __name__ == "__main__":
    unittest.main()
