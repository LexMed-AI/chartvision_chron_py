"""Integration tests for refactored ERE API"""
import pytest
from fastapi.testclient import TestClient
from app.api.ere_api import create_app


class TestRefactoredEREAPI:
    """Test refactored API maintains backward compatibility"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        app = create_app()
        return TestClient(app)

    def test_root_endpoint(self, client):
        """Should return API info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "ERE PDF Processing API"
        assert data["version"] == "1.0.0"

    def test_health_endpoint(self, client):
        """Should return health status"""
        response = client.get("/api/v1/ere/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_metrics_endpoint(self, client):
        """Should return metrics"""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_supported_types_endpoint(self, client):
        """Should return document types"""
        response = client.get("/api/v1/ere/supported-types")
        assert response.status_code == 200
        data = response.json()
        assert "document_types" in data
        assert len(data["document_types"]) > 0
