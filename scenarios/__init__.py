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



SCENARIO_06_RATE_LIMITER = Scenario(
    id="06_distributed_rate_limiter",
    title="Token Bucket Rate Limiter with Sliding Window Burst Control",
    difficulty="Hard",
    description="The TokenBucketRateLimiter drops fractional tokens and fails burst capacity enforcement. Fix rate_limiter.py so that tests/test_rate_limiter.py passes.",
    test_command="python3 -m unittest tests.test_rate_limiter",
    files={
        "tests/__init__.py": "# tests\n",
        "rate_limiter.py": "import time\n\nclass TokenBucketRateLimiter:\n    def __init__(self, capacity, refill_rate, burst_capacity=None, clock=time.monotonic):\n        self.capacity = capacity\n        self.refill_rate = refill_rate\n        self.burst_capacity = burst_capacity or capacity\n        self.clock = clock\n        self.tokens = self.capacity\n        self.last_refill = self.clock()\n\n    def allow(self, tokens=1, now=None):\n        if now is None:\n            now = self.clock()\n\n        elapsed = now - self.last_refill\n        if elapsed > 0:\n            self.tokens += int(elapsed * self.refill_rate)\n            if self.tokens > self.capacity:\n                self.tokens = self.capacity\n            self.last_refill = now\n\n        if tokens <= self.tokens:\n            self.tokens -= tokens\n            return True\n        return False\n",
        "tests/test_rate_limiter.py": "import unittest\nfrom rate_limiter import TokenBucketRateLimiter\n\nclass TestTokenBucketRateLimiter(unittest.TestCase):\n    def test_initial_capacity(self):\n        limiter = TokenBucketRateLimiter(capacity=3, refill_rate=1, clock=lambda: 0.0)\n        for _ in range(3):\n            self.assertTrue(limiter.allow())\n        self.assertFalse(limiter.allow())\n\n    def test_consumption_and_rejection(self):\n        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=1, clock=lambda: 0.0)\n        self.assertTrue(limiter.allow(2))\n        self.assertTrue(limiter.allow(2))\n        self.assertFalse(limiter.allow(2))\n        self.assertTrue(limiter.allow(1))\n\n    def test_replenishment_over_simulated_time(self):\n        limiter = TokenBucketRateLimiter(capacity=2, refill_rate=2, clock=lambda: 0.0)\n        self.assertTrue(limiter.allow(2))\n        self.assertFalse(limiter.allow(1))\n        self.assertTrue(limiter.allow(1, now=0.5))\n        self.assertFalse(limiter.allow(1, now=0.5))\n        self.assertTrue(limiter.allow(1, now=1.0))\n\n    def test_burst_capacity_handling(self):\n        limiter = TokenBucketRateLimiter(\n            capacity=1, refill_rate=1, burst_capacity=4, clock=lambda: 0.0\n        )\n        for _ in range(4):\n            self.assertTrue(limiter.allow())\n        self.assertFalse(limiter.allow())\n\nif __name__ == '__main__':\n    unittest.main()\n"
}
)


SCENARIO_07_WEBSOCKET = Scenario(
    id="07_websocket_backoff",
    title="WebSocket Exponential Backoff with Jitter and Reconnect Replay",
    difficulty="Medium",
    description="A WebSocket client must compute bounded exponential backoff with jitter, replay unacknowledged messages after reconnect, and reset its failure counter after a successful connection.",
    test_command="python3 -m unittest tests.test_client",
    files={
        "tests/__init__.py": "",
        "client.py": "import random\n\n\nclass WebSocketClient:\n    def __init__(self, base_delay=1.0, max_backoff=30.0, jitter=0.0, rng=None):\n        self.base_delay = base_delay\n        self.max_backoff = max_backoff\n        self.jitter = jitter\n        self.rng = rng if rng is not None else random.Random()\n        self.consecutive_failures = 0\n        self.pending_messages = []\n        self.unacknowledged = []\n        self.connected = False\n\n    def compute_backoff(self, attempt=None):\n        if attempt is None:\n            attempt = self.consecutive_failures\n        delay = self.base_delay * (2 ** attempt)\n        if delay > self.max_backoff:\n            delay = self.max_backoff\n        # BUG: jitter is ignored.\n        return delay\n\n    def connect(self):\n        self.connected = True\n        # BUG: consecutive_failures is never reset.\n        return True\n\n    def disconnect(self):\n        self.connected = False\n        self.consecutive_failures += 1\n\n    def send(self, message):\n        if not self.connected:\n            raise RuntimeError(\"client is not connected\")\n        self.pending_messages.append(message)\n        self.unacknowledged.append(message)\n\n    def acknowledge(self, message):\n        if message in self.unacknowledged:\n            self.unacknowledged.remove(message)\n\n    def reconnect(self):\n        self.connected = False\n        # BUG: unacknowledged messages are dropped instead of being re-queued.\n        return self.connect()\n",
        "tests/test_client.py": "import random\nimport unittest\n\nfrom client import WebSocketClient\n\n\nclass TestWebSocketClient(unittest.TestCase):\n    def test_compute_backoff_uses_jitter_and_respects_max(self):\n        first_rng = random.Random(1)\n        second_rng = random.Random(2)\n        first_client = WebSocketClient(\n            base_delay=2.0, max_backoff=5.0, jitter=1.0, rng=first_rng\n        )\n        second_client = WebSocketClient(\n            base_delay=2.0, max_backoff=5.0, jitter=1.0, rng=second_rng\n        )\n\n        first_delay = first_client.compute_backoff(0)\n        second_delay = second_client.compute_backoff(0)\n\n        self.assertNotEqual(first_delay, second_delay)\n        self.assertGreaterEqual(first_delay, 2.0)\n        self.assertLessEqual(first_delay, 3.0)\n        self.assertLessEqual(\n            first_client.compute_backoff(10), first_client.max_backoff\n        )\n\n    def test_reconnect_requeues_unacknowledged_messages(self):\n        client = WebSocketClient()\n        client.connect()\n        client.send(\"message-1\")\n        client.send(\"message-2\")\n        client.acknowledge(\"message-1\")\n\n        client.disconnect()\n        client.reconnect()\n\n        self.assertTrue(client.connected)\n        self.assertIn(\"message-2\", client.pending_messages)\n        self.assertEqual(client.unacknowledged, [])\n\n    def test_successful_connect_resets_failure_counter(self):\n        client = WebSocketClient()\n        client.consecutive_failures = 4\n        client.connect()\n        self.assertEqual(client.consecutive_failures, 0)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
}
)


SCENARIO_08_POOL = Scenario(
    id="08_async_resource_db_pool_context_manager_leak_prevention",
    title="Async Resource / DB Pool Context Manager Leak Prevention",
    difficulty="Medium",
    description="Fix an async connection pool so acquired connections are released even when exceptions occur, exhausted pools raise PoolExhaustedError instead of deadlocking, and the checked-out gauge is decremented on release.",
    test_command="python3 -m unittest tests.test_pool",
    files={
        "tests/__init__.py": "",
        "pool.py": "import asyncio\nfrom contextlib import asynccontextmanager\n\n\nclass PoolExhaustedError(Exception):\n    \"\"\"Raised when no connection becomes available before timeout.\"\"\"\n    pass\n\n\nclass ConnectionPool:\n    def __init__(self, factory, max_size=2, acquire_timeout=0.1):\n        self.factory = factory\n        self.max_size = max_size\n        self.acquire_timeout = acquire_timeout\n        self._available = asyncio.Queue(maxsize=max_size)\n        self._size = 0\n        self._checked_out = 0\n        self._lock = asyncio.Lock()\n\n    @property\n    def checked_out(self):\n        return self._checked_out\n\n    @asynccontextmanager\n    async def acquire(self, timeout=None):\n        conn = await self._acquire(timeout)\n        self._checked_out += 1\n        yield conn\n        await self._release(conn)\n\n    async def _acquire(self, timeout):\n        async with self._lock:\n            if self._size < self.max_size:\n                conn = await self.factory()\n                self._size += 1\n                return conn\n\n        if timeout is None:\n            timeout = self.acquire_timeout\n\n        # BUG: timeout is accepted but never applied, so an exhausted pool waits forever.\n        return await self._available.get()\n\n    async def _release(self, conn):\n        await self._available.put(conn)\n        # BUG: the checked-out gauge is never decremented.\n",
        "tests/test_pool.py": "import asyncio\nimport unittest\n\nfrom pool import ConnectionPool, PoolExhaustedError\n\n\nasync def make_connection():\n    return object()\n\n\nclass TestConnectionPool(unittest.IsolatedAsyncioTestCase):\n    async def test_release_on_exception(self):\n        pool = ConnectionPool(make_connection, max_size=1)\n\n        with self.assertRaises(ValueError):\n            async with pool.acquire():\n                raise ValueError(\"boom\")\n\n        self.assertEqual(pool.checked_out, 0)\n\n        async with pool.acquire() as conn:\n            self.assertIsNotNone(conn)\n\n    async def test_timeout_when_exhausted(self):\n        pool = ConnectionPool(make_connection, max_size=1)\n\n        async def attempt():\n            async with pool.acquire(timeout=0.05):\n                pass\n\n        async with pool.acquire():\n            with self.assertRaises(PoolExhaustedError):\n                await asyncio.wait_for(attempt(), timeout=0.2)\n\n    async def test_checked_out_gauge_decremented(self):\n        pool = ConnectionPool(make_connection, max_size=2)\n\n        async with pool.acquire():\n            self.assertEqual(pool.checked_out, 1)\n\n        self.assertEqual(pool.checked_out, 0)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
}
)


SCENARIO_09_MIGRATION = Scenario(
    id="09_event_schema_evolution",
    title="Event Schema Evolution and Backward Compatibility Migration",
    difficulty="Hard",
    description="Fix event payload migration so optional legacy fields do not raise KeyError, numeric IDs are coerced recursively throughout nested payloads, and schema migrations apply every intermediate transform in version order.",
    test_command="python3 -m unittest tests.test_migrator",
    files={
        "tests/__init__.py": "",
        "migrator.py": "VERSIONS = [\"v1\", \"v1.1\", \"v2\"]\n\n\ndef transform_v1_to_v1_1(payload):\n    result = dict(payload)\n    result.setdefault(\"metadata\", {})\n    result.setdefault(\"created_at\", None)\n    result[\"v1_1_applied\"] = True\n    return result\n\n\ndef transform_v1_1_to_v2(payload):\n    result = dict(payload)\n    result[\"schema_version\"] = \"v2\"\n    result[\"v2_applied\"] = True\n    return result\n\n\nTRANSFORMS = {\n    (\"v1\", \"v1.1\"): transform_v1_to_v1_1,\n    (\"v1.1\", \"v2\"): transform_v1_1_to_v2,\n}\n\n\ndef coerce_numeric_ids(payload):\n    # BUG: only coerces a few top-level keys and ignores nested values.\n    result = dict(payload)\n    for key in (\"event_id\", \"user_id\"):\n        if key in result and isinstance(result[key], str) and result[key].isdigit():\n            result[key] = int(result[key])\n    return result\n\n\ndef migrate_payload(payload, from_version=\"v1\", to_version=\"v2\"):\n    # BUG: accesses optional fields directly and skips intermediate transforms.\n    result = dict(payload)\n    result[\"metadata\"] = payload[\"metadata\"]\n    result[\"created_at\"] = payload[\"created_at\"]\n    result[\"schema_version\"] = to_version\n    return coerce_numeric_ids(result)\n",
        "tests/test_migrator.py": "import unittest\n\nfrom migrator import coerce_numeric_ids, migrate_payload\n\n\nclass TestMigrator(unittest.TestCase):\n    def test_missing_optional_fields_do_not_raise(self):\n        payload = {\"event_id\": \"1\", \"type\": \"created\"}\n        result = migrate_payload(payload)\n\n        self.assertEqual(result[\"metadata\"], {})\n        self.assertIsNone(result[\"created_at\"])\n        self.assertEqual(result[\"schema_version\"], \"v2\")\n        self.assertTrue(result[\"v1_1_applied\"])\n        self.assertTrue(result[\"v2_applied\"])\n\n    def test_nested_numeric_ids_are_coerced(self):\n        payload = {\n            \"event_id\": \"123\",\n            \"data\": {\n                \"user_id\": \"456\",\n                \"items\": [{\"id\": \"789\"}, {\"id\": \"not-a-number\"}],\n            },\n        }\n        result = coerce_numeric_ids(payload)\n\n        self.assertEqual(result[\"event_id\"], 123)\n        self.assertEqual(result[\"data\"][\"user_id\"], 456)\n        self.assertEqual(result[\"data\"][\"items\"][0][\"id\"], 789)\n        self.assertEqual(result[\"data\"][\"items\"][1][\"id\"], \"not-a-number\")\n\n    def test_migration_applies_intermediate_transforms(self):\n        payload = {\"event_id\": \"9\", \"metadata\": {\"source\": \"legacy\"}}\n        result = migrate_payload(payload)\n\n        self.assertEqual(result[\"event_id\"], 9)\n        self.assertEqual(result[\"metadata\"], {\"source\": \"legacy\"})\n        self.assertTrue(result[\"v1_1_applied\"])\n        self.assertTrue(result[\"v2_applied\"])\n        self.assertEqual(result[\"schema_version\"], \"v2\")\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
}
)


SCENARIO_10_PIPELINE = Scenario(
    id="10_memory_bounded_chunked_stream_pipeline",
    title="Memory-Bounded Chunked Stream Pipeline with Backpressure",
    difficulty="Hard",
    description="A streaming pipeline must transform input in bounded chunks, invoke backpressure when a chunk reaches the configured buffer size, and aggregate byte/text chunks into complete records using record delimiters rather than fixed-size truncation.",
    test_command="python3 -m unittest tests.test_pipeline",
    files={
        "tests/__init__.py": "",
        "pipeline.py": "import collections\n\n\ndef stream_transform(source, transform, max_buffer_size=4, backpressure_callback=None):\n    \"\"\"Transform a source stream in bounded chunks.\n\n    The buggy implementation materializes the entire source before yielding.\n    \"\"\"\n    # BUG: loads the whole input generator into memory before yielding.\n    data = list(source)\n    buffer = []\n    for item in data:\n        buffer.append(item)\n        if len(buffer) >= max_buffer_size:\n            if backpressure_callback is not None:\n                backpressure_callback()\n            for buffered_item in buffer:\n                yield transform(buffered_item)\n            buffer.clear()\n    for buffered_item in buffer:\n        yield transform(buffered_item)\n\n\ndef aggregate_chunks(chunks, delimiter=\"\\n\", chunk_size=8):\n    \"\"\"Aggregate chunks into records.\n\n    The buggy implementation slices fixed-size pieces and can split records.\n    \"\"\"\n    buffer = \"\"\n    for chunk in chunks:\n        buffer += chunk\n        # BUG: truncates at an arbitrary fixed size instead of delimiter.\n        while len(buffer) >= chunk_size:\n            yield buffer[:chunk_size]\n            buffer = buffer[chunk_size:]\n    if buffer:\n        yield buffer\n",
        "tests/test_pipeline.py": "import unittest\nfrom pipeline import stream_transform, aggregate_chunks\n\n\nclass TestPipeline(unittest.TestCase):\n    def test_stream_transform_does_not_materialize_entire_source(self):\n        consumed = []\n\n        def source():\n            for value in range(1000):\n                consumed.append(value)\n                yield value\n\n        transformed = list(stream_transform(source(), lambda x: x * 2, max_buffer_size=4))\n        self.assertEqual(transformed, [x * 2 for x in range(1000)])\n        self.assertEqual(len(consumed), 1000)\n\n    def test_backpressure_callback_is_triggered(self):\n        calls = []\n\n        def source():\n            for value in range(10):\n                yield value\n\n        result = list(\n            stream_transform(\n                source(),\n                lambda x: x,\n                max_buffer_size=3,\n                backpressure_callback=lambda: calls.append(1),\n            )\n        )\n        self.assertEqual(result, list(range(10)))\n        self.assertEqual(len(calls), 3)\n\n    def test_aggregate_chunks_respects_delimiters(self):\n        chunks = [\"hel\", \"lo\\nwor\", \"ld\\n\"]\n        records = list(aggregate_chunks(chunks, delimiter=\"\\n\"))\n        self.assertEqual(records, [\"hello\", \"world\"])\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n"
}
)


ALL_SCENARIOS = {
    SCENARIO_01_AUTH.id: SCENARIO_01_AUTH,
    SCENARIO_02_WALLET.id: SCENARIO_02_WALLET,
    SCENARIO_03_TRANSFORM.id: SCENARIO_03_TRANSFORM,
    SCENARIO_04_CACHE_BUS.id: SCENARIO_04_CACHE_BUS,
    SCENARIO_05_REGISTRY.id: SCENARIO_05_REGISTRY,
    SCENARIO_06_RATE_LIMITER.id: SCENARIO_06_RATE_LIMITER,
    SCENARIO_07_WEBSOCKET.id: SCENARIO_07_WEBSOCKET,
    SCENARIO_08_POOL.id: SCENARIO_08_POOL,
    SCENARIO_09_MIGRATION.id: SCENARIO_09_MIGRATION,
    SCENARIO_10_PIPELINE.id: SCENARIO_10_PIPELINE,
}

