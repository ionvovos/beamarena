"""Security and Isolation Test Suite for BeamArena."""

import os
import tempfile
import pytest
from core.sandbox import Sandbox
from core.ingest import RepoIngestor


class TestSandboxSecurity:
    def test_subprocess_environment_sanitization(self):
        """Ensures API keys and secrets do not leak to subprocesses."""
        os.environ["REFLECTION_API_KEY"] = "secret_beam_key_12345"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "super_secret_aws_key"
        os.environ["SAFE_INHERITED_VAR"] = "not_a_secret"

        with Sandbox() as sb:
            cmd = ["python3", "-c", "import os; print('KEY_IN_ENV:', 'REFLECTION_API_KEY' in os.environ, 'AWS_IN_ENV:', 'AWS_SECRET_ACCESS_KEY' in os.environ)"]
            res = sb.run_command(cmd)
            assert res.exit_code == 0
            assert "KEY_IN_ENV: False" in res.stdout
            assert "AWS_IN_ENV: False" in res.stdout

    def test_path_traversal_rejection(self):
        """Verifies sandbox containment rejects path escapes."""
        with Sandbox() as sb:
            with pytest.raises(ValueError, match="Path traversal attempted"):
                sb.write_file("../../outside.txt", "malicious content")

            with pytest.raises(ValueError, match="Path traversal attempted"):
                sb.read_file("../../outside.txt")

    def test_timeout_enforcement(self):
        """Ensures commands exceeding timeout are safely terminated."""
        with Sandbox() as sb:
            cmd = ["python3", "-c", "import time; time.sleep(5)"]
            res = sb.run_command(cmd, timeout_seconds=0.5)
            assert res.timed_out is True
            assert res.exit_code == -1
            assert "timed out" in res.stderr.lower()


class TestIngestorSecurity:
    def test_credential_filtering(self):
        """Verifies repository packer strips secret and credential files."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create harmless file
            with open(os.path.join(tmp, "main.py"), "w") as f:
                f.write("print('hello')\n")
            # Create sensitive files
            with open(os.path.join(tmp, ".env"), "w") as f:
                f.write("API_KEY=123\n")
            with open(os.path.join(tmp, "id_rsa"), "w") as f:
                f.write("PRIVATE KEY\n")
            with open(os.path.join(tmp, "server.pem"), "w") as f:
                f.write("CERTIFICATE\n")

            ingestor = RepoIngestor()
            packed = ingestor.ingest_directory(tmp)
            assert "main.py" in packed.files
            assert ".env" not in packed.files
            assert "id_rsa" not in packed.files
            assert "server.pem" not in packed.files
