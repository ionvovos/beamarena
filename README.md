---
title: BeamArena
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 5.0.0
python_version: "3.11"
app_file: app.py
pinned: false
license: apache-2.0
short_description: 1M-Context Autonomous Coding & Self-Healing Gym on Beam 501B
---

# ⚡ BeamArena — 1M-Context Autonomous Coding & Self-Healing Gym

> Built for the **Reflection AI × Hugging Face $20,000 Beam Build Challenge**.  
> Powered by **`reflection/Beam-1.0-501B-A23B`** (Sparse MoE: 501B total, 23B active per token, 1,048,576 token context).

[![GitHub Repo](https://img.shields.io/badge/GitHub-ionvovos%2Fbeamarena-blue?logo=github)](https://github.com/ionvovos/beamarena)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](https://opensource.org/licenses/Apache-2.0)
[![Model](https://img.shields.io/badge/Model-Beam--1.0--501B--A23B-purple)](https://huggingface.co/reflection/Beam-1.0-501B-A23B)

## What is BeamArena?

BeamArena turns Beam into a full-cycle, test-driven **Autonomous Software Engineer**:
1. **1M-Token Zero-Loss Ingestion:** Ingests entire repositories, dependency graphs, and AST structures without chunking decay.
2. **Reinforcement-Learning Self-Correction Loop:** Executes sandboxed terminal commands, parses execution tracebacks, reasons through errors, and self-corrects until tests pass.
3. **Real-Time Reasoning Visualizer:** Streams Beam's internal Chain-of-Thought (`reasoning_content`) alongside sandboxed execution logs and syntax-highlighted git diffs.
4. **Empirical Benchmark Arena:** Measures multi-turn self-healing pass rates and reasoning token efficiency on real-world coding problems.

## Architecture

- `app.py`: Gradio 5 interactive web interface.
- `core/agent.py`: Multi-turn self-healing state machine.
- `core/client.py`: Reflection API client with real-time reasoning streaming.
- `core/sandbox.py`: Isolated subprocess execution sandbox with timeout safety.
- `core/ingest.py`: 1M-context repository packer and AST parser.
- `scenarios/`: Real-world benchmark scenarios (FastAPI auth, Asyncio race conditions, Data pipeline transformations).

## Local Quickstart

```bash
git clone https://github.com/ionvovos/beamarena.git
cd beamarena
uv venv && uv pip install -r requirements.txt
export REFLECTION_API_KEY="your-key-here"

# Run live autonomous repair demo
python3 examples/live_agent_demo.py

# Launch local Web UI
python3 app.py
```
