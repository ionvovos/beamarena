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
    test_command="python3 -m unittest tests.test_auth",
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
    test_command="python3 -m unittest tests.test_wallet",
    files={
        "tests/__init__.py": "# tests package\n",
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
    test_command="python3 -m unittest tests.test_transformer",
    files={
        "tests/__init__.py": "# tests package\n",
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


SCENARIO_04_CACHE_BUS = Scenario(
    id="04_cache_invalidation",
    title="Event Bus Cache Invalidation & Stale Entity State",
    difficulty="Hard",
    description="The multi-file event bus fails to evict tagged cache entries when user records are updated across modules. Fix cache.py and event_bus.py so that tests/test_cache.py passes.",
    test_command="python3 -m unittest tests.test_cache",
    files={
        "tests/__init__.py": "# tests package\n",
        "event_bus.py": """from typing import Callable, Dict, List

class EventBus:
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def publish(self, event_type: str, payload: dict):
        # BUG: Fails to pass payload or ignores event subscribers if not registered
        if event_type in self.subscribers:
            for cb in self.subscribers[event_type]:
                cb()
""",
        "cache.py": """from typing import Any, Dict, Optional

class TaggedCache:
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._tags: Dict[str, set] = {}

    def set(self, key: str, value: Any, tags: Optional[list] = None):
        self._store[key] = value
        if tags:
            for t in tags:
                if t not in self._tags:
                    self._tags[t] = set()
                self._tags[t].add(key)

    def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def invalidate_tag(self, tag: str):
        # BUG: Only clears the tag registry but does not remove keys from _store
        if tag in self._tags:
            self._tags[tag].clear()
""",
        "service.py": """from event_bus import EventBus
from cache import TaggedCache

bus = EventBus()
cache = TaggedCache()

def setup_listeners():
    def on_user_updated(payload=None):
        # Invalidate all user-tagged cache entries
        cache.invalidate_tag("users")

    bus.subscribe("user_updated", on_user_updated)

def update_user(user_id: str, new_name: str):
    # Mutates user and notifies bus
    bus.publish("user_updated", {"user_id": user_id, "name": new_name})
""",
        "tests/test_cache.py": """import unittest
from event_bus import EventBus
from cache import TaggedCache
import service

class TestTaggedCache(unittest.TestCase):
    def setUp(self):
        service.cache = TaggedCache()
        service.bus = EventBus()
        service.setup_listeners()

    def test_cache_invalidation_on_event(self):
        service.cache.set("user:101", {"name": "Alice"}, tags=["users"])
        self.assertEqual(service.cache.get("user:101")["name"], "Alice")

        # Update user triggers invalidation
        service.update_user("user:101", "Alice New")
        self.assertIsNone(service.cache.get("user:101"))

if __name__ == "__main__":
    unittest.main()
"""
    }
)


SCENARIO_05_REGISTRY = Scenario(
    id="05_plugin_dependency_order",
    title="Topological Dependency Ordering & Circular Dependency Detection",
    difficulty="Hard",
    description="The PluginRegistry executes plugins in random order and enters infinite recursion on circular dependencies. Fix registry.py so that tests/test_registry.py passes.",
    test_command="python3 -m unittest tests.test_registry",
    files={
        "tests/__init__.py": "# tests package\n",
        "registry.py": """from typing import Dict, List, Set

class CircularDependencyError(Exception):
    pass

class PluginRegistry:
    def __init__(self):
        self.plugins: Dict[str, List[str]] = {}

    def register(self, name: str, depends_on: List[str] = None):
        self.plugins[name] = depends_on or []

    def get_load_order(self) -> List[str]:
        # BUG: Simple dict iteration does not sort by dependency,
        # and has no circular dependency detection
        return list(self.plugins.keys())
""",
        "tests/test_registry.py": """import unittest
from registry import PluginRegistry, CircularDependencyError

class TestRegistry(unittest.TestCase):
    def test_dependency_resolution(self):
        reg = PluginRegistry()
        reg.register("auth", depends_on=["db"])
        reg.register("db", depends_on=[])
        reg.register("api", depends_on=["auth"])
        
        order = reg.get_load_order()
        self.assertEqual(order, ["db", "auth", "api"])

    def test_circular_dependency_detection(self):
        reg = PluginRegistry()
        reg.register("A", depends_on=["B"])
        reg.register("B", depends_on=["A"])
        with self.assertRaises(CircularDependencyError):
            reg.get_load_order()

if __name__ == "__main__":
    unittest.main()
"""
    }
)


ALL_SCENARIOS = {
    SCENARIO_01_AUTH.id: SCENARIO_01_AUTH,
    SCENARIO_02_WALLET.id: SCENARIO_02_WALLET,
    SCENARIO_03_TRANSFORM.id: SCENARIO_03_TRANSFORM,
    SCENARIO_04_CACHE_BUS.id: SCENARIO_04_CACHE_BUS,
    SCENARIO_05_REGISTRY.id: SCENARIO_05_REGISTRY,
}
