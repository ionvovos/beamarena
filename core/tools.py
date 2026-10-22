"""Tool Execution & Parsing Module.

Parses structured actions from Beam's output and executes them
against the isolated Sandbox environment.
"""

from dataclasses import dataclass
import re
from typing import List, Optional
from .sandbox import ExecutionResult, Sandbox


@dataclass
class FileEditAction:
    file_path: str
    content: str


@dataclass
class RunCommandAction:
    command: str


@dataclass
class ParsedPlan:
    thought_summary: str = ""
    file_edits: List[FileEditAction] = None
    commands: List[RunCommandAction] = None
    final_answer: str = ""

    def __post_init__(self):
        if self.file_edits is None:
            self.file_edits = []
        if self.commands is None:
            self.commands = []


class ToolParser:
    """Extracts explicit file edits and bash commands from LLM response text."""

    EDIT_PATTERN = re.compile(
        r"<edit_file\s+path=[\"']([^\"']+)[\"']\s*>(.*?)</edit_file>",
        re.DOTALL
    )
    COMMAND_PATTERN = re.compile(
        r"<run_command>(.*?)</run_command>",
        re.DOTALL
    )
    EXPLANATION_PATTERN = re.compile(
        r"<explanation>(.*?)</explanation>",
        re.DOTALL
    )

    def parse(self, text: str) -> ParsedPlan:
        plan = ParsedPlan()

        # Extract file edits
        for match in self.EDIT_PATTERN.finditer(text):
            path = match.group(1).strip()
            content = match.group(2)
            # Remove leading/trailing newlines added by xml tags
            if content.startswith("\n"):
                content = content[1:]
            if content.endswith("\n"):
                content = content[:-1]
            plan.file_edits.append(FileEditAction(file_path=path, content=content))

        # Extract commands
        for match in self.COMMAND_PATTERN.finditer(text):
            cmd = match.group(1).strip()
            if cmd:
                plan.commands.append(RunCommandAction(command=cmd))

        # Extract explanation
        exp_match = self.EXPLANATION_PATTERN.search(text)
        if exp_match:
            plan.thought_summary = exp_match.group(1).strip()
        else:
            # Fall back to removing the tag blocks to get raw explanation
            clean_text = self.EDIT_PATTERN.sub("", text)
            clean_text = self.COMMAND_PATTERN.sub("", clean_text)
            plan.thought_summary = clean_text.strip()

        return plan


class ToolExecutor:
    def __init__(self, sandbox: Sandbox):
        self.sandbox = sandbox

    def apply_plan(self, plan: ParsedPlan) -> List[str]:
        """Applies all edits in the plan to the sandbox, returning execution logs."""
        logs = []
        for edit in plan.file_edits:
            try:
                target_path = self.sandbox.write_file(edit.file_path, edit.content)
                logs.append(f"Successfully edited file: {edit.file_path} ({len(edit.content)} chars)")
            except Exception as e:
                logs.append(f"Failed to edit {edit.file_path}: {str(e)}")
        return logs

    def run_commands(self, plan: ParsedPlan, timeout: float = 15.0) -> List[ExecutionResult]:
        """Executes all bash commands sequentially inside the sandbox."""
        results = []
        for cmd_action in plan.commands:
            parts = cmd_action.command.split()
            if not parts:
                continue
            res = self.sandbox.run_command(parts, timeout_seconds=timeout)
            results.append(res)
        return results
