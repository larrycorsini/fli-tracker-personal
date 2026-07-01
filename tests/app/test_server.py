"""Tests for FastAPI tracker routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


def test_index_serves_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Travel Planner" in response.text or "Flight" in response.text


def test_presets_endpoint():
    response = client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert isinstance(data["presets"], list)
    assert any(p.get("id") == "fifa-dfw-2026-slc-pvu" for p in data["presets"])


def test_booking_options_requires_params():
    response = client.get("/api/booking-options")
    assert response.status_code == 422


def test_tracker_list():
    response = client.get("/api/tracker/list")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "flights" in data
