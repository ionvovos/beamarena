"""Autonomous Self-Healing Agent Loop.

Executes a multi-turn Reinforcement-Learning-style test-driven repair loop:
1. Ingests problem context and codebase.
2. Formulates reasoning plan using Beam's 1M context.
3. Applies file edits and executes sandboxed commands.
4. If tests fail, feeds traceback back to Beam to self-correct until all tests pass.
5. Emits real-time generator events for reactive UI streaming.
"""

from dataclasses import asdict, dataclass, field
import json
import os
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple
from .client import BeamClient, BeamResponse, TokenUsage
from .sandbox import ExecutionResult, Sandbox
from .tools import ParsedPlan, ToolExecutor, ToolParser


@dataclass
class AgentTurn:
    turn_index: int
    prompt: str
    reasoning_content: str
    response_content: str
    edits_applied: List[str]
    command_results: List[ExecutionResult]
    passed: bool
    usage: TokenUsage


@dataclass
class AgentSessionTrace:
    scenario_id: str
    task_description: str
    turns: List[AgentTurn] = field(default_factory=list)
    resolved: bool = False
    total_tokens: int = 0
    total_reasoning_tokens: int = 0
    wall_clock_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Converts trace to JSON-serializable dictionary."""
        return {
            "scenario_id": self.scenario_id,
            "task_description": self.task_description,
            "resolved": self.resolved,
            "total_tokens": self.total_tokens,
            "total_reasoning_tokens": self.total_reasoning_tokens,
            "wall_clock_seconds": self.wall_clock_seconds,
            "turns": [
                {
                    "turn_index": t.turn_index,
                    "reasoning_content": t.reasoning_content,
                    "response_content": t.response_content,
                    "edits_applied": t.edits_applied,
                    "command_results": [
                        {
                            "command": cr.command,
                            "exit_code": cr.exit_code,
                            "stdout": cr.stdout,
                            "stderr": cr.stderr,
                            "timed_out": cr.timed_out,
                            "duration_seconds": cr.duration_seconds,
                        }
                        for cr in t.command_results
                    ],
                    "passed": t.passed,
                    "usage": {
                        "prompt_tokens": t.usage.prompt_tokens,
                        "completion_tokens": t.usage.completion_tokens,
                        "reasoning_tokens": t.usage.reasoning_tokens,
                        "total_tokens": t.usage.total_tokens,
                    },
                }
                for t in self.turns
            ],
        }


AGENT_SYSTEM_PROMPT = """You are BeamArena's Autonomous Software Engineering Agent, powered by Beam-1.0-501B-A23B.
Your goal is to inspect codebases, diagnose bugs or implement requested features, execute test commands, and verify test assertions until green.

FORMAT RULES:
1. When you need to edit or create a file, use the <edit_file> XML block:
<edit_file path="relative/path/to/file.py">
FULL CONTENT OF THE MODIFIED FILE
</edit_file>

2. When you need to run terminal commands (e.g. run pytest or execute a script), use <run_command>:
<run_command>
pytest tests/test_feature.py
</run_command>

3. Provide a clear summary of your reasoning and root-cause analysis inside <explanation>:
<explanation>
Explanation of what went wrong and how you resolved it.
</explanation>

Always write clean, production-ready code with no placeholders or truncated code blocks.
"""


class AutonomousCodingAgent:
    def __init__(
        self,
        client: Optional[BeamClient] = None,
        max_turns: int = 3,
        max_token_budget: int = 100000,
        on_turn_start: Optional[Callable[[int], None]] = None,
        on_turn_complete: Optional[Callable[[AgentTurn], None]] = None,
    ):
        self.client = client or BeamClient()
        self.max_turns = max_turns
        self.max_token_budget = max_token_budget
        self.parser = ToolParser()
        self.on_turn_start = on_turn_start
        self.on_turn_complete = on_turn_complete

    def solve_stream(
        self,
        task_description: str,
        sandbox: Sandbox,
        test_command: str = "pytest",
        scenario_id: str = "custom",
    ) -> Iterator[Tuple[str, Any]]:
        """Streaming generator that yields ('event_type', payload) as the repair loop executes."""
        start_time = time.time()
        trace = AgentSessionTrace(
            scenario_id=scenario_id,
            task_description=task_description,
        )

        executor = ToolExecutor(sandbox)
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": AGENT_SYSTEM_PROMPT}
        ]

        # Initial prompt includes file inventory and user task
        file_list = sandbox.list_files()
        files_dump = []
        for f in file_list:
            if not f.startswith("."):
                try:
                    content = sandbox.read_file(f)
                    files_dump.append(f"<file path='{f}'>\n{content}\n</file>")
                except Exception:
                    pass

        initial_user_prompt = (
            f"TASK DESCRIPTION:\n{task_description}\n\n"
            f"TEST COMMAND TO PASS:\n{test_command}\n\n"
            f"CURRENT WORKSPACE FILES:\n" + "\n".join(files_dump) + "\n\n"
            f"Analyze the codebase, identify the bug or missing implementation, "
            f"FIRST output the corrected file(s) inside <edit_file path='...'>...</edit_file> blocks, "
            f"THEN verify with <run_command>{test_command}</run_command>. "
            f"Do not run tests before providing the edit."
        )

        messages.append({"role": "user", "content": initial_user_prompt})

        for turn_idx in range(1, self.max_turns + 1):
            if trace.total_tokens >= self.max_token_budget:
                yield ("warning", f"Token budget exceeded: {trace.total_tokens} >= {self.max_token_budget}")
                break

            yield ("turn_start", turn_idx)
            if self.on_turn_start:
                self.on_turn_start(turn_idx)

            # 1. Query Beam with streaming callbacks for real-time trace
            current_turn_reasoning: List[str] = []
            current_turn_content: List[str] = []

            def on_r(chunk: str):
                current_turn_reasoning.append(chunk)

            def on_c(chunk: str):
                current_turn_content.append(chunk)

            response: BeamResponse = self.client.stream_chat(
                messages=messages,
                temperature=0.2,
                max_tokens=8192,
                on_reasoning=on_r,
                on_content=on_c,
            )

            # 2. Parse Actions
            plan: ParsedPlan = self.parser.parse(response.content)

            # 3. Apply Edits to Sandbox
            edits_applied = executor.apply_plan(plan)

            # 4. If the model didn't specify the test command, ensure we execute the verification command
            has_test_cmd = any(test_command in c.command for c in plan.commands)
            if not has_test_cmd:
                plan.commands.append(type("Cmd", (), {"command": test_command})())

            command_results = executor.run_commands(plan)

            # 5. Evaluate if the verification command passed
            test_passed = False
            for cr in command_results:
                if test_command in cr.command and cr.exit_code == 0:
                    test_passed = True
                    break

            turn = AgentTurn(
                turn_index=turn_idx,
                prompt=messages[-1]["content"],
                reasoning_content=response.reasoning,
                response_content=response.content,
                edits_applied=edits_applied,
                command_results=command_results,
                passed=test_passed,
                usage=response.usage,
            )
            trace.turns.append(turn)
            trace.total_tokens += response.usage.total_tokens
            trace.total_reasoning_tokens += response.usage.reasoning_tokens

            yield ("turn_complete", turn)
            if self.on_turn_complete:
                self.on_turn_complete(turn)

            # If passed, we are done!
            if test_passed:
                trace.resolved = True
                break

            # 6. If failed and we have turns left, formulate the RL feedback message
            last_cmd_res = command_results[-1] if command_results else None
            failure_feedback = (
                f"VERIFICATION FAILED for command '{test_command}'.\n"
                f"Exit Code: {last_cmd_res.exit_code if last_cmd_res else -1}\n"
                f"STDOUT:\n{last_cmd_res.stdout if last_cmd_res else ''}\n"
                f"STDERR:\n{last_cmd_res.stderr if last_cmd_res else ''}\n\n"
                f"Carefully analyze this traceback and error. What went wrong? "
                f"Provide a revised <edit_file> patch and verify again with <run_command>{test_command}</run_command>."
            )

            assistant_msg = {
                "role": "assistant",
                "content": response.content,
                "reasoning_content": response.reasoning,
            }
            messages.append(assistant_msg)
            messages.append({"role": "user", "content": failure_feedback})

        trace.wall_clock_seconds = round(time.time() - start_time, 2)
        self._persist_trace(trace)
        yield ("done", trace)

    def solve(
        self,
        task_description: str,
        sandbox: Sandbox,
        test_command: str = "pytest",
        scenario_id: str = "custom",
    ) -> AgentSessionTrace:
        """Executes the test-driven self-healing loop synchronously."""
        final_trace = None
        for event, payload in self.solve_stream(
            task_description=task_description,
            sandbox=sandbox,
            test_command=test_command,
            scenario_id=scenario_id,
        ):
            if event == "done":
                final_trace = payload

        if final_trace is None:
            final_trace = AgentSessionTrace(
                scenario_id=scenario_id,
                task_description=task_description,
            )
        return final_trace

    def _persist_trace(self, trace: AgentSessionTrace) -> None:
        """Appends the execution trace to benchmarks/traces.jsonl."""
        try:
            traces_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
            os.makedirs(traces_dir, exist_ok=True)
            traces_file = os.path.join(traces_dir, "traces.jsonl")
            with open(traces_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")
        except Exception:
            pass
