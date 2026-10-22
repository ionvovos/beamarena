#!/usr/bin/env python3
"""BeamArena CLI — Autonomous Coding & Evaluation Engine.

Run autonomous repairs, ingest 1M repositories, and evaluate benchmarks locally.
"""

import argparse
import json
import os
import sys
from core.client import BeamClient
from core.sandbox import Sandbox
from core.agent import AutonomousCodingAgent
from core.ingest import RepoIngestor
from scenarios import ALL_SCENARIOS


def cmd_solve(args):
    scen = ALL_SCENARIOS.get(args.scenario)
    if not scen:
        print(f"Error: Unknown scenario '{args.scenario}'. Available: {list(ALL_SCENARIOS.keys())}")
        sys.exit(1)

    print("=" * 60)
    print(f"⚡ [BeamArena] Solving Scenario: {scen.title}")
    print(f"📁 Workspace: {len(scen.files)} files | Verification: {scen.test_command}")
    print("=" * 60)

    client = BeamClient()
    agent = AutonomousCodingAgent(client=client, max_turns=args.max_turns)

    with Sandbox() as sb:
        sb.load_files(scen.files)

        def on_start(turn_idx):
            print(f"\n>>> TURN {turn_idx} STARTING...")

        def on_complete(turn):
            print(f">>> TURN {turn.turn_index} FINISHED. Tests Passed: {turn.passed}")
            print(f"    Reasoning Tokens: {turn.usage.reasoning_tokens} | Total: {turn.usage.total_tokens}")
            for log in turn.edits_applied:
                print(f"    • {log}")
            for cr in turn.command_results:
                status = "PASS" if cr.exit_code == 0 else f"FAIL (code {cr.exit_code})"
                print(f"    $ {cr.command} -> {status}")

        agent.on_turn_start = on_start
        agent.on_turn_complete = on_complete

        trace = agent.solve(
            task_description=scen.description,
            sandbox=sb,
            test_command=scen.test_command,
            scenario_id=scen.id
        )

        print("\n" + "=" * 60)
        print(f"RESULT: {'✅ SOLVED (TESTS GREEN)' if trace.resolved else '❌ FAILED'}")
        print(f"Turns: {len(trace.turns)} | Time: {trace.wall_clock_seconds}s")
        print(f"Total Tokens: {trace.total_tokens} (Reasoning: {trace.total_reasoning_tokens})")
        print("=" * 60)

        if not trace.resolved:
            sys.exit(1)


def cmd_ingest(args):
    target_dir = os.path.abspath(args.path)
    if not os.path.exists(target_dir):
        print(f"Error: Path does not exist: {target_dir}")
        sys.exit(1)

    print("=" * 60)
    print(f"🌐 [BeamArena] Ingesting Codebase (1M Context Mode): {target_dir}")
    print("=" * 60)

    ingestor = RepoIngestor()
    packed = ingestor.ingest_directory(target_dir)

    print(f"Scanned Files: {len(packed.files)}")
    print(f"Total Size: {round(packed.total_bytes / 1024, 2)} KB")
    print(f"Estimated Tokens: ~{packed.estimated_tokens:,} tokens (Capacity: 1,048,576)")
    print("\n--- File Tree Sample ---")
    tree_preview = "\n".join(packed.file_tree.splitlines()[:25])
    print(tree_preview)
    if len(packed.file_tree.splitlines()) > 25:
        print("... (truncated)")


def cmd_list(args):
    print("Available Scenarios in BeamArena:")
    for s_id, s in ALL_SCENARIOS.items():
        print(f"  • {s_id:25} [{s.difficulty:6}] {s.title}")


def main():
    parser = argparse.ArgumentParser(description="BeamArena Autonomous CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Solve
    solve_parser = subparsers.add_parser("solve", help="Run autonomous self-healing on a scenario")
    solve_parser.add_argument("--scenario", "-s", default="01_fastapi_auth", help="Scenario ID to solve")
    solve_parser.add_argument("--max-turns", "-t", type=int, default=3, help="Max repair turns")

    # Ingest
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a local repository into 1M context")
    ingest_parser.add_argument("path", help="Local directory path to ingest")

    # List
    subparsers.add_parser("list", help="List all benchmark scenarios")

    args = parser.parse_args()
    if args.command == "solve":
        cmd_solve(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
