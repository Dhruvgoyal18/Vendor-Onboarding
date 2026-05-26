"""
Integration tests for API endpoints.

Uses the test_client fixture from conftest.py (in-memory SQLite DB).
The pipeline background task is mocked to avoid calling real LLM/OCR APIs.
"""
import io
import json
import pytest
from unittest.mock import patch, MagicMock


VALID_FORM_DATA = {
    "company_name": "Acme Technologies Pvt Ltd",
    "registration_number": "",
    "country": "IN",
    "incorporation_date": "2015-01-01",
    "contact_name": "Rahul Sharma",
    "contact_email": "rahul@acme.com",
    "tax_id": "",
    "tax_id_type": "",
    "bank_account_name": "Acme Technologies Pvt Ltd",
    "account_number": "1234567890",
    "bank_name": "HDFC Bank",
    "bank_country": "IN",
    "cin_number": "L85110KA1981PLC013115",
    "pan_number": "AAACI1681G",
    "gstin_number": "29AAACI1681G1ZK",
    "ifsc_code": "HDFC0000007",
    "account_type": "current",
    "registered_state": "Karnataka",
}


def _make_pdf_file(name: str = "test.pdf") -> tuple[str, io.BytesIO, str]:
    content = b"%PDF-1.4 fake pdf content for testing"
    return (name, io.BytesIO(content), "application/pdf")


class TestHealthEndpoints:
    def test_root_health(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_health_check(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestSubmissionCreate:
    def test_create_india_submission(self, test_client):
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={
                    "registration_doc": _make_pdf_file("coi.pdf"),
                    "pan_gstin_doc": _make_pdf_file("pan_gstin.pdf"),
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "run_id" in body
        assert body["run_id"].startswith("vnd_")

    def test_create_submission_missing_required_field(self, test_client):
        # Omit a required field entirely (not just empty string)
        bad_data = {k: v for k, v in VALID_FORM_DATA.items() if k != "contact_email"}
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(bad_data)},
            )
        # Missing required field should return 4xx
        assert resp.status_code >= 400

    def test_create_submission_invalid_json(self, test_client):
        resp = test_client.post(
            "/api/submissions",
            data={"data": "not valid json"},
        )
        # Returns 400 (custom error) or 422 (pydantic validation) for bad JSON
        assert resp.status_code in (400, 422)

    def test_create_submission_bad_file_type(self, test_client):
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={
                    "registration_doc": ("script.js", io.BytesIO(b"alert(1)"), "application/javascript"),
                },
            )
        assert resp.status_code == 400


class TestSubmissionGet:
    def _create_run(self, test_client) -> str:
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={"registration_doc": _make_pdf_file()},
            )
        return resp.json()["run_id"]

    def test_get_existing_submission(self, test_client):
        run_id = self._create_run(test_client)
        resp = test_client.get(f"/api/submissions/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["company_name"] == VALID_FORM_DATA["company_name"]

    def test_get_nonexistent_submission(self, test_client):
        resp = test_client.get("/api/submissions/vnd_doesnotexist123")
        assert resp.status_code == 404

    def test_get_versions_first_submission(self, test_client):
        run_id = self._create_run(test_client)
        resp = test_client.get(f"/api/submissions/{run_id}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert isinstance(versions, list)
        assert len(versions) >= 1
        assert versions[0]["run_id"] == run_id
        assert versions[0]["version_number"] == 1

    def test_get_stages(self, test_client):
        run_id = self._create_run(test_client)
        resp = test_client.get(f"/api/submissions/{run_id}/stages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert "stages" in data


class TestDashboard:
    def test_dashboard_stats(self, test_client):
        resp = test_client.get("/api/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "approved" in data
        assert "pending" in data
        assert "rejected" in data
        assert "processing" in data

    def test_dashboard_history_default(self, test_client):
        resp = test_client.get("/api/dashboard/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "pages" in data

    def test_dashboard_history_with_status_filter(self, test_client):
        resp = test_client.get("/api/dashboard/history?status=processing")
        assert resp.status_code == 200
        data = resp.json()
        for vendor in data["items"]:
            assert vendor["status"] == "processing"

    def test_dashboard_history_with_search(self, test_client):
        resp = test_client.get("/api/dashboard/history?search=Acme")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)

    def test_dashboard_history_pagination(self, test_client):
        resp = test_client.get("/api/dashboard/history?page=1&page_size=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 5
