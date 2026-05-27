"""Tests for PII redaction."""

from web_auto_form.redact import redact_text, redact_value_for_log


class TestRedactText:
    def test_redact_email(self):
        result = redact_text("Contact: user@example.com")
        assert "user@example.com" not in result
        assert "***" in result

    def test_redact_chinese_phone(self):
        result = redact_text("Phone: +86 138-0000-1234")
        assert "138" not in result

    def test_redact_chinese_id(self):
        result = redact_text("ID: 110101199001011234")
        assert "110101199001011234" not in result

    def test_no_pii_unchanged(self):
        text = "No PII here, just normal text."
        assert redact_text(text) == text

    def test_redact_ssn(self):
        result = redact_text("SSN: 123-45-6789")
        assert "123-45-6789" not in result


class TestRedactValueForLog:
    def test_redacted_when_enabled(self):
        assert redact_value_for_log("secret", True) == "<redacted>"

    def test_raw_when_disabled(self):
        assert redact_value_for_log("visible", False) == "visible"

    def test_none_handling(self):
        assert redact_value_for_log(None, True) == "<redacted>"
        assert redact_value_for_log(None, False) == ""
