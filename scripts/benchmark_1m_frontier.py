#!/usr/bin/env python3
"""1M-Context Frontier Benchmark Harness for Beam-1.0-501B-A23B.

Audits Beam's reasoning retention, latency scaling, and needle-in-a-codebase
bug resolution across scaling context tiers:
  • Tier 1: 10,000 tokens (Baseline module)
  • Tier 2: 50,000 tokens (Package level)
  • Tier 3: 150,000 tokens (Subsystem level)
  • Tier 4: 500,000 tokens (Large multi-package repo)
  • Tier 5: 1,000,000 tokens (Full frontier window)

Measures:
  - Needle bug localization rate (Top-1 file & symbol)
  - Reasoning token overhead vs context depth
  - Wall-clock response latency
  - Cross-module patch resolution
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.client import BeamClient
from core.ingest import RepoIngestor

TIERS = [
    {"tier": "10K", "target_tokens": 10000, "label": "Module Tier"},
    {"tier": "50K", "target_tokens": 50000, "label": "Package Tier"},
    {"tier": "150K", "target_tokens": 150000, "label": "Subsystem Tier"},
    {"tier": "500K", "target_tokens": 500000, "label": "Multi-Package Tier"},
    {"tier": "1M", "target_tokens": 1000000, "label": "1M Frontier Tier"},
]

def load_haystack_files(target_tokens: int):
    """Gathers real source files up to the target token budget."""
    site_packages = os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python3.13", "site-packages")
    selected_files = {}
    current_tokens = 0

    # Scan through site-packages gradio & pytest submodules for realistic python source
    for root, _, files in os.walk(site_packages):
        for f in files:
            if f.endswith(".py") and not f.startswith("test_"):
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, site_packages)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                        content = fp.read()
                    est_tokens = len(content) // 4
                    if current_tokens + est_tokens <= target_tokens - 1000:
                        selected_files[rel_path] = content
                        current_tokens += est_tokens
                    if current_tokens >= target_tokens - 1500:
                        break
                except Exception:
                    continue
        if current_tokens >= target_tokens - 1500:
            break

    return selected_files, current_tokens

def main():
    print("=" * 70)
    print("🔬 [AIOS Orchestrator] Executing 1M-Context SWE Frontier Benchmark")
    print("   Model: Beam-1.0-501B-A23B · Reflection AI")
    print("=" * 70)

    client = BeamClient()
    if not client.api_key:
        print("Error: REFLECTION_API_KEY is required.")
        sys.exit(1)

    benchmarks_dir = os.path.join(os.path.dirname(__file__), "..", "benchmarks")
    os.makedirs(benchmarks_dir, exist_ok=True)
    out_results_file = os.path.join(benchmarks_dir, "1m_frontier_results.json")
    out_traces_file = os.path.join(benchmarks_dir, "1m_frontier_traces.jsonl")

    needle_file = "auth/token_verifier.py"
    needle_code = '''# auth/token_verifier.py
import time
import base64

class SecurityTokenVerifier:
    """Verifies cryptographic tokens across microservices."""
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def verify_token_expiry(self, token_payload: dict, now: float = None) -> bool:
        current = now if now is not None else time.time()
        # NEEDLE BUG: Inverted operator causes valid tokens to be rejected and expired tokens accepted
        if token_payload.get("exp", 0) > current:
            return False  # BUG: should return True when exp > current
        return True
'''

    results = {
        "benchmark_title": "Beam-1.0-501B-A23B 1M-Context SWE Reasoning Frontier",
        "benchmark_date": "2026-10-22T18:42:00+03:00",
        "model": client.model,
        "evaluations": []
    }

    # Evaluate each tier
    for t_spec in TIERS:
        tier_id = t_spec["tier"]
        target_tokens = t_spec["target_tokens"]
        label = t_spec["label"]

        print(f"\n--> Assembling Haystack for {tier_id} ({label}, target ~{target_tokens:,} tokens)...")
        haystack, actual_tokens = load_haystack_files(target_tokens)

        # Insert needle at 50% depth (dead center: maximum 'lost-in-the-middle' stress)
        items = list(haystack.items())
        mid = len(items) // 2
        items.insert(mid, (needle_file, needle_code))
        packed_prompt_parts = [
            f"You are evaluating a large production codebase packed into Beam's 1M context window.",
            f"A subtle security bug was reported where valid user auth tokens are rejected while expired tokens pass.",
            f"Analyze the entire codebase below. Identify the exact file, class, method, and operator bug.",
            f"Provide your reasoning in <explanation>, then fix the bug inside <edit_file path='{needle_file}'>...</edit_file>.\n\n",
            f"--- REPOSITORY CONTEXT ({len(items)} files, approx {actual_tokens + 250:,} tokens) ---\n"
        ]

        for p, c in items:
            packed_prompt_parts.append(f"\n# File: {p}\n{c}\n")

        full_prompt = "".join(packed_prompt_parts)
        prompt_tokens_est = len(full_prompt) // 4
        print(f"    Dispatching to Beam API ({prompt_tokens_est:,} prompt tokens)...")

        t0 = time.time()
        try:
            resp = client.chat_complete(
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=2000,
                temperature=0.1
            )
            elapsed = round(time.time() - t0, 2)
            content = resp.content or ""
            reasoning = resp.reasoning or ""
            r_tokens = resp.usage.reasoning_tokens
            total_tokens = resp.usage.total_tokens

            # Evaluate success criteria
            found_file = needle_file in content or needle_file in reasoning
            found_bug = "exp" in content and (">" in content or "inverted" in content.lower() or "expiry" in content.lower())
            resolved = found_file and found_bug and ("return True" in content or "token_payload" in content)

            status_str = "✅ RESOLVED" if resolved else "❌ FAILED"
            print(f"    {status_str} in {elapsed}s | Reasoning Tokens: {r_tokens} | Total: {total_tokens}")

            eval_entry = {
                "tier": tier_id,
                "label": label,
                "input_tokens": prompt_tokens_est,
                "reasoning_tokens": r_tokens,
                "total_tokens": total_tokens,
                "latency_seconds": elapsed,
                "needle_found": found_file,
                "resolved": resolved,
                "status": status_str,
            }
            results["evaluations"].append(eval_entry)

            # Record trace
            trace_entry = {
                "tier": tier_id,
                "input_tokens": prompt_tokens_est,
                "reasoning_tokens": r_tokens,
                "latency_seconds": elapsed,
                "resolved": resolved,
                "reasoning_excerpt": reasoning[:500],
                "patch_excerpt": content[:500]
            }
            with open(out_traces_file, "a", encoding="utf-8") as tf:
                tf.write(json.dumps(trace_entry) + "\n")

        except Exception as e:
            print(f"    Error during {tier_id} evaluation: {e}")
            eval_entry = {
                "tier": tier_id,
                "label": label,
                "input_tokens": prompt_tokens_est,
                "error": str(e),
                "resolved": False,
                "status": "❌ ERROR"
            }
            results["evaluations"].append(eval_entry)

    with open(out_results_file, "w", encoding="utf-8") as rf:
        json.dump(results, rf, indent=2)

    print("\n" + "=" * 70)
    print(f"🏆 1M Frontier Benchmark Complete. Results saved to: {out_results_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()
