#!/usr/bin/env python3
"""Uses Beam-1.0-501B-A23B to design and verify advanced benchmark scenarios."""

import json
import os
import sys

# Ensure root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.client import BeamClient
from core.sandbox import Sandbox

def main():
    print("=" * 65)
    print("🚀 [AIOS Orchestrator] Generating Advanced Scenarios with Beam 501B")
    print("=" * 65)

    client = BeamClient()
    if not client.api_key:
        print("Error: REFLECTION_API_KEY is not set.")
        sys.exit(1)

    print(f"Connecting to Reflection AI API with model {client.model}...")
    prompt = """You are an expert Principal Python Engineer designing hard benchmark debugging scenarios.
Design Scenario 06: A distributed Token Bucket Rate Limiter with sliding window burst control.
Requirements:
1. Provide a buggy implementation in rate_limiter.py with subtle concurrency/math bugs:
   - Does not replenish tokens properly based on elapsed time
   - Drops remainder fractional tokens leading to premature rejection
   - Lacks proper thread/coroutine safety or burst limit enforcement
2. Provide a strict unittest test suite in tests/test_rate_limiter.py:
   - Tests initial capacity
   - Tests consumption and rejection when limit is reached
   - Tests replenishment over simulated time
   - Tests burst capacity handling
Return a JSON object with keys:
"title", "difficulty", "description", "test_command", "buggy_code", "test_code", "solution_code".
Output ONLY valid JSON.
"""

    resp = client.chat_complete(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000,
        temperature=0.2
    )

    print(f"Beam response received! Reasoning tokens: {resp.usage.reasoning_tokens}, Total tokens: {resp.usage.total_tokens}")
    out_file = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "beam_generated_scenario_06.json")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(resp.content)
    print(f"Saved Beam scenario draft to {out_file}")

if __name__ == "__main__":
    main()
