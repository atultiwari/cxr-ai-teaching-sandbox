from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def test_samples_listed_with_licences():
    body = client.get("/api/samples").json()
    assert len(body["samples"]) == 6
    assert all(s["license"] and s["source_page"].startswith("https://commons.wikimedia.org") for s in body["samples"])
    assert "not a clinical device" in body["disclaimer"]


def test_analyse_sample():
    body = client.post("/api/analyse", data={"sample_id": "ett_right_mainstem_ap"}).json()
    assert body["has_tube_position_output"] is False
    assert body["overlay"].startswith("data:image/png;base64,")
    assert "not a clinical device" in body["disclaimer"]


def test_unknown_sample_and_path_traversal_rejected():
    assert client.post("/api/analyse", data={"sample_id": "../app"}).status_code == 404


def test_bad_upload_type_rejected():
    r = client.post("/api/analyse", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415


def test_corrupt_image_rejected():
    r = client.post("/api/analyse", files={"file": ("x.png", b"\x89PNGjunk", "image/png")})
    assert r.status_code == 422


def test_unknown_cam_label_rejected():
    r = client.post("/api/analyse", data={"sample_id": "normal_pa", "cam_label": "Tube"})
    assert r.status_code == 400


def test_security_headers_present():
    r = client.get("/")
    assert "default-src 'self'" in r.headers["content-security-policy"]
