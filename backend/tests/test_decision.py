"""
Unit tests for the decision engine and email renderer.
Pure functions — no DB or network required.
"""
import os
from unittest.mock import patch
import pytest

with patch.dict(os.environ, {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "key",
    "SUPABASE_SERVICE_KEY": "key",
    "DATABASE_URL": "sqlite:///:memory:",
    "ANTHROPIC_API_KEY": "key",
}):
    from app.services.decision import (
        make_decision,
        render_pending_email,
        _collect_reason_codes,
        _severity_score,
        REJECTION_THRESHOLD,
        REASON_CODES,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _pass(check: str, layer: int = 1) -> dict:
    return {"check": check, "status": "pass", "detail": "ok", "confidence": 1.0, "layer": layer}

def _fail(check: str, detail: str = "fail", layer: int = 1) -> dict:
    return {"check": check, "status": "fail", "detail": detail, "confidence": 1.0, "layer": layer}

def _miss(check: str) -> dict:
    return {"check": check, "status": "missing", "detail": "missing", "confidence": 1.0}

def _warn(check: str) -> dict:
    return {"check": check, "status": "warning", "detail": "warn", "confidence": 0.9}

def _low_cred() -> dict:
    return {"risk_level": "low", "flags": []}

def _high_cred() -> dict:
    return {"risk_level": "high", "flags": []}

def _cred_with_flag(severity: str = "high") -> dict:
    return {"risk_level": "low", "flags": [{"severity": severity, "flag": "test_flag"}]}


# ─── make_decision ────────────────────────────────────────────────────────────

class TestMakeDecision:
    def test_all_pass_returns_approved(self):
        checks = [_pass("cin_format"), _pass("pan_format"), _pass("doc_coi")]
        result = make_decision(checks, [], _low_cred())
        assert result["status"] == "approved"
        assert result["severity_score"] == 0

    def test_empty_checks_returns_approved(self):
        result = make_decision([], [], _low_cred())
        assert result["status"] == "approved"

    def test_high_risk_level_rejects(self):
        checks = [_pass("cin_format")]
        result = make_decision(checks, [], _high_cred())
        assert result["status"] == "rejected"
        assert result["reasons"]["risk_level"] == "high"

    def test_single_high_severity_flag_rejects(self):
        checks = [_pass("cin_format")]
        result = make_decision(checks, [], _cred_with_flag("high"))
        assert result["status"] == "rejected"
        assert len(result["reasons"]["high_severity_flags"]) == 1

    def test_medium_flag_does_not_hard_reject(self):
        checks = [_pass("cin_format")]
        result = make_decision(checks, [], _cred_with_flag("medium"))
        # medium flag alone adds 8 to score, not a hard reject
        assert result["status"] in ("approved", "pending")

    def test_missing_doc_returns_pending(self):
        checks = [_miss("doc_coi")]
        result = make_decision(checks, [], _low_cred())
        assert result["status"] == "pending"
        assert "missing_documents" in result["reasons"]
        assert "coi" in result["reasons"]["missing_documents"]

    def test_missing_field_returns_pending(self):
        checks = [_miss("field_pan_number")]
        result = make_decision(checks, [], _low_cred())
        assert result["status"] == "pending"
        assert "missing_fields" in result["reasons"]

    def test_format_failure_returns_pending(self):
        checks = [_fail("cin_format")]
        result = make_decision(checks, [], _low_cred())
        assert result["status"] == "pending"
        assert "format_failures" in result["reasons"]

    def test_consistency_failure_returns_pending(self):
        consistency = [{"check": "name_match", "status": "mismatch", "detail": "mismatch"}]
        result = make_decision([], consistency, _low_cred())
        assert result["status"] == "pending"
        assert "consistency_failures" in result["reasons"]

    def test_severity_above_threshold_rejects(self):
        # 3 missing docs × 10 = 30 ≥ threshold(25) → rejected
        checks = [_miss("doc_coi"), _miss("doc_pan_gstin"), _miss("doc_bank_letter")]
        result = make_decision(checks, [], _low_cred())
        assert result["status"] == "rejected"
        assert result["severity_score"] >= REJECTION_THRESHOLD

    def test_severity_below_threshold_pending(self):
        # 1 missing doc × 10 = 10 < threshold(25) → pending
        checks = [_miss("doc_coi")]
        result = make_decision(checks, [], _low_cred())
        assert result["status"] == "pending"
        assert result["severity_score"] < REJECTION_THRESHOLD

    def test_result_always_has_severity_score(self):
        for checks, cred in [
            ([_pass("cin_format")], _low_cred()),
            ([_miss("doc_coi")], _low_cred()),
            ([_fail("cin_format")], _high_cred()),
        ]:
            result = make_decision(checks, [], cred)
            assert "severity_score" in result
            assert isinstance(result["severity_score"], int)

    def test_reason_codes_present_in_pending(self):
        checks = [_miss("doc_coi"), _fail("cin_format")]
        result = make_decision(checks, [], _low_cred())
        assert result["status"] == "pending"
        assert "reason_codes" in result["reasons"]
        assert isinstance(result["reasons"]["reason_codes"], list)

    def test_warnings_do_not_trigger_pending(self):
        checks = [_warn("pan_checksum")]
        result = make_decision(checks, [], _low_cred())
        # A single warning has score 0 → approved (warning isn't a fail/missing)
        assert result["status"] == "approved"


# ─── _severity_score ──────────────────────────────────────────────────────────

class TestSeverityScore:
    def test_empty_inputs_zero(self):
        assert _severity_score([], [], [], [], "low", []) == 0

    def test_missing_doc_adds_10_per_doc(self):
        missing_docs = [_miss("doc_coi"), _miss("doc_pan_gstin")]
        score = _severity_score(missing_docs, [], [], [], "low", [])
        assert score == 20

    def test_format_failure_adds_8_per_failure(self):
        format_failures = [_fail("cin_format"), _fail("pan_format")]
        score = _severity_score([], format_failures, [], [], "low", [])
        assert score == 16

    def test_medium_risk_adds_15(self):
        score = _severity_score([], [], [], [], "medium", [])
        assert score == 15

    def test_high_severity_flag_adds_25(self):
        flags = [{"severity": "high", "flag": "fraud"}]
        score = _severity_score([], [], [], [], "low", flags)
        assert score == 25

    def test_medium_severity_flag_adds_8(self):
        flags = [{"severity": "medium", "flag": "warn"}]
        score = _severity_score([], [], [], [], "low", flags)
        assert score == 8

    def test_consistency_mismatch_adds_8(self):
        consistency = [{"check": "name_match", "status": "mismatch"}]
        score = _severity_score([], [], [], consistency, "low", [])
        assert score == 8

    def test_consistency_partial_match_adds_3(self):
        consistency = [{"check": "name_match", "status": "partial_match"}]
        score = _severity_score([], [], [], consistency, "low", [])
        assert score == 3

    def test_structural_fails_add_6_each(self):
        # non-doc, non-field fail in all_checks adds 6
        checks = [_fail("cin_format"), _fail("gstin_pan_match")]
        score = _severity_score([], [], checks, [], "low", [])
        assert score == 12

    def test_scores_accumulate(self):
        missing_docs = [_miss("doc_coi")]
        format_failures = [_fail("cin_format")]
        score = _severity_score(missing_docs, format_failures, [], [], "low", [])
        assert score == 10 + 8  # 10 for missing doc + 8 for format fail


# ─── _collect_reason_codes ────────────────────────────────────────────────────

class TestCollectReasonCodes:
    def test_empty_returns_empty(self):
        assert _collect_reason_codes([], []) == []

    def test_pass_checks_produce_no_codes(self):
        checks = [_pass("cin_format"), _pass("pan_format")]
        codes = _collect_reason_codes(checks, [])
        assert codes == []

    def test_missing_doc_maps_to_reason_code(self):
        codes = _collect_reason_codes([_miss("doc_coi")], [])
        assert "MISSING_COI" in codes

    def test_fail_mapped_to_known_reason_code(self):
        codes = _collect_reason_codes([_fail("cin_format")], [])
        assert "CIN_FORMAT_INVALID" in codes

    def test_missing_field_maps_to_missing_required_fields(self):
        codes = _collect_reason_codes([_miss("field_pan_number")], [])
        assert "MISSING_REQUIRED_FIELDS" in codes

    def test_deduplication(self):
        # Two different doc missing checks both mapping to MISSING_COI → only one code
        codes = _collect_reason_codes(
            [_miss("doc_coi"), _miss("doc_registration")], []
        )
        assert codes.count("MISSING_COI") == 1

    def test_order_preserved(self):
        checks = [_miss("doc_coi"), _fail("cin_format")]
        codes = _collect_reason_codes(checks, [])
        assert codes.index("MISSING_COI") < codes.index("CIN_FORMAT_INVALID")

    def test_consistency_failures_included(self):
        consistency = [{"check": "gstin_pan_match", "status": "fail", "detail": "mismatch"}]
        codes = _collect_reason_codes([], consistency)
        assert "GSTIN_PAN_MISMATCH" in codes

    def test_unknown_check_with_missing_status_uses_generic(self):
        # doc_ prefix with missing status → fallback MISSING_COI
        checks = [{"check": "doc_unknown_type", "status": "missing", "detail": "", "confidence": 1.0}]
        codes = _collect_reason_codes(checks, [])
        assert "MISSING_COI" in codes


# ─── render_pending_email ─────────────────────────────────────────────────────

class TestRenderPendingEmail:
    def test_returns_string(self):
        result = render_pending_email("Acme Ltd", [])
        assert isinstance(result, str)

    def test_contains_vendor_name(self):
        result = render_pending_email("Test Corp", [])
        assert "Test Corp" in result

    def test_contains_required_actions_section(self):
        result = render_pending_email("Acme Ltd", ["MISSING_COI"])
        assert "REQUIRED ACTIONS" in result

    def test_reason_code_message_appears_in_email(self):
        result = render_pending_email("Acme Ltd", ["MISSING_COI"])
        msg, _ = REASON_CODES["MISSING_COI"]
        assert msg in result

    def test_missing_doc_section_appears(self):
        checks = [_miss("doc_coi")]
        result = render_pending_email("Acme Ltd", ["MISSING_COI"], all_checks=checks)
        assert "MISSING DOCUMENTS" in result
        assert "Certificate of Incorporation" in result

    def test_missing_field_section_appears(self):
        checks = [_miss("field_pan_number")]
        result = render_pending_email("Acme Ltd", [], all_checks=checks)
        assert "MISSING REQUIRED FIELDS" in result
        assert "PAN Number" in result

    def test_format_fail_section_appears(self):
        checks = [_fail("cin_format", "CIN does not match format")]
        result = render_pending_email("Acme Ltd", [], all_checks=checks)
        assert "FORMAT & COMPLIANCE ISSUES" in result
        assert "CIN does not match format" in result

    def test_cross_doc_fail_section_appears(self):
        checks = [_fail("company_name_vs_coi", "Name mismatch on COI", layer=3)]
        result = render_pending_email("Acme Ltd", [], all_checks=checks)
        assert "CROSS-DOCUMENT INCONSISTENCIES" in result

    def test_warning_section_appears(self):
        checks = [_warn("pan_checksum")]
        result = render_pending_email("Acme Ltd", [], all_checks=checks)
        assert "WARNINGS" in result

    def test_what_passed_section_appears_when_passes_exist(self):
        checks = [_pass("cin_format"), _miss("doc_coi")]
        result = render_pending_email("Acme Ltd", ["MISSING_COI"], all_checks=checks)
        assert "WHAT PASSED" in result

    def test_consistency_issues_section_appears(self):
        consistency = [{
            "check": "company_name",
            "status": "mismatch",
            "detail": "Name mismatch",
            "form_value": "Acme Ltd",
            "document_value": "Acme Limited",
        }]
        result = render_pending_email("Acme Ltd", [], consistency_results=consistency)
        assert "DATA INCONSISTENCIES" in result

    def test_consistency_shows_form_vs_doc_values(self):
        consistency = [{
            "check": "company_name",
            "status": "mismatch",
            "detail": "",
            "form_value": "Acme Ltd",
            "document_value": "Acme Limited",
        }]
        result = render_pending_email("Acme Ltd", [], consistency_results=consistency)
        assert "Acme Ltd" in result
        assert "Acme Limited" in result

    def test_empty_reason_codes_shows_default_action(self):
        result = render_pending_email("Acme Ltd", [])
        assert "REQUIRED ACTIONS" in result
        # default action item
        assert "1." in result

    def test_multiple_reason_codes_numbered(self):
        codes = ["MISSING_COI", "SAVINGS_ACCOUNT", "GSTIN_PAN_MISMATCH"]
        result = render_pending_email("Acme Ltd", codes)
        assert "1." in result
        assert "2." in result
        assert "3." in result

    def test_resubmit_instructions_present(self):
        result = render_pending_email("Acme Ltd", [])
        assert "HOW TO RESUBMIT" in result

    def test_all_sections_together(self):
        checks = [
            _miss("doc_coi"),
            _miss("field_pan_number"),
            _fail("cin_format", "bad format"),
            _fail("company_name_vs_coi", "name mismatch", layer=3),
            _warn("pan_checksum"),
            _pass("gstin_format"),
        ]
        consistency = [{"check": "gstin", "status": "mismatch", "detail": "mismatch"}]
        result = render_pending_email(
            "Acme Ltd",
            ["MISSING_COI", "CIN_FORMAT_INVALID"],
            all_checks=checks,
            consistency_results=consistency,
        )
        for section in (
            "MISSING DOCUMENTS",
            "MISSING REQUIRED FIELDS",
            "FORMAT & COMPLIANCE ISSUES",
            "CROSS-DOCUMENT INCONSISTENCIES",
            "DATA INCONSISTENCIES",
            "WARNINGS",
            "WHAT PASSED",
            "REQUIRED ACTIONS",
            "HOW TO RESUBMIT",
        ):
            assert section in result, f"Missing section: {section}"
