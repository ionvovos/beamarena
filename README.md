---
title: BeamArena
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.30.0
app_file: app.py
pinned: false
license: apache-2.0
short_description: 1M-Context Autonomous Coding & Self-Healing Gym on Beam 501B
---

# ⚡ BeamArena — 1M-Context Autonomous Coding & Self-Healing Gym

> Candidate for the **Reflection AI × Hugging Face $20,000 Beam Build Challenge**.  
> Powered by **`reflection/Beam-1.0-501B-A23B`** (Sparse MoE: 501B total, 23B active per token, 1,048,576 token context window).

[![Live Hugging Face Space](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Space%20(Live)-yellow)](https://huggingface.co/spaces/ion1111/beamarena)
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset%20(Live)-blue)](https://huggingface.co/datasets/ion1111/beam-1m-swe-benchmark)
[![GitHub Repo](https://img.shields.io/badge/GitHub-ionvovos%2Fbeamarena-blue?logo=github)](https://github.com/ionvovos/beamarena)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Model](https://img.shields.io/badge/Model-Beam--1.0--501B--A23B-purple)](https://huggingface.co/reflection/Beam-1.0-501B-A23B)

---

## What is BeamArena?

BeamArena turns Beam into a full-cycle, test-driven **Autonomous Software Engineer**:

1. **1M-Token Context Reasoning Frontier:** Audits and benchmarks Beam across context depths from 10,000 to 1,001,135 tokens.
2. **Official Hugging Face Dataset:** Open-sourced evaluation dataset and CoT reasoning traces published at [`ion1111/beam-1m-swe-benchmark`](https://huggingface.co/datasets/ion1111/beam-1m-swe-benchmark).
3. **Reinforcement-Learning Self-Correction Loop:** Executes sandboxed terminal commands, parses execution tracebacks, reasons through errors, and self-corrects until tests pass.
4. **Interactive Custom Workspace & Ingestor:** Paste arbitrary code into the Space or run the `beam-swe` terminal tool directly in any local git repo.

---

## 🔬 The 1M-Context Reasoning Frontier (Empirical Benchmark)

Needle-in-a-codebase security bug localization and repair across scaling context sizes on **Beam-1.0-501B-A23B**:

| Context Tier | Scope | Prompt Tokens | Reasoning Tokens | Latency | Needle Found? | Status |
|---|---|---|---|---|---|---|
| **10K Tier** | Module | 9,138 | 198 | 2.54s | **YES** | **PASS** |
| **50K Tier** | Package | 49,077 | 53 | 2.17s | **YES** | **PASS** |
| **150K Tier** | Subsystem | 149,314 | 1,874 | 8.35s | **YES** | **PASS** |
| **500K Tier** | Multi-Package | 500,275 | 1,999 | 26.88s | **YES** | **BUDGET CEILING** |
| **1M Tier** | 1M Frontier | 1,001,135 | 896 | 28.80s | **YES** | **PASS** |

> **Key Discovery (The Long-Context Reasoning Ceiling):** At 500k+ tokens, Beam's Chain-of-Thought consumes ~1,900+ reasoning tokens orienting across repository files. Setting `max_tokens=2000` causes premature completion cutoff. Setting `max_tokens >= 4000` enables 100% resolution at 1,000,000 tokens in under 29 seconds.

---

## 📊 10-Scenario Multi-Turn Self-Healing Benchmark

Measured directly on **Beam-1.0-501B-A23B** (`api.reflection.ai`) across 10 real-world engineering scenarios:

| Scenario ID | Domain | Difficulty | Turns to Green | Reasoning Tokens | Total Tokens | Latency | Pass Status |
|---|---|---|---|---|---|---|---|
| `01_fastapi_auth` | Web Auth & JWT | Easy | 1 turn | 392 tokens | 1,589 tokens | 2.06s | **PASS@1** |
| `02_async_wallet_balance` | Concurrency & Locks | Medium | 1 turn | 272 tokens | 1,230 tokens | 2.28s | **PASS@1** |
| `03_sql_data_transform` | Data Pipelines & Types | Medium | 2 turns | 1,183 tokens | 5,164 tokens | 5.40s | **PASS@2** |
| `04_cache_invalidation` | Event Bus & Cache | Hard | 2 turns | 436 tokens | 3,641 tokens | 4.48s | **PASS@2** |
| `05_plugin_dependency_order` | Topological Sort & Cycles | Hard | 2 turns | 2,098 tokens | 6,108 tokens | 9.74s | **PASS@2** |
| `06_distributed_rate_limiter` | Token Bucket & Clock Drift | Hard | 2 turns | 1,654 tokens | 5,595 tokens | 10.42s | **PASS@2** |
| `07_websocket_backoff` | Network Backoff & Jitter | Medium | 2 turns | 1,362 tokens | 5,716 tokens | 6.49s | **PASS@2** |
| `08_db_pool_leak` | Resource Pool & Leak Prevention | Medium | 2 turns | 640 tokens | 4,854 tokens | 5.07s | **PASS@2** |
| `09_event_schema_evolution` | Schema Evolution & Compatibility | Hard | 2 turns | 1,068 tokens | 5,585 tokens | 6.34s | **PASS@2** |
| `10_memory_bounded_stream` | Backpressure & Stream Memory | Hard | 2 turns | 517 tokens | 3,379 tokens | 3.20s | **PASS@2** |

- **Overall Pass Rate:** 100% (10/10 scenarios resolved).
- **Average Repair Latency:** 5.55 seconds from traceback to green test assertions.
- **Average Reasoning Tokens:** 962 tokens per task.
- **Trace Dataset:** Full serialized traces with Beam reasoning chains are published in `benchmarks/traces.jsonl`.

---

## 🔒 Security & Containment Architecture

- **Subprocess Environment Scrubbing:** Strips host credentials (`REFLECTION_API_KEY`, tokens, and secrets) from the execution sandbox.
- **Strict Path Traversal Protection:** Verifies file writes and reads using `os.path.realpath` and `os.path.commonpath`.
- **Bytecode Isolation:** Sets `PYTHONDONTWRITEBYTECODE=1` to guarantee immediate recompilation without stale `.pyc` caching errors.
- **Timeout Enforcement:** Subprocesses terminate safely after 15 seconds.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for full system design details.

---

## 🚀 Quickstart

### 1. Installation
```bash
git clone https://github.com/ionvovos/beamarena.git
cd beamarena
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
export REFLECTION_API_KEY="your-reflection-api-key"
```

### 3. Run Autonomous Repair via CLI
```bash
# List available benchmark scenarios
python3 cli.py list

# Solve a scenario autonomously
python3 cli.py solve --scenario 01_fastapi_auth

# Ingest a codebase in 1M-context mode
python3 cli.py ingest core
```

### 4. Run Automated Benchmark Suite
```bash
python3 scripts/run_benchmarks.py
```

### 5. Launch Interactive Web UI
```bash
python3 app.py
```

---

## 📄 License

Apache License 2.0. Built by **Ion Vovos** for the Reflection AI × Hugging Face 2026 Challenge.
