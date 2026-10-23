---
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
configs:
- config_name: 1m_frontier_evals
  data_files:
  - split: train
    path: swe_1m_frontier_evals.jsonl
- config_name: swe_scenarios
  data_files:
  - split: train
    path: swe_bench_10_scenarios.jsonl
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
