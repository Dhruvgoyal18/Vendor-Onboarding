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


def _pdf(name: str = "test.pdf") -> tuple:
    return (name, io.BytesIO(b"%PDF-1.4 fake pdf content"), "application/pdf")


def _create_run(test_client, form_data=None) -> str:
    data = form_data or VALID_FORM_DATA
    with patch("app.api.submissions.BackgroundTasks.add_task"):
        resp = test_client.post(
            "/api/submissions",
            data={"data": json.dumps(data)},
            files={"registration_doc": _pdf()},
        )
    assert resp.status_code == 200
    return resp.json()["run_id"]


# ─── Health ───────────────────────────────────────────────────────────────────

class TestHealthEndpoints:
    def test_root_health(self, test_client):
        resp = test_client.get("/")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_health_check(self, test_client):
        resp = test_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ─── Submission create ────────────────────────────────────────────────────────

class TestSubmissionCreate:
    def test_create_india_submission(self, test_client):
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={
                    "registration_doc": _pdf("coi.pdf"),
                    "pan_gstin_doc": _pdf("pan_gstin.pdf"),
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "run_id" in body
        assert body["run_id"].startswith("vnd_")

    def test_create_submission_missing_required_field(self, test_client):
        bad_data = {k: v for k, v in VALID_FORM_DATA.items() if k != "contact_email"}
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(bad_data)},
            )
        assert resp.status_code >= 400

    def test_create_submission_invalid_json(self, test_client):
        resp = test_client.post("/api/submissions", data={"data": "not valid json"})
        assert resp.status_code in (400, 422)

    def test_create_submission_bad_file_type(self, test_client):
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={"registration_doc": ("script.js", io.BytesIO(b"alert(1)"), "application/javascript")},
            )
        assert resp.status_code == 400

    def test_run_id_format(self, test_client):
        run_id = _create_run(test_client)
        # vnd_YYYYMMDD_xxxxxxxx
        parts = run_id.split("_")
        assert len(parts) == 3
        assert parts[0] == "vnd"
        assert len(parts[1]) == 8   # date
        assert len(parts[2]) == 8   # uuid suffix

    def test_non_india_submission_accepted(self, test_client):
        form = {**VALID_FORM_DATA, "country": "GB", "cin_number": "", "pan_number": "",
                "gstin_number": "", "ifsc_code": "", "account_type": "", "registered_state": ""}
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(form)},
                files={"registration_doc": _pdf()},
            )
        assert resp.status_code == 200
        assert resp.json()["run_id"].startswith("vnd_")

    def test_oversized_file_rejected(self, test_client):
        big_content = b"x" * (11 * 1024 * 1024)  # 11 MB > 10 MB limit
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={"registration_doc": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
            )
        assert resp.status_code == 400

    def test_image_file_accepted(self, test_client):
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={"registration_doc": ("scan.jpg", io.BytesIO(b"\xff\xd8\xff fake jpeg"), "image/jpeg")},
            )
        assert resp.status_code == 200


# ─── Submission get ───────────────────────────────────────────────────────────

class TestSubmissionGet:
    def test_get_existing_submission(self, test_client):
        run_id = _create_run(test_client)
        resp = test_client.get(f"/api/submissions/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["company_name"] == VALID_FORM_DATA["company_name"]

    def test_get_nonexistent_submission(self, test_client):
        resp = test_client.get("/api/submissions/vnd_doesnotexist123")
        assert resp.status_code == 404

    def test_response_includes_all_expected_fields(self, test_client):
        run_id = _create_run(test_client)
        data = test_client.get(f"/api/submissions/{run_id}").json()
        for field in ("run_id", "company_name", "status", "documents",
                      "validation_results", "pipeline_stages", "email_logs"):
            assert field in data, f"Missing field: {field}"

    def test_get_versions_first_submission(self, test_client):
        run_id = _create_run(test_client)
        resp = test_client.get(f"/api/submissions/{run_id}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert isinstance(versions, list)
        assert len(versions) >= 1
        assert versions[0]["run_id"] == run_id
        assert versions[0]["version_number"] == 1

    def test_get_stages_structure(self, test_client):
        run_id = _create_run(test_client)
        resp = test_client.get(f"/api/submissions/{run_id}/stages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert "stages" in data
        assert isinstance(data["stages"], list)

    def test_all_pipeline_stages_initialized(self, test_client):
        run_id = _create_run(test_client)
        stages = test_client.get(f"/api/submissions/{run_id}/stages").json()["stages"]
        stage_names = {s["stage"] for s in stages}
        for expected in ("intake", "extract_fields", "format_check", "extract_docs",
                         "check_completeness", "decide", "done"):
            assert expected in stage_names, f"Missing stage: {expected}"

    def test_documents_stored_on_submission(self, test_client):
        run_id = _create_run(test_client)
        data = test_client.get(f"/api/submissions/{run_id}").json()
        assert len(data["documents"]) >= 1
        doc = data["documents"][0]
        assert "document_type" in doc
        assert "original_filename" in doc
        assert "ocr_status" in doc


# ─── Resubmission ─────────────────────────────────────────────────────────────

class TestResubmission:
    def test_resubmit_creates_version_2(self, test_client):
        run_id = _create_run(test_client)
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                f"/api/submissions/{run_id}/resubmit",
                data={
                    "data": json.dumps({**VALID_FORM_DATA, "company_name": "Acme v2"}),
                    "resubmission_notes": "Fixed CIN mismatch",
                },
                files={"registration_doc": _pdf("coi_v2.pdf")},
            )
        assert resp.status_code == 200
        new_run_id = resp.json()["run_id"]
        assert new_run_id != run_id
        assert "v2" in resp.json()["message"]

    def test_resubmit_version_history(self, test_client):
        run_id = _create_run(test_client)
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                f"/api/submissions/{run_id}/resubmit",
                data={"data": json.dumps(VALID_FORM_DATA)},
                files={"registration_doc": _pdf()},
            )
        new_run_id = resp.json()["run_id"]
        versions = test_client.get(f"/api/submissions/{new_run_id}/versions").json()
        version_numbers = [v["version_number"] for v in versions]
        assert 1 in version_numbers
        assert 2 in version_numbers

    def test_resubmit_nonexistent_run_404(self, test_client):
        with patch("app.api.submissions.BackgroundTasks.add_task"):
            resp = test_client.post(
                "/api/submissions/vnd_doesnotexist/resubmit",
                data={"data": json.dumps(VALID_FORM_DATA)},
            )
        assert resp.status_code == 404


# ─── Retry ────────────────────────────────────────────────────────────────────

class TestRetry:
    def test_retry_nonexistent_run(self, test_client):
        resp = test_client.post("/api/submissions/vnd_nope/retry")
        assert resp.status_code == 404

    def test_retry_processing_run_returns_409(self, test_client):
        run_id = _create_run(test_client)
        # Fresh submission is in "processing" state
        resp = test_client.post(f"/api/submissions/{run_id}/retry")
        assert resp.status_code == 409


# ─── Admin override ───────────────────────────────────────────────────────────

class TestAdminOverride:
    def _auth(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}

    def test_override_requires_auth(self, test_client):
        run_id = _create_run(test_client)
        resp = test_client.post(
            f"/api/submissions/{run_id}/override",
            json={"decision": "approved", "reason": "Manual review passed"},
        )
        assert resp.status_code == 401

    def test_override_processing_run_rejected(self, test_client, admin_token):
        run_id = _create_run(test_client)
        resp = test_client.post(
            f"/api/submissions/{run_id}/override",
            json={"decision": "approved", "reason": "Test"},
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 409

    def test_override_invalid_decision_rejected(self, test_client, admin_token):
        run_id = _create_run(test_client)
        resp = test_client.post(
            f"/api/submissions/{run_id}/override",
            json={"decision": "maybe", "reason": "Hm"},
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 400

    def test_override_empty_reason_rejected(self, test_client, admin_token):
        run_id = _create_run(test_client)
        resp = test_client.post(
            f"/api/submissions/{run_id}/override",
            json={"decision": "approved", "reason": "   "},
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 400

    def test_override_nonexistent_run(self, test_client, admin_token):
        resp = test_client.post(
            "/api/submissions/vnd_ghost/override",
            json={"decision": "approved", "reason": "Test"},
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 404


# ─── Dashboard ────────────────────────────────────────────────────────────────

class TestDashboard:
    def _auth(self, admin_token):
        return {"Authorization": f"Bearer {admin_token}"}

    def test_dashboard_requires_auth(self, test_client):
        assert test_client.get("/api/dashboard/stats").status_code == 401
        assert test_client.get("/api/dashboard/history").status_code == 401

    def test_dashboard_stats(self, test_client, admin_token):
        resp = test_client.get("/api/dashboard/stats", headers=self._auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        for field in ("total", "approved", "pending", "rejected", "processing"):
            assert field in data

    def test_dashboard_stats_counts_are_non_negative(self, test_client, admin_token):
        data = test_client.get("/api/dashboard/stats", headers=self._auth(admin_token)).json()
        for key in ("total", "approved", "pending", "rejected", "processing", "error"):
            assert data[key] >= 0

    def test_dashboard_history_default(self, test_client, admin_token):
        resp = test_client.get("/api/dashboard/history", headers=self._auth(admin_token))
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "pages" in data

    def test_dashboard_history_with_status_filter(self, test_client, admin_token):
        resp = test_client.get(
            "/api/dashboard/history?status=processing",
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 200
        for vendor in resp.json()["items"]:
            assert vendor["status"] == "processing"

    def test_dashboard_history_with_search(self, test_client, admin_token):
        _create_run(test_client)
        resp = test_client.get(
            "/api/dashboard/history?search=Acme",
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["items"], list)
        for item in data["items"]:
            assert "acme" in item["company_name"].lower()

    def test_dashboard_history_pagination(self, test_client, admin_token):
        resp = test_client.get(
            "/api/dashboard/history?page=1&page_size=5",
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 5

    def test_dashboard_history_invalid_status_ignored(self, test_client, admin_token):
        resp = test_client.get(
            "/api/dashboard/history?status=nonsense",
            headers=self._auth(admin_token),
        )
        assert resp.status_code == 200
