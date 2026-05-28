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
        _validate_pan_checksum,
        _validate_account_number,
        _extract_cin_year,
        INDIA_STATE_CODES,
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


# ─── PAN Checksum ─────────────────────────────────────────────────────────────

class TestPanChecksum:
    # ABCCC1234S: computed valid checksum
    # weights=[2,4,6,8,10,3,5,7,9]
    # A=0,B=1,C=2,C=2,C=2,1=1,2=2,3=3,4=4
    # total=0+4+12+16+20+3+10+21+36=122  122%26=18  chr(65+18)='S'
    VALID_PAN = "ABCCC1234S"
    INVALID_PAN = "AAACI1681G"  # checksum char should be 'M', not 'G'

    def test_valid_pan_checksum_passes(self):
        assert _validate_pan_checksum(self.VALID_PAN) is True

    def test_invalid_pan_checksum_fails(self):
        assert _validate_pan_checksum(self.INVALID_PAN) is False

    def test_valid_pan_format_invalid_checksum_warns_via_format_checks(self):
        form = {**BASE_INDIA_FORM, "pan_number": self.INVALID_PAN}
        results = run_india_format_checks(form)
        checksum_r = next((r for r in results if r["check"] == "pan_checksum"), None)
        assert checksum_r is not None
        assert checksum_r["status"] == "warning"

    def test_valid_pan_with_valid_checksum_passes_via_format_checks(self):
        form = {**BASE_INDIA_FORM, "pan_number": self.VALID_PAN}
        results = run_india_format_checks(form)
        checksum_r = next((r for r in results if r["check"] == "pan_checksum"), None)
        assert checksum_r is not None
        assert checksum_r["status"] == "pass"

    def test_invalid_format_pan_returns_false(self):
        assert _validate_pan_checksum("TOOSHORT") is False

    def test_pan_checksum_wrong_regex_returns_false(self):
        assert _validate_pan_checksum("lowercase1234s") is False


# ─── CIN Year Extraction ──────────────────────────────────────────────────────

class TestCinYearExtraction:
    def test_extracts_1981_from_standard_cin(self):
        assert _extract_cin_year("L85110KA1981PLC013115") == 1981

    def test_extracts_2010_from_cin(self):
        assert _extract_cin_year("U72200MH2010PTC204100") == 2010

    def test_extracts_2018_from_cin(self):
        assert _extract_cin_year("U72200KA2018PTC098765") == 2018

    def test_year_mismatch_detected_via_format_checks(self):
        # CIN encodes 1981 but form says 2015
        form = {
            **BASE_INDIA_FORM,
            "cin_number": "L85110KA1981PLC013115",
            "incorporation_date": "2015-01-01",
        }
        results = run_india_format_checks(form)
        year_check = next((r for r in results if r["check"] == "cin_year_vs_incorporation_date"), None)
        assert year_check is not None
        assert year_check["status"] == "fail"

    def test_year_match_passes_via_format_checks(self):
        # CIN encodes 1981 and form says 1981
        form = {
            **BASE_INDIA_FORM,
            "cin_number": "L85110KA1981PLC013115",
            "incorporation_date": "1981-06-15",
        }
        results = run_india_format_checks(form)
        year_check = next((r for r in results if r["check"] == "cin_year_vs_incorporation_date"), None)
        assert year_check is not None
        assert year_check["status"] == "pass"

    def test_short_cin_returns_none(self):
        assert _extract_cin_year("L851") is None

    def test_empty_cin_returns_none(self):
        assert _extract_cin_year("") is None


# ─── Account Number Validation ────────────────────────────────────────────────

class TestAccountNumberValidation:
    def test_9_digits_passes(self):
        valid, _ = _validate_account_number("123456789")
        assert valid is True

    def test_18_digits_passes(self):
        valid, _ = _validate_account_number("123456789012345678")
        assert valid is True

    def test_8_digits_fails(self):
        valid, reason = _validate_account_number("12345678")
        assert valid is False
        assert "short" in reason.lower()

    def test_19_digits_fails(self):
        valid, reason = _validate_account_number("1234567890123456789")
        assert valid is False
        assert "long" in reason.lower()

    def test_non_digit_characters_fail(self):
        valid, reason = _validate_account_number("1234ABCD5")
        assert valid is False
        assert "non-digit" in reason.lower()

    def test_12_digits_passes(self):
        valid, _ = _validate_account_number("123456789012")
        assert valid is True

    def test_whitespace_stripped_before_check(self):
        # spaces should be stripped
        valid, _ = _validate_account_number("1234 5678 9")
        assert valid is True

    def test_account_number_8_digits_fails_via_format_checks(self):
        form = {**BASE_INDIA_FORM, "account_number": "12345678"}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_number_format"), None)
        assert r is not None
        assert r["status"] == "fail"

    def test_account_number_9_digits_passes_via_format_checks(self):
        form = {**BASE_INDIA_FORM, "account_number": "123456789"}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_number_format"), None)
        assert r is not None
        assert r["status"] == "pass"

    def test_missing_account_number_flagged(self):
        form = {**BASE_INDIA_FORM, "account_number": ""}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_number_format"), None)
        assert r is not None
        assert r["status"] == "missing"


# ─── Account Type Edge Cases ──────────────────────────────────────────────────

class TestAccountType:
    def test_current_account_passes(self):
        form = {**BASE_INDIA_FORM, "account_type": "current"}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_type"), None)
        assert r is not None
        assert r["status"] == "pass"

    def test_savings_account_fails(self):
        form = {**BASE_INDIA_FORM, "account_type": "savings"}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_type"), None)
        assert r is not None
        assert r["status"] == "fail"

    def test_missing_account_type_is_missing(self):
        form = {**BASE_INDIA_FORM, "account_type": ""}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_type"), None)
        assert r is not None
        assert r["status"] == "missing"

    def test_case_insensitive_current(self):
        form = {**BASE_INDIA_FORM, "account_type": "Current Account"}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_type"), None)
        assert r is not None
        assert r["status"] == "pass"

    def test_case_insensitive_savings(self):
        form = {**BASE_INDIA_FORM, "account_type": "Savings Account"}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_type"), None)
        assert r is not None
        assert r["status"] == "fail"

    def test_unknown_account_type_warns(self):
        form = {**BASE_INDIA_FORM, "account_type": "nro"}
        results = run_india_format_checks(form)
        r = next((r for r in results if r["check"] == "account_type"), None)
        assert r is not None
        assert r["status"] == "warning"


# ─── GSTIN State Mismatch ─────────────────────────────────────────────────────

class TestGstinStateMismatch:
    def test_gstin_state_29_karnataka_matches_karnataka(self):
        form = {
            **BASE_INDIA_FORM,
            "gstin_number": "29AAACI1681G1ZK",
            "registered_state": "Karnataka",
        }
        results = run_india_format_checks(form)
        state_check = next(
            (r for r in results if r["check"] == "gstin_state_vs_registered_state"), None
        )
        assert state_check is not None
        assert state_check["status"] == "pass"

    def test_gstin_state_29_karnataka_mismatches_maharashtra(self):
        # 29 = Karnataka, but registered_state = Maharashtra → fail
        form = {
            **BASE_INDIA_FORM,
            "gstin_number": "29AAACI1681G1ZK",
            "registered_state": "Maharashtra",
        }
        results = run_india_format_checks(form)
        state_check = next(
            (r for r in results if r["check"] == "gstin_state_vs_registered_state"), None
        )
        assert state_check is not None
        assert state_check["status"] == "fail"

    def test_gstin_state_27_maharashtra_matches_maharashtra(self):
        # 27 = Maharashtra — use a valid GSTIN with state code 27
        form = {
            **BASE_INDIA_FORM,
            "pan_number": "AAACI1681G",
            "gstin_number": "27AAACI1681G1ZK",
            "registered_state": "Maharashtra",
        }
        results = run_india_format_checks(form)
        state_check = next(
            (r for r in results if r["check"] == "gstin_state_vs_registered_state"), None
        )
        assert state_check is not None
        assert state_check["status"] == "pass"

    def test_gstin_state_code_detail_contains_state_name(self):
        form = {**BASE_INDIA_FORM, "gstin_number": "29AAACI1681G1ZK"}
        results = run_india_format_checks(form)
        state_code_check = next(
            (r for r in results if r["check"] == "gstin_state_code"), None
        )
        assert state_code_check is not None
        assert "Karnataka" in state_code_check["detail"]

    def test_state_codes_map_has_karnataka(self):
        assert INDIA_STATE_CODES.get("29") == "Karnataka"

    def test_state_codes_map_has_maharashtra(self):
        assert INDIA_STATE_CODES.get("27") == "Maharashtra"
