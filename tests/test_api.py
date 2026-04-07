import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════
# Health & Documentation
# ═══════════════════════════════════════════════════════════════

class TestHealthAndDocs:
    def test_health_check_returns_ok(self):
        """Service health endpoint should return 200 with status ok."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_openapi_docs_served(self):
        """Swagger UI should be accessible at /docs."""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_docs_served(self):
        """ReDoc should be accessible at /redoc."""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_request_id_header_present(self):
        """Every response should include an X-Request-ID tracing header."""
        response = client.get("/")
        assert "x-request-id" in response.headers


# ═══════════════════════════════════════════════════════════════
# Input Validation (Pydantic)
# ═══════════════════════════════════════════════════════════════

class TestInputValidation:
    def test_rejects_missing_text_field(self):
        """POST /submit should return 422 when 'text' key is missing."""
        response = client.post("/submit", json={"invalid_field": "no text here"})
        assert response.status_code == 422

    def test_rejects_empty_text(self):
        """POST /submit should reject empty strings."""
        response = client.post("/submit", json={"text": ""})
        assert response.status_code == 422

    def test_rejects_oversized_text(self):
        """POST /submit should reject text exceeding 64KB."""
        payload = {"text": "A" * (1024 * 65)}
        response = client.post("/submit", json=payload)
        assert response.status_code == 422

    def test_rejects_wrong_content_type(self):
        """POST /submit should reject non-JSON payloads."""
        response = client.post("/submit", content="plain text", headers={"content-type": "text/plain"})
        assert response.status_code == 422


# ═══════════════════════════════════════════════════════════════
# Submission Endpoint (Happy Path)
# ═══════════════════════════════════════════════════════════════

class TestSubmissionEndpoint:
    @patch("app.api.routes.celery_app")
    def test_submit_returns_201_with_id(self, mock_celery):
        """Valid submission should return 201 with a submission_id and status=queued."""
        mock_celery.send_task = MagicMock()

        response = client.post("/submit", json={"text": "Analyze this for sentiment."})
        assert response.status_code == 201

        data = response.json()
        assert "submission_id" in data
        assert data["status"] == "queued"

    @patch("app.api.routes.celery_app")
    def test_submit_dispatches_celery_task(self, mock_celery):
        """Submitting should trigger a Celery task dispatch."""
        mock_celery.send_task = MagicMock()

        client.post("/submit", json={"text": "Test dispatch"})
        mock_celery.send_task.assert_called_once()


# ═══════════════════════════════════════════════════════════════
# Status Retrieval
# ═══════════════════════════════════════════════════════════════

class TestStatusEndpoint:
    def test_nonexistent_submission_returns_404(self):
        """GET with a random UUID should return 404."""
        response = client.get("/submissions/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_invalid_uuid_returns_422(self):
        """GET with a non-UUID string should return 422."""
        response = client.get("/submissions/not-a-uuid")
        assert response.status_code == 422

    def test_list_submissions_returns_list(self):
        """GET /submissions should return a list."""
        response = client.get("/submissions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_submissions_pagination(self):
        """Pagination parameters should be accepted."""
        response = client.get("/submissions?skip=0&limit=5")
        assert response.status_code == 200

    def test_list_submissions_status_filter(self):
        """Status filter should be accepted."""
        response = client.get("/submissions?status=completed")
        assert response.status_code == 200
