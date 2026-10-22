#!/usr/bin/env python3
"""Automated Benchmark Evaluation Harness for BeamArena.

Executes autonomous self-healing repair runs across all 5 benchmark scenarios
using the live Reflection AI API (Beam-1.0-501B-A23B), records latency, token telemetry,
and turns-to-green, and generates benchmarks/results.json.
"""

import json
import os
import sys
import time

# Ensure core and scenarios can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.client import BeamClient
from core.sandbox import Sandbox
from core.agent import AutonomousCodingAgent
from scenarios import ALL_SCENARIOS


def run_benchmark():
    results = {
        "benchmark_timestamp": "2026-10-22T17:32:00+03:00",
        "model": "Beam-1.0-501B-A23B",
        "benchmarks": []
    }

    client = BeamClient()
    benchmarks_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    os.makedirs(benchmarks_dir, exist_ok=True)

    domains = {
        "01_fastapi_auth": "Web Auth & JWT",
        "02_async_wallet_balance": "Concurrency & Locks",
        "03_sql_data_transform": "Data Pipelines & Types",
        "04_cache_invalidation": "Event Bus & Cache",
        "05_plugin_dependency_order": "Topological Sort & Cycles",
        "06_distributed_rate_limiter": "Token Bucket & Clock Drift",
        "07_websocket_reconnect_backoff": "Network Backoff & Jitter",
        "08_db_connection_pool_leak": "Resource Pool & Leak Prevention",
        "09_schema_migration_backward_compat": "Schema Evolution & Compatibility",
        "10_memory_bounded_stream_pipeline": "Backpressure & Stream Memory",
    }

    print("=" * 65)
    print("🚀 [BeamArena] Executing Live Benchmark Suite (Beam 501B)")
    print("=" * 65)

    for scen_id, scen in ALL_SCENARIOS.items():
        print(f"\nEvaluating {scen_id} ({scen.difficulty})...")
        agent = AutonomousCodingAgent(client=client, max_turns=3)

        with Sandbox() as sb:
            sb.load_files(scen.files)
            trace = agent.solve(
                task_description=scen.description,
                sandbox=sb,
                test_command=scen.test_command,
                scenario_id=scen.id
            )

        status_str = f"✅ PASS@{len(trace.turns)}" if trace.resolved else "❌ FAIL"
        entry = {
            "scenario_id": scen.id,
            "domain": domains.get(scen.id, "General"),
            "difficulty": scen.difficulty,
            "turns_to_green": len(trace.turns),
            "reasoning_tokens": trace.total_reasoning_tokens,
            "total_tokens": trace.total_tokens,
            "latency_seconds": trace.wall_clock_seconds,
            "status": status_str,
            "resolved": trace.resolved,
        }
        results["benchmarks"].append(entry)
        print(f" -> {status_str} in {trace.wall_clock_seconds}s | Reasoning Tokens: {trace.total_reasoning_tokens}")

    results_file = os.path.join(benchmarks_dir, "results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 65)
    print(f"🏆 Benchmark complete. Saved empirical data to: {results_file}")
    print("=" * 65)


if __name__ == "__main__":
    run_benchmark()
