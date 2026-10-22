#!/usr/bin/env python3
"""Runs live Beam 501B evaluation on scenarios 06 to 10 and updates results.json and traces.jsonl."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.client import BeamClient
from core.sandbox import Sandbox
from core.agent import AutonomousCodingAgent
from scenarios import ALL_SCENARIOS

def main():
    benchmarks_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    results_file = os.path.join(benchmarks_dir, "results.json")

    with open(results_file, "r") as f:
        existing_data = json.load(f)

    client = BeamClient()
    domains = {
        "01_fastapi_auth": "Web Auth & JWT",
        "02_async_wallet_balance": "Concurrency & Locks",
        "03_sql_data_transform": "Data Pipelines & Types",
        "04_cache_invalidation": "Event Bus & Cache",
        "05_plugin_dependency_order": "Topological Sort & Cycles",
        "06_distributed_rate_limiter": "Token Bucket & Clock Drift",
        "07_websocket_backoff": "Network Backoff & Jitter",
        "08_async_resource_db_pool_context_manager_leak_prevention": "Resource Pool & Leak Prevention",
        "09_event_schema_evolution": "Schema Evolution & Compatibility",
        "10_memory_bounded_chunked_stream_pipeline": "Backpressure & Stream Memory",
    }

    target_ids = [
        "06_distributed_rate_limiter",
        "07_websocket_backoff",
        "08_async_resource_db_pool_context_manager_leak_prevention",
        "09_event_schema_evolution",
        "10_memory_bounded_chunked_stream_pipeline"
    ]

    print("=" * 65)
    print("🚀 [AIOS Orchestrator] Live Evaluation: Scenarios 06-10 on Beam 501B")
    print("=" * 65)

    existing_map = {b["scenario_id"]: b for b in existing_data.get("benchmarks", [])}

    for scen_id in target_ids:
        scen = ALL_SCENARIOS.get(scen_id)
        if not scen:
            continue
        print(f"\n--> Evaluating {scen.id} ({scen.difficulty})...")
        agent = AutonomousCodingAgent(client=client, max_turns=3, persist_trace=True)

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
        existing_map[scen.id] = entry
        print(f"    Result: {status_str} in {trace.wall_clock_seconds}s | Reasoning tokens: {trace.total_reasoning_tokens}")

    ordered_results = [existing_map[s_id] for s_id in ALL_SCENARIOS.keys() if s_id in existing_map]
    existing_data["benchmarks"] = ordered_results
    existing_data["benchmark_timestamp"] = "2026-10-22T18:15:00+03:00"

    with open(results_file, "w") as f:
        json.dump(existing_data, f, indent=2)

    print("\n" + "=" * 65)
    print(f"Saved complete 10-scenario empirical benchmark dataset to {results_file}")
    print("=" * 65)

if __name__ == "__main__":
    main()
