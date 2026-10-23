"""Tests for AIOS Triple Verification Gate and Architectural Health."""

import unittest
from core.sandbox import Sandbox, ExecutionResult
from core.validator import TripleValidator
from core.ingest import RepoIngestor


class TestTripleValidator(unittest.TestCase):
    def test_validator_certifies_clean_solution(self):
        with Sandbox() as sb:
            sb.write_file("main.py", "def add(a, b):\n    return a + b\n")
            validator = TripleValidator(sb)
            cmd_res = [ExecutionResult(
                command="pytest test_main.py",
                exit_code=0,
                stdout="test session starts ... 1 passed in 0.05s",
                stderr="",
            )]
            cert = validator.certify("pytest test_main.py", ["main.py"], cmd_res)
            self.assertTrue(cert.certified)
            self.assertTrue(cert.gate_syntax.passed)
            self.assertTrue(cert.gate_security.passed)
            self.assertTrue(cert.gate_assertions.passed)
            self.assertGreater(cert.overall_confidence, 80.0)

    def test_validator_rejects_syntax_error(self):
        with Sandbox() as sb:
            sb.write_file("main.py", "def add(a, b)\n    return a + b\n")  # missing colon
            validator = TripleValidator(sb)
            cmd_res = [ExecutionResult(
                command="pytest test_main.py",
                exit_code=0,
                stdout="1 passed",
                stderr="",
            )]
            cert = validator.certify("pytest test_main.py", ["main.py"], cmd_res)
            self.assertFalse(cert.certified)
            self.assertFalse(cert.gate_syntax.passed)

    def test_validator_rejects_failed_tests(self):
        with Sandbox() as sb:
            sb.write_file("main.py", "def add(a, b):\n    return a + b\n")
            validator = TripleValidator(sb)
            cmd_res = [ExecutionResult(
                command="pytest test_main.py",
                exit_code=1,
                stdout="",
                stderr="AssertionError: 2 != 5",
            )]
            cert = validator.certify("pytest test_main.py", ["main.py"], cmd_res)
            self.assertFalse(cert.certified)
            self.assertFalse(cert.gate_assertions.passed)

    def test_git_url_security_rejection(self):
        ingestor = RepoIngestor()
        with self.assertRaises(ValueError):
            ingestor.ingest_git_repo("https://malicious.com/repo.git")

        with self.assertRaises(ValueError):
            ingestor.ingest_git_repo("ssh://git@github.com/user/repo")

        with self.assertRaises(ValueError):
            ingestor.ingest_git_repo("https://github.com/user/repo; rm -rf /")

    def test_architectural_health_metrics(self):
        with Sandbox() as sb:
            sb.write_file("app.py", "def run():\n    '''Main entry point'''\n    pass\n")
            sb.write_file("test_app.py", "def test_run():\n    pass\n")
            ingestor = RepoIngestor()
            packed = ingestor.ingest_directory(sb.root)
            health = packed.calculate_health()
            self.assertEqual(health.total_files, 2)
            self.assertEqual(health.test_files_count, 1)
            self.assertEqual(health.test_density_pct, 50.0)
            self.assertGreater(health.docstring_coverage_pct, 0.0)


if __name__ == "__main__":
    unittest.main()
