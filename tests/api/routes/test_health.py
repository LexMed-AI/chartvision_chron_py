"""Tests for health check routes"""
import time
from fastapi.testclient import TestClient
from app.api.routes.health import create_health_router


class TestHealthRoutes:
    """Test health check and metrics endpoints"""

    def test_health_check_returns_healthy(self):
        """Should return healthy status"""
        router = create_health_router(start_time=time.time())
        # Create minimal app for testing
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/v1/ere/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "uptime" in data
        assert "version" in data

    def test_metrics_endpoint(self):
        """Should return Prometheus metrics"""
        router = create_health_router(start_time=time.time())
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_supported_types_endpoint(self):
        """Should return document types"""
        router = create_health_router(start_time=time.time())
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/v1/ere/supported-types")
        assert response.status_code == 200
        data = response.json()
        assert "document_types" in data
        assert len(data["document_types"]) > 0
