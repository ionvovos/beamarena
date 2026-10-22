#!/usr/bin/env python3
import json
import os
import ssl
import sys
import urllib.request

# Load .env manually without external libraries
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

api_key = os.environ.get("REFLECTION_API_KEY")
base_url = os.environ.get("REFLECTION_BASE_URL", "https://api.reflection.ai/openai/v1")
model = os.environ.get("MODEL_NAME", "Beam-1.0-501B-A23B")

if not api_key:
    print("Error: REFLECTION_API_KEY not found in .env")
    sys.exit(1)

req_data = {
    "model": model,
    "messages": [
        {"role": "user", "content": "Explain in 2 sentences what makes you ideal for autonomous coding and long-context reasoning."}
    ],
    "max_tokens": 1000,
    "stream": False
}

req = urllib.request.Request(
    f"{base_url}/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    data=json.dumps(req_data).encode("utf-8")
)

print(f"Connecting to Reflection API ({model})...")
try:
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx) as resp:
        res = json.loads(resp.read().decode("utf-8"))
except Exception:
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, context=ctx) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        choice = res["choices"][0]["message"]
        print("\n--- Reasoning Content (Chain of Thought) ---")
        print(choice.get("reasoning_content", "(None)"))
        print("\n--- Final Content ---")
        print(choice.get("content", ""))
        print("\n--- Token Usage ---")
        print(json.dumps(res.get("usage", {}), indent=2))
except Exception as e:
    print(f"Error during request: {e}")
    sys.exit(1)
