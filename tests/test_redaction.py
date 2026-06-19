from __future__ import annotations

from prometheus_cli.redaction import REDACTED, redact


class TestApiKeyRedaction:
    def test_openai_key(self):
        assert redact("key=sk-abc123def456ghi789jkl012mno345pqr678") == f"key={REDACTED}"

    def test_google_key(self):
        text = "AIzaSyA1234567890abcdefghijklmnopqrstuvwx"
        assert redact(text) == REDACTED

    def test_aws_key(self):
        assert redact("aws_access_key_id = AKIAIOSFODNN7EXAMPLE") == f"aws_access_key_id = {REDACTED}"

    def test_github_token(self):
        text = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        assert redact(text) == REDACTED

    def test_slack_token(self):
        text = "xoxb-12345-abcdef"
        assert redact(text) == REDACTED


class TestCredentialPatterns:
    def test_password_assignment(self):
        text = "password = SuperSecretValue123"
        result = redact(text)
        assert REDACTED in result
        assert "SuperSecretValue123" not in result

    def test_api_key_in_env_style(self):
        text = "API_KEY=abcdef1234567890abcd"
        result = redact(text)
        assert REDACTED in result
        assert "abcdef1234567890abcd" not in result

    def test_bearer_token(self):
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
        result = redact(text)
        assert REDACTED in result
        assert "eyJhbGciOi" not in result

    def test_authorization_header(self):
        text = "Authorization: Basic dXNlcjpwYXNzMTIzNDU2Nzg5MA=="
        result = redact(text)
        assert REDACTED in result
        assert "dXNlcjpwYXNz" not in result

    def test_private_key_block(self):
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA1234567890abcdefghijklmnopqrstuvwxyz\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = redact(text)
        assert REDACTED in result
        assert "MIIEowIBAAKCAQEA" not in result

    def test_sha256_hash(self):
        hash_text = "a" * 64
        result = redact(hash_text)
        assert result == REDACTED


class TestNonSecretsPreserved:
    def test_normal_code_unchanged(self):
        code = "def add(a, b):\n    return a + b\n"
        assert redact(code) == code

    def test_short_strings_unchanged(self):
        assert redact("hello world") == "hello world"

    def test_empty_string(self):
        assert redact("") == ""

    def test_file_paths_unchanged(self):
        assert redact("/usr/local/bin/python") == "/usr/local/bin/python"


class TestRedactionInEvidence:
    def test_tool_output_with_secret_is_redacted(self):
        text = "config loaded: api_key=sk-1234567890abcdefghijklmnopqrstuv"
        assert "sk-1234567890abcdefghijklmnopqrstuv" not in redact(text)
