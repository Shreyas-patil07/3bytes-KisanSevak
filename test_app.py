"""
test_app.py — Basic tests for KisanSevak security & infrastructure fixes.

Run:  python -m pytest test_app.py -v
"""

import json
import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"
    with app.test_client() as c:
        yield c


def _login(client):
    """Helper: create account and login, returns session-ready client."""
    client.post("/auth/signup", json={
        "name": "Test Farmer",
        "email": "test@test.com",
        "password": "password123"
    })
    return client


# -------------------------------------------------------
# 6. Lat/Lon range validation
# -------------------------------------------------------
class TestLatLonValidation:
    def test_valid_coords(self, client):
        _login(client)
        resp = client.post("/chat/location", json={"lat": 19.07, "lon": 72.87})
        assert resp.status_code == 200

    def test_lat_out_of_range(self, client):
        _login(client)
        resp = client.post("/chat/location", json={"lat": 95.0, "lon": 72.87})
        assert resp.status_code == 400
        assert "out of range" in resp.get_json()["error"].lower()

    def test_lon_out_of_range(self, client):
        _login(client)
        resp = client.post("/chat/location", json={"lat": 19.07, "lon": 200.0})
        assert resp.status_code == 400
        assert "out of range" in resp.get_json()["error"].lower()

    def test_non_numeric(self, client):
        _login(client)
        resp = client.post("/chat/location", json={"lat": "abc", "lon": 72.87})
        assert resp.status_code == 400


# -------------------------------------------------------
# 4. Session prerequisite validation
# -------------------------------------------------------
class TestPrerequisiteValidation:
    def test_ask_category_without_location(self, client):
        _login(client)
        resp = client.post("/chat", json={"stage": "ASK_CATEGORY", "message": "seeds"})
        assert resp.status_code == 400
        assert "prerequisites" in resp.get_json()["error"].lower()

    def test_ask_product_without_category(self, client):
        _login(client)
        # Set location but not category
        client.post("/chat/location", json={"lat": 19.07, "lon": 72.87})
        resp = client.post("/chat", json={"stage": "ASK_PRODUCT", "message": "wheat seeds"})
        assert resp.status_code == 400
        assert "category" in resp.get_json()["error"].lower()

    def test_ask_preference_without_product(self, client):
        _login(client)
        client.post("/chat/location", json={"lat": 19.07, "lon": 72.87})
        client.post("/chat", json={"stage": "ASK_CATEGORY", "message": "seeds"})
        resp = client.post("/chat", json={"stage": "ASK_PREFERENCE", "message": "quality"})
        assert resp.status_code == 400
        assert "selected_product" in resp.get_json()["error"].lower()


# -------------------------------------------------------
# 5. Gemini error logging (verify fallback reply still works)
# -------------------------------------------------------
class TestGeminiFallback:
    def test_full_flow_without_gemini(self, client):
        """Complete happy path — model is None so fallback reply is used."""
        _login(client)
        client.post("/chat/location", json={"lat": 19.07, "lon": 72.87})
        client.post("/chat", json={"stage": "ASK_CATEGORY", "message": "seeds"})
        client.post("/chat", json={"stage": "ASK_PRODUCT", "message": "wheat seeds"})
        resp = client.post("/chat", json={"stage": "ASK_PREFERENCE", "message": "quality"})
        data = resp.get_json()
        assert resp.status_code == 200
        assert "stage" in data


# -------------------------------------------------------
# 7. Rate limiting
# -------------------------------------------------------
class TestRateLimiting:
    def test_login_rate_limit(self, client):
        """6th request within a minute should be rate-limited."""
        for i in range(5):
            client.post("/auth/login", json={
                "email": f"brute{i}@test.com",
                "password": "wrong"
            })
        resp = client.post("/auth/login", json={
            "email": "brute@test.com",
            "password": "wrong"
        })
        assert resp.status_code == 429

    def test_signup_rate_limit(self, client):
        for i in range(5):
            client.post("/auth/signup", json={
                "name": f"User {i}",
                "email": f"spam{i}@test.com",
                "password": "password123"
            })
        resp = client.post("/auth/signup", json={
            "name": "User X",
            "email": "spamX@test.com",
            "password": "password123"
        })
        assert resp.status_code == 429


# -------------------------------------------------------
# 3. Location text handler (city lookup)
# -------------------------------------------------------
class TestLocationText:
    def test_city_name_mumbai(self, client):
        _login(client)
        resp = client.post("/chat", json={"stage": "ASK_LOCATION_TEXT", "message": "mumbai"})
        data = resp.get_json()
        assert data["stage"] == "ASK_CATEGORY"
        assert "Location set" in data["reply"]

    def test_unknown_city(self, client):
        _login(client)
        resp = client.post("/chat", json={"stage": "ASK_LOCATION_TEXT", "message": "xyzville"})
        data = resp.get_json()
        assert data["stage"] == "ASK_LOCATION_TEXT"
        assert "couldn't find" in data["reply"].lower()

    def test_empty_message(self, client):
        _login(client)
        resp = client.post("/chat", json={"stage": "ASK_LOCATION_TEXT", "message": ""})
        data = resp.get_json()
        assert data["stage"] == "ASK_LOCATION_TEXT"
