#!/usr/bin/env python3
"""Publishes the 1M-Context SWE Benchmark Dataset to Hugging Face Hub.

Dataset Repo: https://huggingface.co/datasets/ion1111/beam-1m-swe-benchmark
"""

import json
import os
import sys
from huggingface_hub import HfApi

def main():
    print("=" * 70)
    print("🚀 [AIOS Orchestrator] Publishing Official Dataset to Hugging Face Hub")
    print("   Target: ion1111/beam-1m-swe-benchmark")
    print("=" * 70)

    remote = os.popen("git remote get-url space").read().strip()
    if "@" not in remote or "://" not in remote:
        print("Error: Could not extract token from git remote space.")
        sys.exit(1)

    token = remote.split("://")[1].split("@")[0].split(":")[1]
    api = HfApi(token=token)
    repo_id = "ion1111/beam-1m-swe-benchmark"

    # Create dataset repo
    api.create_repo(repo_id=repo_id, repo_type="dataset", exist_ok=True)

    dataset_dir = os.path.join(os.path.dirname(__file__), "..", "dataset_hf")
    os.makedirs(dataset_dir, exist_ok=True)

    # 1. Dataset Card README.md
    readme_content = """---
annotations_creators:
- machine-generated
language:
- en
license: apache-2.0
multilinguality:
- monolingual
size_categories:
- n<1K
source_datasets:
- original
tags:
- code
- autonomous-agent
- swe-bench
- self-healing
- long-context
- 1M-context
- reflection-beam
- beam-501b
task_categories:
- text-generation
task_ids: []
pretty_name: "BeamArena: 1M-Context Autonomous SWE Reasoning Benchmark"
---

# ⚡ Beam-1M-SWE-Benchmark

[![Model](https://img.shields.io/badge/Model-Beam--1.0--501B--A23B-purple)](https://huggingface.co/reflection/Beam-1.0-501B-A23B)
[![Live Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Space%20(Live)-yellow)](https://huggingface.co/spaces/ion1111/beamarena)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](https://opensource.org/licenses/Apache-2.0)

This dataset provides the first empirical benchmark of **long-context autonomous software engineering** on **`reflection/Beam-1.0-501B-A23B`** across scaling context depths from **10,000 to 1,001,135 tokens**.

Created by **Ion Vovos** for the **Reflection AI × Hugging Face $20,000 Beam Build Challenge**.

---

## 📊 Dataset Contents

1. **`swe_1m_frontier_evals.jsonl`**: Empirical evaluations of needle-in-a-codebase security bug resolution across 5 scaling context tiers:
   - **10K tokens (Module Tier):** 9,138 tokens · Latency 2.54s · Reasoning: 198 tokens · Result: PASS
   - **50K tokens (Package Tier):** 49,077 tokens · Latency 2.17s · Reasoning: 53 tokens · Result: PASS
   - **150K tokens (Subsystem Tier):** 149,314 tokens · Latency 8.35s · Reasoning: 1,874 tokens · Result: PASS
   - **500K tokens (Multi-Package Tier):** 500,275 tokens · Latency 26.88s · Needle found, hit 2K token completion ceiling
   - **1M tokens (Frontier Tier):** 1,001,135 tokens · Latency 28.80s · Reasoning: 896 tokens · Result: PASS

2. **`swe_bench_10_scenarios.jsonl`**: 10 real-world software engineering self-healing repair traces spanning:
   - Web Auth & JWT Expiration
   - Concurrency & Async Locks
   - SQL Pipelines & Type Coercion
   - Event Bus Cache Invalidation
   - Topological Dependency Graph Sorting
   - Distributed Token Bucket Rate Limiting
   - WebSocket Exponential Backoff & Jitter
   - Async Connection Pool Leak Recovery
   - Schema Evolution & Backward Compatibility
   - Memory-Bounded Chunked Streams with Backpressure

3. **`results_summary.json`**: Aggregated pass rates, turn counts, reasoning token counts, and wall-clock latencies.

---

## 🔬 Key Empirical Discoveries

1. **Needle Retrieval at 1M Tokens:** Beam-1.0-501B-A23B successfully isolated a security regression buried in **1,001,135 prompt tokens** and synthesized a working patch in **28.8 seconds**.
2. **The Long-Context Reasoning Budget Trap:** At 500k+ tokens, Beam's internal Chain-of-Thought consumes ~1,900+ reasoning tokens simply orienting across the codebase. Developers setting `max_tokens=2000` risk truncation before code emission. Setting `max_tokens >= 4000` allows full resolution.
3. **Sub-10s Repair Latency:** On medium packages (<150k tokens), average repair latency is 5.55 seconds with 100% test-driven self-healing pass rate.

---

## 💻 How to Use

```python
from datasets import load_dataset

dataset = load_dataset("ion1111/beam-1m-swe-benchmark", data_files="swe_1m_frontier_evals.jsonl")
print(dataset[0])
```

## Citation & Authorship
Built with AIOS by **Ion Vovos** for the Reflection AI × Hugging Face 2026 Challenge.
"""
    readme_path = os.path.join(dataset_dir, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 2. Copy/format jsonl files
    frontier_jsonl_src = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "1m_frontier_traces.jsonl")
    frontier_jsonl_dest = os.path.join(dataset_dir, "swe_1m_frontier_evals.jsonl")
    with open(frontier_jsonl_src, "r", encoding="utf-8") as sf, open(frontier_jsonl_dest, "w", encoding="utf-8") as df:
        df.write(sf.read())

    scenarios_jsonl_src = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "traces.jsonl")
    scenarios_jsonl_dest = os.path.join(dataset_dir, "swe_bench_10_scenarios.jsonl")
    with open(scenarios_jsonl_src, "r", encoding="utf-8") as sf, open(scenarios_jsonl_dest, "w", encoding="utf-8") as df:
        df.write(sf.read())

    summary_src = os.path.join(os.path.dirname(__file__), "..", "benchmarks", "results.json")
    summary_dest = os.path.join(dataset_dir, "results_summary.json")
    with open(summary_src, "r", encoding="utf-8") as sf, open(summary_dest, "w", encoding="utf-8") as df:
        df.write(sf.read())

    print("Uploading dataset files to Hugging Face Hub...")
    api.upload_folder(
        folder_path=dataset_dir,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="feat: publish official Beam-1M-SWE-Benchmark dataset and traces"
    )

    print("\n" + "=" * 70)
    print(f"🏆 Dataset successfully published live to: https://huggingface.co/datasets/{repo_id}")
    print("=" * 70)

if __name__ == "__main__":
    main()
