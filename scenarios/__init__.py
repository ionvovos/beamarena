"""Pre-baked Real-World Benchmark Scenarios for BeamArena."""

from dataclasses import dataclass
from typing import Dict


@dataclass
class Scenario:
    id: str
    title: str
    difficulty: str  # "Easy", "Medium", "Hard"
    description: str
    test_command: str
    files: Dict[str, str]


SCENARIO_01_AUTH = Scenario(
    id="01_fastapi_auth",
    title="Broken JWT Claim Decoding & Expiry Handling",
    difficulty="Easy",
    description="The authentication module fails when validating expired tokens and misparses user role claims. Fix auth.py so that all tests in tests/test_auth.py pass.",
    test_command="python3 -m unittest tests/test_auth.py",
    files={
        "tests/__init__.py": "# tests package\n",
        "auth.py": """import base64
import json
import time

SECRET_KEY = "super-secret"

class AuthError(Exception):
    pass

def decode_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Invalid token format")
    
    # BUG 1: Missing padding handling in base64 decode
    payload_raw = base64.urlsafe_b64decode(parts[1])
    payload = json.loads(payload_raw.decode("utf-8"))
    
    # BUG 2: Incorrect expiration check (uses > instead of <= or wrong comparison)
    current_time = time.time()
    if payload.get("exp", 0) > current_time:
        raise AuthError("Token has expired")
        
    return payload

def has_role(payload: dict, required_role: str) -> bool:
    # BUG 3: roles can be a list or a single string, but code assumes single string
    user_role = payload.get("roles")
    return user_role == required_role
""",
        "tests/test_auth.py": """import base64
import json
import time
import unittest
from auth import decode_token, has_role, AuthError

def make_token(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode("utf-8").rstrip("=")
    payload_str = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
    return f"{header}.{payload_str}.signature"

class TestAuth(unittest.TestCase):
    def test_valid_token(self):
        token = make_token({"sub": "user_123", "exp": time.time() + 3600, "roles": ["admin", "editor"]})
        decoded = decode_token(token)
        self.assertEqual(decoded["sub"], "user_123")

    def test_expired_token(self):
        token = make_token({"sub": "user_123", "exp": time.time() - 3600, "roles": ["user"]})
        with self.assertRaises(AuthError):
            decode_token(token)

    def test_role_verification_list(self):
        payload = {"roles": ["admin", "editor"]}
        self.assertTrue(has_role(payload, "admin"))
        self.assertTrue(has_role(payload, "editor"))
        self.assertFalse(has_role(payload, "billing"))

    def test_role_verification_single(self):
        payload = {"roles": "viewer"}
        self.assertTrue(has_role(payload, "viewer"))
        self.assertFalse(has_role(payload, "admin"))

if __name__ == "__main__":
    unittest.main()
"""
    }
)


SCENARIO_02_WALLET = Scenario(
    id="02_async_wallet_balance",
    title="Wallet Balance Concurrent Overdraft Race Condition",
    difficulty="Medium",
    description="The Wallet manager allows concurrent transactions to overdraw an account because it lacks proper locking synchronization. Fix wallet.py so that tests/test_wallet.py passes.",
    test_command="python3 -m unittest tests/test_wallet.py",
    files={
        "wallet.py": """import asyncio

class InsufficientFundsError(Exception):
    pass

class Wallet:
    def __init__(self, initial_balance: float = 0.0):
        self.balance = initial_balance
        # BUG: Missing asyncio.Lock to synchronize concurrent transfers
        
    async def deposit(self, amount: float):
        if amount <= 0:
            raise ValueError("Deposit must be positive")
        self.balance += amount
        return self.balance
        
    async def withdraw(self, amount: float):
        # Simulated async I/O delay revealing race conditions
        current = self.balance
        await asyncio.sleep(0.01)
        if current < amount:
            raise InsufficientFundsError("Not enough funds")
        self.balance = current - amount
        return self.balance
""",
        "tests/test_wallet.py": """import asyncio
import unittest
from wallet import Wallet, InsufficientFundsError

class TestWallet(unittest.TestCase):
    def test_concurrent_withdrawals(self):
        async def run_test():
            w = Wallet(initial_balance=100.0)
            # Try 5 withdrawals of 30.0 each (total 150.0). Only 3 should succeed!
            results = await asyncio.gather(
                *[w.withdraw(30.0) for _ in range(5)],
                return_exceptions=True
            )
            successes = [r for r in results if not isinstance(r, Exception)]
            errors = [r for r in results if isinstance(r, InsufficientFundsError)]
            
            self.assertEqual(len(successes), 3)
            self.assertEqual(len(errors), 2)
            self.assertEqual(w.balance, 10.0)

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
"""
    }
)


SCENARIO_03_TRANSFORM = Scenario(
    id="03_sql_data_transform",
    title="Pipeline Schema Type Mismatch & Null Safety",
    difficulty="Medium",
    description="The data transformer crashes when encountered with missing fields or null values, and converts ISO timestamps inconsistently. Fix transformer.py so that tests/test_transformer.py passes.",
    test_command="python3 -m unittest tests/test_transformer.py",
    files={
        "transformer.py": """from datetime import datetime, timezone
from typing import Dict, Any, Optional

def transform_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    # BUG 1: Crashes with KeyError if 'id' or 'amount' is missing or null
    record_id = int(raw["id"])
    
    # BUG 2: Float conversion fails if amount is a currency string like '$123.45'
    amount = float(raw["amount"])
    
    # BUG 3: Does not handle timezone-aware vs naive timestamp formatting
    ts = raw.get("timestamp")
    formatted_ts = None
    if ts:
        dt = datetime.fromisoformat(ts)
        formatted_ts = dt.strftime("%Y-%m-%d %H:%M:%S")
        
    return {
        "id": record_id,
        "amount": round(amount, 2),
        "status": raw.get("status", "pending").lower(),
        "timestamp": formatted_ts
    }
""",
        "tests/test_transformer.py": """import unittest
from transformer import transform_record

class TestTransformer(unittest.TestCase):
    def test_clean_record(self):
        raw = {"id": 101, "amount": 49.99, "status": "COMPLETED", "timestamp": "2026-10-22T14:30:00"}
        res = transform_record(raw)
        self.assertEqual(res["id"], 101)
        self.assertEqual(res["amount"], 49.99)
        self.assertEqual(res["status"], "completed")

    def test_currency_string_and_nulls(self):
        raw = {"id": "202", "amount": "$1,250.50", "status": None}
        res = transform_record(raw)
        self.assertEqual(res["id"], 202)
        self.assertEqual(res["amount"], 1250.50)
        self.assertEqual(res["status"], "pending")

    def test_missing_id_defaults(self):
        raw = {"amount": "10.0"}
        res = transform_record(raw)
        self.assertIsNone(res["id"])
        self.assertEqual(res["amount"], 10.0)

if __name__ == "__main__":
    unittest.main()
"""
    }
)

ALL_SCENARIOS = {
    SCENARIO_01_AUTH.id: SCENARIO_01_AUTH,
    SCENARIO_02_WALLET.id: SCENARIO_02_WALLET,
    SCENARIO_03_TRANSFORM.id: SCENARIO_03_TRANSFORM,
}
