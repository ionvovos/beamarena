import os
import unittest
from core.client import BeamClient
from core.sandbox import Sandbox
from core.ingest import RepoIngestor
from core.tools import ToolParser, ToolExecutor, ParsedPlan, FileEditAction


class TestCoreModules(unittest.TestCase):
    def test_sandbox_write_read_and_run(self):
        with Sandbox() as sb:
            sb.write_file("hello.py", "print('SANDBOX_OK')")
            self.assertEqual(sb.read_file("hello.py"), "print('SANDBOX_OK')")
            res = sb.run_command(["python3", "hello.py"])
            self.assertEqual(res.exit_code, 0)
            self.assertIn("SANDBOX_OK", res.stdout)

    def test_ingestor_structure(self):
        with Sandbox() as sb:
            sb.write_file("main.py", "def add(a, b):\n    '''Adds two numbers'''\n    return a + b\n")
            sb.write_file("sub/utils.py", "class Helper:\n    pass\n")
            ingestor = RepoIngestor()
            packed = ingestor.ingest_directory(sb.root)
            self.assertEqual(len(packed.files), 2)
            self.assertIn("main.py", packed.files)
            self.assertIn("sub/utils.py", packed.files)
            prompt = packed.render_prompt_context()
            self.assertIn("<repository", prompt)
            self.assertIn("Adds two numbers", prompt)

    def test_tool_parser(self):
        parser = ToolParser()
        sample = """
        I will fix the bug in auth.py and run the tests.
        <edit_file path="auth.py">
        def authenticate():
            return True
        </edit_file>
        <run_command>
        pytest tests/test_auth.py
        </run_command>
        <explanation>
        Fixed the token check.
        </explanation>
        """
        plan = parser.parse(sample)
        self.assertEqual(len(plan.file_edits), 1)
        self.assertEqual(plan.file_edits[0].file_path, "auth.py")
        self.assertIn("return True", plan.file_edits[0].content)
        self.assertEqual(len(plan.commands), 1)
        self.assertEqual(plan.commands[0].command, "pytest tests/test_auth.py")
        self.assertEqual(plan.thought_summary, "Fixed the token check.")

    def test_scenario_aliases(self):
        from scenarios import get_scenario
        scen_08 = get_scenario("08_db_pool_leak")
        self.assertIsNotNone(scen_08)
        self.assertEqual(scen_08.id, "08_async_resource_db_pool_context_manager_leak_prevention")

        scen_10 = get_scenario("10_memory_bounded_stream")
        self.assertIsNotNone(scen_10)
        self.assertEqual(scen_10.id, "10_memory_bounded_chunked_stream_pipeline")

    def test_custom_workspace_parser_hardening(self):
        from app import parse_custom_workspace
        # Test standard separator comment does not produce empty filename
        code = """# ====================
# Just a comment separator
def foo():
    return 1
# ===== mod/bar.py =====
def bar():
    return 2
"""
        files = parse_custom_workspace(code)
        self.assertNotIn("", files)
        self.assertIn("solution.py", files)
        self.assertIn("mod/bar.py", files)
        self.assertIn("def foo():", files["solution.py"])
        self.assertIn("def bar():", files["mod/bar.py"])

    def test_analyze_repo_path_confinement(self):
        from app import analyze_repo_prompt
        # Path outside project root should be denied
        report, status = analyze_repo_prompt("/etc")
        self.assertIn("Access denied", report)
        self.assertEqual(status, "Access Denied")

        report, status = analyze_repo_prompt("../../..")
        self.assertIn("Access denied", report)
        self.assertEqual(status, "Access Denied")


if __name__ == "__main__":
    unittest.main()
