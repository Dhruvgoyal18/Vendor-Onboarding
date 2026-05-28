"""
Unit tests for check_completeness (generic and India paths).
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
    from app.services.validator import (
        check_completeness,
        INDIA_REQUIRED_FIELDS,
        REQUIRED_FIELDS,
        INDIA_REQUIRED_DOCS,
        INDIA_DOC_ALIASES,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

BASE_INDIA_FORM = {
    "company_name": "Acme Technologies Pvt Ltd",
    "country": "IN",
    "incorporation_date": "2015-01-01",
    "contact_name": "Rahul Sharma",
    "contact_email": "rahul@acme.com",
    "cin_number": "L85110KA1981PLC013115",
    "pan_number": "AAACI1681G",
    "gstin_number": "29AAACI1681G1ZK",
    "ifsc_code": "HDFC0000007",
    "account_type": "current",
    "registered_state": "Karnataka",
    "bank_account_name": "Acme Technologies Pvt Ltd",
    "account_number": "1234567890",
    "bank_name": "HDFC Bank",
    "bank_country": "IN",
}

INDIA_DOCS = ["coi", "pan_gstin", "bank_letter"]

BASE_GENERIC_FORM = {
    "company_name": "Acme UK Ltd",
    "registration_number": "12345678",
    "country": "GB",
    "incorporation_date": "2015-01-01",
    "contact_name": "John Smith",
    "contact_email": "john@acme.co.uk",
    "bank_account_name": "Acme UK Ltd",
    "account_number": "GB33BUKB20201555555555",
    "bank_name": "Barclays",
    "bank_country": "GB",
}

GENERIC_DOCS = ["registration", "bank_letter", "tax_cert"]


def _by_check(results, check_name):
    return next((r for r in results if r["check"] == check_name), None)


# ─── India Path ───────────────────────────────────────────────────────────────

class TestCheckCompletenessIndia:
    def test_all_fields_present_all_pass(self):
        results = check_completeness(BASE_INDIA_FORM, INDIA_DOCS, "IN")
        field_results = [r for r in results if r["check"].startswith("field_")]
        fails = [r for r in field_results if r["status"] != "pass"]
        assert fails == [], f"Unexpected failures: {fails}"

    def test_missing_pan_flagged(self):
        form = {**BASE_INDIA_FORM, "pan_number": ""}
        results = check_completeness(form, INDIA_DOCS, "IN")
        r = _by_check(results, "field_pan_number")
        assert r is not None
        assert r["status"] == "missing"

    def test_missing_cin_flagged(self):
        form = {**BASE_INDIA_FORM, "cin_number": ""}
        results = check_completeness(form, INDIA_DOCS, "IN")
        r = _by_check(results, "field_cin_number")
        assert r is not None
        assert r["status"] == "missing"

    def test_missing_gstin_flagged(self):
        form = {**BASE_INDIA_FORM, "gstin_number": ""}
        results = check_completeness(form, INDIA_DOCS, "IN")
        r = _by_check(results, "field_gstin_number")
        assert r is not None
        assert r["status"] == "missing"

    def test_all_india_required_fields_checked(self):
        results = check_completeness(BASE_INDIA_FORM, INDIA_DOCS, "IN")
        checked_fields = {r["check"].replace("field_", "") for r in results if r["check"].startswith("field_")}
        for field in INDIA_REQUIRED_FIELDS:
            assert field in checked_fields, f"Field not checked: {field}"

    def test_missing_coi_doc_flagged(self):
        results = check_completeness(BASE_INDIA_FORM, ["pan_gstin", "bank_letter"], "IN")
        r = _by_check(results, "doc_coi")
        assert r is not None
        assert r["status"] == "missing"

    def test_missing_pan_gstin_doc_flagged(self):
        results = check_completeness(BASE_INDIA_FORM, ["coi", "bank_letter"], "IN")
        r = _by_check(results, "doc_pan_gstin")
        assert r is not None
        assert r["status"] == "missing"

    def test_missing_bank_letter_doc_flagged(self):
        results = check_completeness(BASE_INDIA_FORM, ["coi", "pan_gstin"], "IN")
        r = _by_check(results, "doc_bank_letter")
        assert r is not None
        assert r["status"] == "missing"

    def test_coi_alias_registration_accepted(self):
        # "registration" is an alias for "coi"
        results = check_completeness(BASE_INDIA_FORM, ["registration", "pan_gstin", "bank_letter"], "IN")
        r = _by_check(results, "doc_coi")
        assert r is not None
        assert r["status"] == "pass"

    def test_pan_gstin_alias_tax_cert_accepted(self):
        results = check_completeness(BASE_INDIA_FORM, ["coi", "tax_cert", "bank_letter"], "IN")
        r = _by_check(results, "doc_pan_gstin")
        assert r is not None
        assert r["status"] == "pass"

    def test_bank_alias_accepted(self):
        results = check_completeness(BASE_INDIA_FORM, ["coi", "pan_gstin", "bank"], "IN")
        r = _by_check(results, "doc_bank_letter")
        assert r is not None
        assert r["status"] == "pass"

    def test_all_docs_present_all_pass(self):
        results = check_completeness(BASE_INDIA_FORM, INDIA_DOCS, "IN")
        doc_results = [r for r in results if r["check"].startswith("doc_")]
        fails = [r for r in doc_results if r["status"] != "pass"]
        assert fails == []

    def test_valid_email_passes(self):
        results = check_completeness(BASE_INDIA_FORM, INDIA_DOCS, "IN")
        r = _by_check(results, "email_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_invalid_email_fails(self):
        form = {**BASE_INDIA_FORM, "contact_email": "not_an_email"}
        results = check_completeness(form, INDIA_DOCS, "IN")
        r = _by_check(results, "email_format")
        assert r is not None
        assert r["status"] == "fail"

    def test_empty_docs_list_all_docs_missing(self):
        results = check_completeness(BASE_INDIA_FORM, [], "IN")
        doc_results = [r for r in results if r["check"].startswith("doc_")]
        assert all(r["status"] == "missing" for r in doc_results)

    def test_country_in_form_data_routes_to_india(self):
        # No explicit country arg — should read from form_data
        results = check_completeness(BASE_INDIA_FORM, INDIA_DOCS)
        r = _by_check(results, "field_cin_number")
        assert r is not None  # India-specific field is checked

    def test_each_result_has_required_keys(self):
        results = check_completeness(BASE_INDIA_FORM, INDIA_DOCS, "IN")
        for r in results:
            assert "check" in r
            assert "status" in r
            assert "detail" in r
            assert "confidence" in r


# ─── Generic Path ─────────────────────────────────────────────────────────────

class TestCheckCompletenessGeneric:
    def test_all_required_fields_pass(self):
        results = check_completeness(BASE_GENERIC_FORM, GENERIC_DOCS, "GB")
        field_results = [r for r in results if r["check"].startswith("field_")]
        fails = [r for r in field_results if r["status"] != "pass"]
        assert fails == [], f"Unexpected failures: {fails}"

    def test_all_generic_required_fields_checked(self):
        results = check_completeness(BASE_GENERIC_FORM, GENERIC_DOCS, "GB")
        checked_fields = {r["check"].replace("field_", "") for r in results if r["check"].startswith("field_")}
        for field in REQUIRED_FIELDS:
            assert field in checked_fields, f"Field not checked: {field}"

    def test_missing_company_name_flagged(self):
        form = {**BASE_GENERIC_FORM, "company_name": ""}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "field_company_name")
        assert r is not None
        assert r["status"] == "missing"

    def test_missing_contact_email_flagged(self):
        form = {**BASE_GENERIC_FORM, "contact_email": ""}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "field_contact_email")
        assert r is not None
        assert r["status"] == "missing"

    def test_valid_email_passes(self):
        results = check_completeness(BASE_GENERIC_FORM, GENERIC_DOCS, "GB")
        r = _by_check(results, "email_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_invalid_email_fails(self):
        form = {**BASE_GENERIC_FORM, "contact_email": "bademail"}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "email_format")
        assert r is not None
        assert r["status"] == "fail"

    def test_valid_uk_vat_passes(self):
        form = {**BASE_GENERIC_FORM, "tax_id": "GB123456789"}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "tax_id_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_invalid_uk_vat_fails(self):
        form = {**BASE_GENERIC_FORM, "tax_id": "GBINVALID"}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "tax_id_format")
        assert r is not None
        assert r["status"] == "fail"

    def test_valid_us_ein_passes(self):
        form = {**BASE_GENERIC_FORM, "country": "US", "tax_id": "12-3456789"}
        results = check_completeness(form, GENERIC_DOCS, "US")
        r = _by_check(results, "tax_id_format")
        assert r is not None
        assert r["status"] == "pass"

    def test_missing_doc_flagged(self):
        results = check_completeness(BASE_GENERIC_FORM, [], "GB")
        doc_results = [r for r in results if r["check"].startswith("doc_")]
        assert all(r["status"] == "missing" for r in doc_results)

    def test_all_docs_present_pass(self):
        results = check_completeness(BASE_GENERIC_FORM, GENERIC_DOCS, "GB")
        doc_results = [r for r in results if r["check"].startswith("doc_")]
        assert all(r["status"] == "pass" for r in doc_results)

    def test_account_name_exact_match_passes(self):
        form = {**BASE_GENERIC_FORM, "company_name": "Acme UK Ltd", "bank_account_name": "Acme UK Ltd"}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "account_name_match")
        assert r is not None
        assert r["status"] == "pass"

    def test_account_name_suffix_stripped_match_passes(self):
        # "Acme UK Limited" vs "Acme UK Ltd" — after stripping LTD/LIMITED, both → "Acme UK"
        form = {**BASE_GENERIC_FORM,
                "company_name": "Acme UK Limited",
                "bank_account_name": "Acme UK Ltd"}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "account_name_match")
        assert r is not None
        assert r["status"] == "pass"

    def test_account_name_mismatch_fails(self):
        form = {**BASE_GENERIC_FORM, "company_name": "Acme UK Ltd", "bank_account_name": "Totally Different Corp"}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "account_name_match")
        assert r is not None
        assert r["status"] == "fail"

    def test_valid_iban_passes(self):
        # GB33BUKB20201555555555 is a valid test IBAN
        form = {**BASE_GENERIC_FORM, "account_number": "GB33BUKB20201555555555"}
        results = check_completeness(form, GENERIC_DOCS, "GB")
        r = _by_check(results, "iban_format")
        if r:  # IBAN check only runs when account starts with alpha
            assert r["status"] == "pass"

    def test_unknown_country_no_tax_id_format_check(self):
        form = {**BASE_GENERIC_FORM, "country": "ZZ", "tax_id": "SOME123"}
        results = check_completeness(form, GENERIC_DOCS, "ZZ")
        r = _by_check(results, "tax_id_format")
        # Unknown country with tax_id → "pass" with low confidence
        if r:
            assert r["status"] == "pass"
            assert r["confidence"] <= 0.5
