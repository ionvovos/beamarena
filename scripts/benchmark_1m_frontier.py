#!/usr/bin/env python3
"""1M-Context Frontier Benchmark Harness (BeamArena 2.0).

Audits Beam-1.0-501B-A23B on true un-leaked needle bug localization,
reasoning token overhead, latency scaling, and dynamic sandbox test execution across scaling context tiers:
  • Tier 1: 10,000 tokens (Module Tier)
  • Tier 2: 50,000 tokens (Package Tier)
  • Tier 3: 150,000 tokens (Subsystem Tier)
  • Tier 4: 500,000 tokens (Multi-Package Tier)
  • Tier 5: 1,000,000 tokens (1M Frontier Tier)

Key Upgrades in 2.0:
1. Zero Prompt Leaks: The prompt does NOT specify the needle file path.
2. Clean Needle: Source code contains zero bug-revealing comments.
3. Dynamic Sandbox Execution: Verification executes real unit tests via Sandbox and AIOS Triple Gate.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.client import BeamClient
from core.sandbox import Sandbox
from core.tools import ToolParser, ToolExecutor
from core.validator import TripleValidator

TIERS = [
    {"tier": "10K", "target_tokens": 10000, "label": "Module Tier"},
    {"tier": "50K", "target_tokens": 50000, "label": "Package Tier"},
    {"tier": "150K", "target_tokens": 150000, "label": "Subsystem Tier"},
    {"tier": "500K", "target_tokens": 500000, "label": "Multi-Package Tier"},
    {"tier": "1M", "target_tokens": 1000000, "label": "1M Frontier Tier"},
]

VERIFICATION_TEST_CODE = """import time
import unittest
from auth.token_verifier import SecurityTokenVerifier

class TestVerifier(unittest.TestCase):
    def test_valid_token_passes(self):
        v = SecurityTokenVerifier("secret")
        self.assertTrue(v.verify_token_expiry({"exp": time.time() + 3600}))

    def test_expired_token_fails(self):
        v = SecurityTokenVerifier("secret")
        self.assertFalse(v.verify_token_expiry({"exp": time.time() - 3600}))

if __name__ == "__main__":
    unittest.main()
"""

def load_haystack_files(target_tokens: int):
    """Gathers real Python source files up to target token budget."""
    site_packages = os.path.join(os.path.dirname(__file__), "..", ".venv", "lib", "python3.13", "site-packages")
    selected_files = {}
    current_tokens = 0

    if not os.path.exists(site_packages):
        # Fallback to local codebase files if venv path differs
        site_packages = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    for root, _, files in os.walk(site_packages):
        for f in files:
            if f.endswith(".py") and not f.startswith("test_") and not f.startswith("."):
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
    print("🔬 [BeamArena 2.0] Executing Un-Leaked 1M Frontier SWE Benchmark")
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
    # Clean needle with zero bug comments
    needle_code = '''# auth/token_verifier.py
import time
import base64

class SecurityTokenVerifier:
    """Verifies cryptographic tokens across microservices."""
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def verify_token_expiry(self, token_payload: dict, now: float = None) -> bool:
        current = now if now is not None else time.time()
        if token_payload.get("exp", 0) > current:
            return False
        return True
'''

    results = {
        "benchmark_title": "Beam-1.0-501B-A23B 1M-Context SWE Reasoning Frontier (BeamArena 2.0)",
        "benchmark_date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": client.model,
        "evaluations": []
    }

    parser = ToolParser()

    for t_spec in TIERS:
        tier_id = t_spec["tier"]
        target_tokens = t_spec["target_tokens"]
        label = t_spec["label"]

        print(f"\n--> Assembling Un-Leaked Haystack for {tier_id} ({label}, target ~{target_tokens:,} tokens)...")
        haystack, actual_tokens = load_haystack_files(target_tokens)

        # Insert needle at 50% depth (maximum 'lost-in-the-middle' stress)
        items = list(haystack.items())
        mid = len(items) // 2
        items.insert(mid, (needle_file, needle_code))

        # Un-leaked prompt: does NOT specify needle file path
        packed_prompt_parts = [
            "You are evaluating a large production repository packed into Beam's 1M context window.\n",
            "A subtle security regression was reported: cryptographic session token validation rejects active valid tokens while expired tokens pass.\n",
            "1. Analyze the codebase to locate which file and method implements token expiration verification.\n",
            "2. Provide your root-cause analysis in <explanation>...</explanation>.\n",
            "3. Emit the corrected file inside <edit_file path='...'>...</edit_file>.\n\n",
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
                max_tokens=4000,  # Ensure adequate headroom for 500K+ CoT reasoning
                temperature=0.1
            )
            elapsed = round(time.time() - t0, 2)
            content = resp.content or ""
            reasoning = resp.reasoning or ""
            r_tokens = resp.usage.reasoning_tokens
            total_tokens = resp.usage.total_tokens

            # Dynamic verification in Sandbox
            with Sandbox() as sb:
                sb.write_file("auth/__init__.py", "")
                sb.write_file("auth/token_verifier.py", needle_code)
                sb.write_file("test_verifier.py", VERIFICATION_TEST_CODE)

                plan = parser.parse(content)
                executor = ToolExecutor(sb)
                executor.apply_plan(plan)

                # Execute dynamic test
                test_res = sb.run_command(["python3", "-m", "unittest", "test_verifier.py"])
                validator = TripleValidator(sb)
                cert = validator.certify("python3 -m unittest test_verifier.py", ["auth/token_verifier.py"], [test_res])

                needle_localized = any("auth/token_verifier.py" in edit.file_path for edit in plan.file_edits)
                resolved = cert.certified and test_res.exit_code == 0

            status_str = f"✅ RESOLVED (Certified {cert.overall_confidence:.0f}%)" if resolved else "❌ FAILED"
            print(f"    {status_str} in {elapsed}s | Reasoning Tokens: {r_tokens} | Total: {total_tokens}")

            eval_entry = {
                "tier": tier_id,
                "label": label,
                "input_tokens": prompt_tokens_est,
                "reasoning_tokens": r_tokens,
                "total_tokens": total_tokens,
                "latency_seconds": elapsed,
                "needle_localized": needle_localized,
                "resolved": resolved,
                "certified": cert.certified,
                "confidence": cert.overall_confidence,
                "status": status_str,
            }
            results["evaluations"].append(eval_entry)

            trace_entry = {
                "tier": tier_id,
                "input_tokens": prompt_tokens_est,
                "reasoning_tokens": r_tokens,
                "latency_seconds": elapsed,
                "resolved": resolved,
                "needle_localized": needle_localized,
                "reasoning_excerpt": reasoning[:500],
                "patch_excerpt": content[:500],
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
    print(f"🏆 BeamArena 2.0 Frontier Benchmark Complete. Results: {out_results_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()
