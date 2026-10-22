"""Agent Loop Unit & Integration Tests (Mocked Client)."""

import pytest
from core.agent import AutonomousCodingAgent, AgentSessionTrace
from core.client import BeamClient, BeamResponse, TokenUsage
from core.sandbox import Sandbox


class MockBeamClient(BeamClient):
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    def stream_chat(self, messages, **kwargs):
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            if kwargs.get("on_reasoning") and resp.reasoning:
                kwargs["on_reasoning"](resp.reasoning)
            if kwargs.get("on_content") and resp.content:
                kwargs["on_content"](resp.content)
            return resp
        return BeamResponse(
            content="<explanation>No further action</explanation>",
            reasoning="Done",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )


def test_agent_solves_bug_in_turn_1():
    """Verifies that when Beam provides a working patch, the loop exits green."""
    mock_resp = BeamResponse(
        content="""<explanation>Fixing bug by defining add</explanation>
<edit_file path="calc.py">
def add(a, b):
    return a + b
</edit_file>
<run_command>
pytest test_calc.py
</run_command>""",
        reasoning="I need to define add function returning a + b.",
        usage=TokenUsage(prompt_tokens=100, completion_tokens=50, reasoning_tokens=25, total_tokens=150),
    )

    client = MockBeamClient([mock_resp])
    agent = AutonomousCodingAgent(client=client, max_turns=2, persist_trace=False)

    with Sandbox() as sb:
        sb.write_file("calc.py", "def add(a, b):\n    return 0\n")
        sb.write_file("test_calc.py", "from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n")

        trace: AgentSessionTrace = agent.solve(
            task_description="Fix add function in calc.py",
            sandbox=sb,
            test_command="pytest test_calc.py",
            scenario_id="mock_test",
        )

        assert trace.resolved is True
        assert len(trace.turns) == 1
        assert trace.turns[0].passed is True
        assert "return a + b" in sb.read_file("calc.py")


def test_agent_multi_turn_self_healing():
    """Verifies that when turn 1 fails, the feedback is analyzed and turn 2 fixes it."""
    resp1 = BeamResponse(
        content="""<explanation>Attempting fix with subtraction</explanation>
<edit_file path="calc.py">
def add(a, b):
    return a - b
</edit_file>
<run_command>
pytest test_calc.py
</run_command>""",
        reasoning="First try subtraction.",
        usage=TokenUsage(prompt_tokens=100, completion_tokens=40, reasoning_tokens=20, total_tokens=140),
    )

    resp2 = BeamResponse(
        content="""<explanation>Correcting to addition</explanation>
<edit_file path="calc.py">
def add(a, b):
    return a + b
</edit_file>
<run_command>
pytest test_calc.py
</run_command>""",
        reasoning="The traceback showed 2 - 3 == -1 != 5. Switch to a + b.",
        usage=TokenUsage(prompt_tokens=150, completion_tokens=40, reasoning_tokens=20, total_tokens=190),
    )

    client = MockBeamClient([resp1, resp2])
    agent = AutonomousCodingAgent(client=client, max_turns=3, persist_trace=False)

    with Sandbox() as sb:
        sb.write_file("calc.py", "def add(a, b):\n    return 0\n")
        sb.write_file("test_calc.py", "from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n")

        trace = agent.solve(
            task_description="Fix add in calc.py",
            sandbox=sb,
            test_command="pytest test_calc.py",
            scenario_id="mock_multi_turn",
        )

        assert trace.resolved is True
        assert len(trace.turns) == 2
        assert trace.turns[0].passed is False
        assert trace.turns[1].passed is True
