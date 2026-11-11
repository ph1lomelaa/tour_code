import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.security import hash_password
from app.main import app
from db.models import Base, User


class AuthApiTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        with self.Session() as db:
            db.add(User(email="admin@test.kz", full_name="Админ", role="admin",
                        password_hash=hash_password("adminpass1")))
            db.commit()

        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    def _login(self, email, password):
        r = self.client.post("/api/v1/auth/login", json={"email": email, "password": password})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def _invite(self, admin, email, role):
        r = self.client.post("/api/v1/users", json={"email": email, "role": role}, headers=admin)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_api_requires_login(self):
        self.assertEqual(self.client.get("/api/v1/settings/reference").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/users").status_code, 401)
        bad = {"Authorization": "Bearer nonsense"}
        self.assertEqual(self.client.get("/api/v1/settings/reference", headers=bad).status_code, 401)

    def test_wrong_password(self):
        r = self.client.post("/api/v1/auth/login", json={"email": "admin@test.kz", "password": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_invite_flow_and_viewer_is_read_only(self):
        admin = self._login("Admin@Test.kz", "adminpass1")
        created = self._invite(admin, "viewer@test.kz", "viewer")
        token = created["invite_token"]
        self.assertEqual(created["user"]["status"], "invited")

        # Приглашённый ещё не может войти.
        r = self.client.post("/api/v1/auth/login", json={"email": "viewer@test.kz", "password": ""})
        self.assertEqual(r.status_code, 401)

        self.assertEqual(self.client.get(f"/api/v1/auth/invite/{token}").json()["email"], "viewer@test.kz")
        r = self.client.post(f"/api/v1/auth/invite/{token}", json={"full_name": "Зритель", "password": "short"})
        self.assertEqual(r.status_code, 422)
        r = self.client.post(f"/api/v1/auth/invite/{token}", json={"full_name": "Зритель", "password": "viewerpass1"})
        self.assertEqual(r.status_code, 200, r.text)
        viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # Ссылка одноразовая.
        self.assertEqual(self.client.get(f"/api/v1/auth/invite/{token}").status_code, 404)

        self.assertEqual(self.client.get("/api/v1/settings/reference", headers=viewer).status_code, 200)
        r = self.client.post("/api/v1/settings/airlines", json={"data": {"code": "XX"}}, headers=viewer)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get("/api/v1/users", headers=viewer).status_code, 403)

        # Повышаем до редактора — запись проходит дальше проверки прав.
        uid = created["user"]["id"]
        r = self.client.patch(f"/api/v1/users/{uid}", json={"role": "editor"}, headers=admin)
        self.assertEqual(r.json()["role"], "editor")
        r = self.client.post("/api/v1/settings/airlines/verify", json={"data": {}}, headers=viewer)
        self.assertNotEqual(r.status_code, 403)

        # Отключённый пользователь теряет доступ сразу.
        self.client.patch(f"/api/v1/users/{uid}", json={"is_active": False}, headers=admin)
        self.assertEqual(self.client.get("/api/v1/auth/me", headers=viewer).status_code, 401)

    def test_session_and_invite_do_not_expire(self):
        from jose import jwt
        from app.core.config import settings
        r = self.client.post("/api/v1/auth/login", json={"email": "admin@test.kz", "password": "adminpass1"})
        claims = jwt.get_unverified_claims(r.json()["access_token"])
        self.assertNotIn("exp", claims)
        admin = {"Authorization": f"Bearer {r.json()['access_token']}"}
        created = self._invite(admin, "later@test.kz", "viewer")
        with self.Session() as db:
            self.assertIsNone(db.get(User, created["user"]["id"]).invite_expires_at)

    def test_new_link_invalidates_old_one(self):
        admin = self._login("admin@test.kz", "adminpass1")
        created = self._invite(admin, "u@test.kz", "editor")
        r = self.client.post(f"/api/v1/users/{created['user']['id']}/invite", headers=admin)
        new_token = r.json()["invite_token"]
        self.assertEqual(self.client.get(f"/api/v1/auth/invite/{created['invite_token']}").status_code, 404)
        self.assertEqual(self.client.get(f"/api/v1/auth/invite/{new_token}").status_code, 200)

    def test_duplicate_email_and_self_protection(self):
        admin = self._login("admin@test.kz", "adminpass1")
        r = self.client.post("/api/v1/users", json={"email": "ADMIN@test.kz", "role": "viewer"}, headers=admin)
        self.assertEqual(r.status_code, 409)
        me = self.client.get("/api/v1/auth/me", headers=admin).json()
        self.assertEqual(self.client.patch(f"/api/v1/users/{me['id']}", json={"role": "viewer"}, headers=admin).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/v1/users/{me['id']}", headers=admin).status_code, 400)

    def test_delete_user(self):
        admin = self._login("admin@test.kz", "adminpass1")
        created = self._invite(admin, "gone@test.kz", "viewer")
        r = self.client.delete(f"/api/v1/users/{created['user']['id']}", headers=admin)
        self.assertEqual(r.status_code, 200)
        emails = [u["email"] for u in self.client.get("/api/v1/users", headers=admin).json()["items"]]
        self.assertNotIn("gone@test.kz", emails)


if __name__ == "__main__":
    unittest.main()
