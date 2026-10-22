#!/usr/bin/env python3
"""Batch generates scenarios 09 and 10 using Beam-1.0-501B-A23B."""

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.client import BeamClient
from scripts.generate_scenarios_batch import generate_scenario

def main():
    client = BeamClient()
    benchmarks_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks")

    # 09: Schema Migration Backward Compatibility
    prompt_09 = """You are designing Scenario 09: Event Schema Evolution and Backward Compatibility Migration.
Buggy file: migrator.py. Unit test: tests/test_migrator.py.
Bugs in migrator.py:
1. migrate_payload() raises KeyError on legacy v1 payloads missing optional 'metadata' or 'created_at'.
2. Type coercion for numeric IDs (string vs integer) fails when nested inside event payload.
3. Schema version tag is updated to v2 without applying migration transform functions in sequential order (skips v1->v1.1 intermediate transform)."""
    generate_scenario(client, prompt_09, os.path.join(benchmarks_dir, "scenario_09_beam.json"))

    # 10: Memory Bounded Stream Pipeline with Backpressure
    prompt_10 = """You are designing Scenario 10: Memory-Bounded Chunked Stream Pipeline with Backpressure.
Buggy file: pipeline.py. Unit test: tests/test_pipeline.py.
Bugs in pipeline.py:
1. stream_transform() loads entire input generator into an in-memory list before yielding, causing memory spike / violation of max_buffer_size constraint.
2. Backpressure callback is never triggered when consumer lag occurs.
3. Chunk aggregator produces truncated partial records across chunk boundaries instead of slicing at record delimiters."""
    generate_scenario(client, prompt_10, os.path.join(benchmarks_dir, "scenario_10_beam.json"))

if __name__ == "__main__":
    main()
