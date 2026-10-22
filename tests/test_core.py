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


if __name__ == "__main__":
    unittest.main()
