from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_supported_health_contract():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert client.post("/health").status_code == 405


def test_greeting_and_version_identify_the_same_deployed_service():
    greeting, version = client.get("/").json(), client.get("/version").json()
    assert greeting["app"] == version["app"] == "hello-aegis"
    assert greeting["version"] == version["version"] == "1.0.0"
    assert "deployed by Aegis" in greeting["message"]


def test_echo_round_trips_json_without_executing_input():
    text = '<script>alert("hello")</script>'
    response = client.get("/api/echo", params={"message": text})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"message": text}


def test_echo_rejects_missing_empty_or_oversized_input():
    assert client.get("/api/echo").status_code == 422
    assert client.get("/api/echo", params={"message": ""}).status_code == 422
    assert client.get("/api/echo", params={"message": "x" * 121}).status_code == 422


def test_documentation_endpoints_are_not_exposed():
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
