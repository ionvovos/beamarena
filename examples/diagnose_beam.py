import json
from core.client import BeamClient

client = BeamClient()

# Test 1: User prompt only
print("Test 1: User prompt only")
resp1 = client.chat_complete([
    {"role": "user", "content": "Write a python function to add two numbers. Format inside <edit_file path='add.py'>...</edit_file>"}
])
print("Resp 1 content:", repr(resp1.content)[:200])
print("Resp 1 reasoning:", repr(resp1.reasoning)[:200])

# Test 2: System prompt + User prompt
print("\nTest 2: System prompt + User prompt")
resp2 = client.chat_complete([
    {"role": "system", "content": "You are a coding assistant. Always output files inside <edit_file path='...'>...</edit_file>."},
    {"role": "user", "content": "Write a python function to add two numbers."}
])
print("Resp 2 content:", repr(resp2.content)[:200])
print("Resp 2 reasoning:", repr(resp2.reasoning)[:200])
