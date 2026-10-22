#!/usr/bin/env python3
"""Batch generates and verifies advanced scenarios using Beam-1.0-501B-A23B."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.client import BeamClient

def generate_scenario(client, spec_prompt, output_file):
    print(f"\n--> Requesting Beam generation for: {output_file}...")
    full_prompt = f"""{spec_prompt}

Return a STRICT, CLEAN JSON object with NO markdown fencing, with EXACT keys:
"id": string (e.g. "07_websocket_backoff")
"title": string
"difficulty": string ("Medium" or "Hard")
"description": string
"test_command": string (e.g. "python3 -m unittest tests.test_...")
"files": dictionary mapping relative file paths to their exact string contents (must include "tests/__init__.py", implementation file, and test file).
Ensure the implementation file has clear bugs that cause the tests in test file to fail initially, but the tests test legitimate correct behavior.
"""
    resp = client.chat_complete(
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=4000,
        temperature=0.2
    )
    print(f"Received Beam response! Reasoning tokens: {resp.usage.reasoning_tokens}, Total tokens: {resp.usage.total_tokens}")
    content = resp.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]
        content = content.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(content)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Successfully validated & saved: {output_file}")
        return data
    except Exception as e:
        print(f"JSON decode error: {e}")
        # Save raw content for manual inspection
        with open(output_file + ".raw", "w", encoding="utf-8") as f:
            f.write(content)
        return None

def main():
    client = BeamClient()
    benchmarks_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    os.makedirs(benchmarks_dir, exist_ok=True)

    # 07: WebSocket Backoff & Reconnect
    prompt_07 = """You are designing Scenario 07: WebSocket Exponential Backoff with Jitter and Reconnect Replay.
Buggy file: client.py. Unit test: tests/test_client.py.
Bugs in client.py:
1. compute_backoff ignores jitter or computes fixed delay exceeding max_backoff.
2. reconnect() does not clear or re-queue unacknowledged pending messages on connection loss, causing message drop.
3. consecutive_failures counter is never reset upon successful connect."""
    generate_scenario(client, prompt_07, os.path.join(benchmarks_dir, "scenario_07_beam.json"))

    # 08: Async Connection Pool Leak
    prompt_08 = """You are designing Scenario 08: Async Resource / DB Pool Context Manager Leak Prevention.
Buggy file: pool.py. Unit test: tests/test_pool.py.
Bugs in pool.py:
1. acquire() context manager fails to release the acquired connection back to the available queue when an exception occurs inside the 'with' block.
2. Lacks proper timeout handling when pool is exhausted (deadlocks instead of raising PoolExhaustedError).
3. Pool size gauge is incremented without decrementing upon release."""
    generate_scenario(client, prompt_08, os.path.join(benchmarks_dir, "scenario_08_beam.json"))

if __name__ == "__main__":
    main()
