from core.client import BeamClient
from scenarios import SCENARIO_01_AUTH

client = BeamClient()

prompt = f"""You are an autonomous software engineer.
Fix the bugs in auth.py so that tests/test_auth.py passes.

CURRENT FILES:
auth.py:
{SCENARIO_01_AUTH.files['auth.py']}

tests/test_auth.py:
{SCENARIO_01_AUTH.files['tests/test_auth.py']}

Provide the fixed auth.py inside <edit_file path="auth.py">...</edit_file>.
"""

print("Testing STREAMING with Beam...")
reasoning_chunks = []
content_chunks = []

resp = client.stream_chat(
    messages=[{"role": "user", "content": prompt}],
    max_tokens=16000,
    on_reasoning=lambda r: reasoning_chunks.append(r),
    on_content=lambda c: content_chunks.append(c)
)

print(f"\nReasoning Chunks: {len(reasoning_chunks)} (Length: {len(''.join(reasoning_chunks))})")
print(f"Content Chunks: {len(content_chunks)} (Length: {len(''.join(content_chunks))})")
print("\n--- CONTENT GENERATED ---")
print("".join(content_chunks))
