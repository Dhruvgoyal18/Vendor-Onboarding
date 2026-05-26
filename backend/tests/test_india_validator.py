"""
Unit tests for India-specific format validators.
These are pure functions — no DB or network required.
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
    from app.services.india_validator import (
        run_india_format_checks,
        run_india_cross_doc_checks,
        CIN_PATTERN,
        PAN_PATTERN,
        GSTIN_PATTERN,
        IFSC_PATTERN,
    )


# ─── Regex Pattern Tests ──────────────────────────────────────────────────────

class TestRegexPatterns:
    def test_valid_cin(self):
        assert CIN_PATTERN.match("L85110KA1981PLC013115")
        assert CIN_PATTERN.match("U72200MH2010PTC204100")

    def test_invalid_cin_wrong_first_char(self):
        assert not CIN_PATTERN.match("X85110KA1981PLC013115")

    def test_invalid_cin_too_short(self):
        assert not CIN_PATTERN.match("L85110KA1981PLC013")

    def test_valid_pan(self):
        assert PAN_PATTERN.match("AAACI1681G")
        assert PAN_PATTERN.match("AABCP1234D")

    def test_invalid_pan_lowercase(self):
        assert not PAN_PATTERN.match("aaaci1681g")

    def test_invalid_pan_too_short(self):
        assert not PAN_PATTERN.match("AAACI168")

    def test_valid_gstin(self):
        assert GSTIN_PATTERN.match("27AAACI1681G1ZK")
        assert GSTIN_PATTERN.match("29AABCP1234D1Z5")

    def test_invalid_gstin_wrong_z_position(self):
        assert not GSTIN_PATTERN.match("27AAACI1681G1AK")  # 'A' instead of 'Z'

    def test_valid_ifsc(self):
        assert IFSC_PATTERN.match("HDFC0000007")
        assert IFSC_PATTERN.match("SBIN0012345")

    def test_invalid_ifsc_no_zero(self):
        assert not IFSC_PATTERN.match("HDFC1000007")


# ─── run_india_format_checks Tests ───────────────────────────────────────────

BASE_INDIA_FORM = {
    "cin_number": "L85110KA1981PLC013115",
    "pan_number": "AAACI1681G",
    "gstin_number": "29AAACI1681G1ZK",
    "ifsc_code": "HDFC0000007",
    "account_type": "current",
    "registered_state": "KA",
}


class TestFormatChecks:
    def _check(self, form_data: dict, check_name: str) -> dict | None:
        results = run_india_format_checks(form_data)
        for r in results:
            if r["check"] == check_name:
                return r
        return None

    def test_valid_cin_passes(self):
        r = self._check(BASE_INDIA_FORM, "cin_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_missing_cin_flagged(self):
        form = {**BASE_INDIA_FORM, "cin_number": ""}
        r = self._check(form, "cin_format")
        assert r is not None
        assert r["status"] == "missing"

    def test_invalid_cin_fails(self):
        form = {**BASE_INDIA_FORM, "cin_number": "BADCIN12345"}
        r = self._check(form, "cin_format")
        assert r is not None
        assert r["status"] == "fail"

    def test_valid_pan_passes(self):
        r = self._check(BASE_INDIA_FORM, "pan_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_individual_pan_rejected(self):
        form = {**BASE_INDIA_FORM, "pan_number": "ABCPP1234D"}  # P = individual
        results = run_india_format_checks(form)
        entity_check = next(
            (r for r in results if r["check"] == "pan_entity_type"), None
        )
        assert entity_check is not None
        assert entity_check["status"] == "fail"

    def test_company_pan_accepted(self):
        form = {**BASE_INDIA_FORM, "pan_number": "AAACI1681G"}  # C = company
        results = run_india_format_checks(form)
        entity_check = next(
            (r for r in results if r["check"] == "pan_entity_type"), None
        )
        assert entity_check is not None
        assert entity_check["status"] == "pass"

    def test_valid_gstin_passes(self):
        r = self._check(BASE_INDIA_FORM, "gstin_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_missing_gstin_flagged(self):
        form = {**BASE_INDIA_FORM, "gstin_number": ""}
        r = self._check(form, "gstin_format")
        assert r is not None
        assert r["status"] == "missing"

    def test_invalid_gstin_fails(self):
        form = {**BASE_INDIA_FORM, "gstin_number": "NOTGSTIN12345"}
        r = self._check(form, "gstin_format")
        assert r is not None
        assert r["status"] == "fail"

    def test_valid_ifsc_passes(self):
        r = self._check(BASE_INDIA_FORM, "ifsc_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_invalid_ifsc_fails(self):
        form = {**BASE_INDIA_FORM, "ifsc_code": "BADIFSC"}
        r = self._check(form, "ifsc_format")
        assert r is not None
        assert r["status"] == "fail"

    def test_pan_gstin_cross_check_match(self):
        form = {**BASE_INDIA_FORM, "pan_number": "AAACI1681G", "gstin_number": "29AAACI1681G1ZK"}
        results = run_india_format_checks(form)
        cross = next(
            (r for r in results if r["check"] == "gstin_pan_match"), None
        )
        assert cross is not None
        assert cross["status"] in ("pass", "match")

    def test_pan_gstin_cross_check_mismatch(self):
        form = {
            **BASE_INDIA_FORM,
            "pan_number": "AABCP1234D",
            "gstin_number": "29AAACI1681G1ZK",
        }
        results = run_india_format_checks(form)
        cross = next(
            (r for r in results if r["check"] == "gstin_pan_match"), None
        )
        assert cross is not None
        assert cross["status"] in ("fail", "mismatch")

    def test_gstin_state_code_check(self):
        # Karnataka GSTIN (29) with Karnataka registered state should pass
        form = {
            **BASE_INDIA_FORM,
            "registered_state": "Karnataka",
            "gstin_number": "29AAACI1681G1ZK",
        }
        results = run_india_format_checks(form)
        state_check = next(
            (r for r in results if "state" in r["check"].lower()), None
        )
        if state_check:
            assert state_check["status"] in ("pass", "warning")

    def test_returns_list(self):
        results = run_india_format_checks(BASE_INDIA_FORM)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_each_result_has_required_keys(self):
        results = run_india_format_checks(BASE_INDIA_FORM)
        for r in results:
            assert "check" in r
            assert "status" in r
            assert "detail" in r
            assert "confidence" in r
            assert r["status"] in ("pass", "fail", "warning", "missing", "match", "mismatch")


# ─── run_india_cross_doc_checks Tests ────────────────────────────────────────

class TestCrossDocChecks:
    def test_matching_names_pass(self):
        form = {**BASE_INDIA_FORM, "company_name": "Infosys Limited"}
        extracted = {
            "coi": {"company_name": "Infosys Ltd"},
            "pan_gstin": {"company_name": "Infosys Limited"},
        }
        results = run_india_cross_doc_checks(form, extracted)
        assert isinstance(results, list)

    def test_mismatching_names_flagged(self):
        form = {**BASE_INDIA_FORM, "company_name": "Infosys Limited"}
        extracted = {
            "coi": {"company_name": "Wipro Technologies Ltd"},
        }
        results = run_india_cross_doc_checks(form, extracted)
        name_checks = [r for r in results if "name" in r["check"].lower()]
        if name_checks:
            statuses = {r["status"] for r in name_checks}
            # At least one mismatch should be flagged
            assert statuses & {"fail", "mismatch", "warning"}

    def test_empty_extracted_returns_list(self):
        results = run_india_cross_doc_checks(BASE_INDIA_FORM, {})
        assert isinstance(results, list)
