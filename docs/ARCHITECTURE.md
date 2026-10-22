# BeamArena System Architecture

**BeamArena** is an autonomous self-healing software engineering environment and empirical benchmark gym built for the **Reflection AI × Hugging Face Beam Build Challenge**. It leverages **Beam-1.0-501B-A23B** (Sparse MoE: 501B total, 23B active parameters per token, 1,048,576 token context window) to ingest codebases without chunking loss and repair software failures through test-driven self-correction.

```
                    ┌─────────────────────────┐
                    │     Codebase / Repo     │
                    └────────────┬────────────┘
                                 │ Ingest
                                 ▼
                     ┌───────────────────────┐
                     │   RepoIngestor (AST)  │
                     │  1M Context Packer    │
                     └───────────┬───────────┘
                                 │ Packed XML Prompt
                                 ▼
                    ┌─────────────────────────┐
                    │  Beam-1.0-501B-A23B     │◄───────────────────┐
                    │ (Reflection AI API)     │                    │
                    └────────────┬────────────┘                    │
                                 │ Streaming Reasoning & Edits     │
                                 ▼                                 │
                     ┌───────────────────────┐                     │
                     │ ToolParser & Executor │                     │
                     └───────────┬───────────┘                     │
                                 │ Apply Patches                   │
                                 ▼                                 │
                     ┌───────────────────────┐                     │
                     │   Isolated Sandbox    │                     │
                     │  (Sanitized Subproc)  │                     │
                     └───────────┬───────────┘                     │
                                 │ Run Test Verification           │
                                 ▼                                 │
                      [ Tests Pass / Fail? ]                       │
                           │           │                           │
                   Pass    │           │ Fail                      │
                   ────────┘           └────── Traceback / STDERR ─┘
```

---

## Core Components

### 1. Client & Telemetry (`core/client.py`)
- Communicates directly with `api.reflection.ai/openai/v1` using native Server-Sent Events (SSE).
- Extracts Beam's Chain-of-Thought (`reasoning_content`) separately from final content (`content`).
- Captures token usage telemetry (`prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `total_tokens`).
- Implements exponential backoff retries (up to 3 attempts) for transient 429/503 HTTP errors.
- Restores verified TLS/SSL validation (`ssl.create_default_context()`) with controlled fallback.

### 2. Sandbox Execution Engine (`core/sandbox.py`)
- Creates isolated temporary execution environments for applying patches and executing tests.
- **Environment Scrubbing:** Strips host environment variables matching `*KEY*`, `*TOKEN*`, `*SECRET*`, `*PASS*`, `*CRED*`, `*AUTH*`, ensuring credentials like `REFLECTION_API_KEY` never leak to executing code.
- **Path Traversal Protection:** Validates target paths using `os.path.realpath` and `os.path.commonpath` against the sandbox root.
- **Bytecode Isolation:** Enforces `PYTHONDONTWRITEBYTECODE=1` so multi-turn modifications are immediately recompiled without stale `.pyc` caching errors.
- **Timeout Enforcement:** Subprocesses are killed if execution exceeds timeout limits (default 15s).

### 3. Self-Healing Agent Loop (`core/agent.py`)
- Implements an autonomous test-driven repair loop:
  1. Inspects codebase files and test command requirements.
  2. Submits structured prompt to Beam enforcing `<edit_file>` blocks and verification commands.
  3. Executes edits inside the isolated sandbox.
  4. Runs the test command. If green, terminates successfully.
  5. If failing, captures standard output, standard error, and exit codes, constructs reinforcement feedback, and queries Beam again.
- Implements `solve_stream` generator yielding real-time turn events for non-blocking UI rendering.
- Automatically saves serialized run traces to `benchmarks/traces.jsonl`.

### 4. 1M Context Repository Packer (`core/ingest.py`)
- Scans full directory trees, filters ignored files, binaries, and sensitive credential formats (`*.pem`, `*.key`, `.env*`).
- Uses Python `ast` to parse high-level symbol trees (classes, async/sync functions, line numbers, docstrings).
- Packs the entire repository into a structured XML representation capable of occupying up to 1,048,576 tokens without chunking loss.

---

## Empirical Benchmark Suite (`scenarios/`)

The repository includes 10 benchmark scenarios spanning real-world engineering challenges:

| Scenario | Domain | Difficulty | Bug Description |
|---|---|---|---|
| `01_fastapi_auth` | Web Auth & JWT | Easy | Base64 padding errors, inverted expiration timestamps, and role claim misparsing. |
| `02_async_wallet_balance` | Concurrency & Locks | Medium | Async overdraft race condition due to missing `asyncio.Lock` synchronization. |
| `03_sql_data_transform` | Data Pipelines & Types | Medium | Unhandled null fields, currency string conversions, and timezone-naive formatting. |
| `04_cache_invalidation` | Event Bus & Cache | Hard | Tagged cache fails to evict mutated entity keys upon event bus publication. |
| `05_plugin_dependency_order` | Topological Sort & Cycles | Hard | Plugin registry lacks topological dependency sorting and circular reference detection. |
| `06_distributed_rate_limiter` | Token Bucket & Clock Drift | Hard | Token bucket rate limiter drops fractional tokens and fails burst capacity under simulated time. |
| `07_websocket_backoff` | Network Backoff & Jitter | Medium | WebSocket client computes fixed backoff without jitter and drops pending unacked message queue. |
| `08_db_pool_leak` | Resource Pool & Leak Prevention | Medium | Database connection pool fails to reclaim connections on exceptions inside context manager. |
| `09_event_schema_evolution` | Schema Evolution & Compatibility | Hard | Event migration fails on legacy v1 payloads missing optional metadata and skips intermediate version steps. |
| `10_memory_bounded_stream` | Backpressure & Stream Memory | Hard | Stream pipeline exhausts memory buffer on large generator payloads and fails backpressure triggers. |

---

## Empirical Results

Measured against **Beam-1.0-501B-A23B** on 2026-10-22:

- **Pass Rate:** 100% (10/10 scenarios resolved).
- **Pass@1:** 20% (2/10 on first attempt).
- **Pass@2:** 80% (8/10 resolved on self-healing retry).
- **Average Repair Latency:** 5.55 seconds.
- **Average Reasoning Tokens:** 962 tokens per task.
- **Trace Dataset:** Serialized traces with multi-turn CoT reasoning chains published in `benchmarks/traces.jsonl`.
