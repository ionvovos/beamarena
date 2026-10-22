#!/usr/bin/env python3
import sys
from core.client import BeamClient
from core.sandbox import Sandbox
from core.agent import AutonomousCodingAgent
from scenarios import SCENARIO_01_AUTH

print("=" * 60)
print(f"RUNNING LIVE AUTONOMOUS AGENT ON: {SCENARIO_01_AUTH.title}")
print("=" * 60)

client = BeamClient()
agent = AutonomousCodingAgent(client=client, max_turns=3)

with Sandbox() as sb:
    sb.load_files(SCENARIO_01_AUTH.files)
    print(f"Workspace loaded with {len(sb.list_files())} files.")
    
    def on_start(turn_idx):
        print(f"\n>>> TURN {turn_idx} STARTING...")

    def on_complete(turn):
        print(f">>> TURN {turn.turn_index} FINISHED. Passed: {turn.passed}")
        print(f"Reasoning Tokens: {turn.usage.reasoning_tokens} | Total: {turn.usage.total_tokens}")
        print(f"Edits applied: {len(turn.edits_applied)}")
        print("\n--- Model Response Preview ---")
        print(turn.response_content[:500] + ("..." if len(turn.response_content) > 500 else ""))
        print("------------------------------")
        for cr in turn.command_results:
            print(f"Cmd: '{cr.command}' -> Exit Code: {cr.exit_code}")

    agent.on_turn_start = on_start
    agent.on_turn_complete = on_complete

    trace = agent.solve(
        task_description=SCENARIO_01_AUTH.description,
        sandbox=sb,
        test_command=SCENARIO_01_AUTH.test_command,
        scenario_id=SCENARIO_01_AUTH.id
    )

    print("\n" + "=" * 60)
    print(f"FINAL RESULT: {'SOLVED (PASSED)' if trace.resolved else 'FAILED'}")
    print(f"Total Turns: {len(trace.turns)}")
    print(f"Wall Clock: {trace.wall_clock_seconds}s")
    print(f"Total Tokens: {trace.total_tokens} (Reasoning: {trace.total_reasoning_tokens})")
    print("=" * 60)

    if not trace.resolved:
        sys.exit(1)
