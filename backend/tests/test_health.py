"""Automated tests for health endpoint and CORS configuration."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)
settings = get_settings()


def test_health_endpoint_status_and_schema():
    """Verify that GET /health returns HTTP 200 and the required structured JSON."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "application_name" in data
    assert "api_version" in data

    assert data["status"] == "healthy"
    assert data["application_name"] == settings.APP_NAME
    assert data["api_version"] == settings.APP_VERSION
    assert data["environment"] == settings.ENVIRONMENT


def test_api_v1_health_endpoint():
    """Verify that GET /api/v1/health returns HTTP 200 with matching schema."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["application_name"] == settings.APP_NAME
    assert data["api_version"] == settings.APP_VERSION


def test_root_endpoint():
    """Verify that GET / returns status 200 with service welcome info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "health_url" in data


def test_cors_headers_for_vite_origin():
    """Verify that requests from http://localhost:5173 receive appropriate CORS headers."""
    response = client.get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_not_found_structured_error():
    """Verify that requesting an unmapped route returns a structured 404 response."""
    response = client.get("/non-existent-route")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data

