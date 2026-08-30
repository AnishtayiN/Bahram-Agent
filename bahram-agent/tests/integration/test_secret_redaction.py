"""Tests for secret redaction in monitoring and logging."""
from __future__ import annotations

from bahram.monitoring.status import redact_secrets


class TestRedactApiKeys:
    def test_openai_key_redacted(self) -> None:
        text = "Using key sk-abcdefghijklmnopqrstuvwxyz123456"
        result = redact_secrets(text)
        assert "sk-" not in result
        assert "REDACTED" in result

    def test_gemini_key_redacted(self) -> None:
        text = "Key: AIzaSyA1234567890abcdefghijklmnopqrstuv"
        result = redact_secrets(text)
        assert "AIzaSy" not in result
        assert "REDACTED" in result

    def test_generic_api_key_format(self) -> None:
        text = "api_key: abcdefghijklmnopqrst1234567890"
        result = redact_secrets(text)
        assert "abcdefghijklmnopqrst1234567890" not in result
        assert "REDACTED" in result


class TestRedactTelegramTokens:
    def test_telegram_bot_token_redacted(self) -> None:
        text = "Bot token: 1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg"
        result = redact_secrets(text)
        assert "1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefg" not in result
        assert "REDACTED" in result

    def test_token_keyword_format(self) -> None:
        text = "token = abcdefghijklmnopqrstuvwxyz12345678"
        result = redact_secrets(text)
        assert "abcdefghijklmnopqrstuvwxyz12345678" not in result
        assert "REDACTED" in result


class TestRedactEnvironmentSecrets:
    def test_env_var_redacted(self) -> None:
        import os
        old_val = os.environ.get("TEST_SECRET_XYZ_98765")
        try:
            os.environ["TEST_SECRET_XYZ_98765"] = "supersecretvalue999"
            text = "Config has TEST_SECRET_XYZ_98765=supersecretvalue999"
            result = redact_secrets(text)
            assert "supersecretvalue999" not in result
            assert "REDACTED" in result
        finally:
            if old_val is None:
                os.environ.pop("TEST_SECRET_XYZ_98765", None)
            else:
                os.environ["TEST_SECRET_XYZ_98765"] = old_val

    def test_short_env_var_not_redacted(self) -> None:
        import os
        old_val = os.environ.get("TEST_SHORT_98765")
        try:
            os.environ["TEST_SHORT_98765"] = "abc"
            text = "value is abc"
            result = redact_secrets(text)
            assert "abc" in result
        finally:
            if old_val is None:
                os.environ.pop("TEST_SHORT_98765", None)
            else:
                os.environ["TEST_SHORT_98765"] = old_val


class TestRedactToolOutput:
    def test_tool_result_with_key_is_redacted(self) -> None:
        tool_output = '{"api_key": "sk-test123456789012345678901234", "status": "ok"}'
        result = redact_secrets(tool_output)
        assert "sk-test123456789012345678901234" not in result
        assert "REDACTED" in result

    def test_tool_result_with_token_is_redacted(self) -> None:
        tool_output = 'Bot token: 9876543210:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh'
        result = redact_secrets(tool_output)
        assert "9876543210:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh" not in result
        assert "REDACTED" in result

    def test_tool_result_without_secrets_unchanged(self) -> None:
        tool_output = "File created successfully at /tmp/test.txt"
        result = redact_secrets(tool_output)
        assert result == tool_output

    def test_empty_string_unchanged(self) -> None:
        assert redact_secrets("") == ""

    def test_jwt_redacted(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = redact_secrets(jwt)
        assert jwt not in result
        assert "REDACTED" in result

    def test_github_token_redacted(self) -> None:
        text = "Token: ghp_TESTFAKE123456789012345678901234"
        result = redact_secrets(text)
        assert "ghp_" not in result
        assert "REDACTED" in result

    def test_slack_token_redacted(self) -> None:
        text = "Token: xoxb-TEST-FAKE-abcdef"
        result = redact_secrets(text)
        assert "REDACTED" in result

    def test_password_keyword_redacted(self) -> None:
        text = "password = mySuperSecretPass123"
        result = redact_secrets(text)
        assert "mySuperSecretPass123" not in result
        assert "REDACTED" in result
