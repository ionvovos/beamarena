import unittest
from core.sandbox import Sandbox
from scenarios import (
    SCENARIO_01_AUTH,
    SCENARIO_02_WALLET,
    SCENARIO_03_TRANSFORM,
    SCENARIO_04_CACHE_BUS,
    SCENARIO_05_REGISTRY,
)


class TestScenariosInitialBugs(unittest.TestCase):
    def test_scenario_01_fails_initially(self):
        """Confirms that the initial broken auth code indeed fails tests."""
        with Sandbox() as sb:
            sb.load_files(SCENARIO_01_AUTH.files)
            res = sb.run_command(SCENARIO_01_AUTH.test_command.split())
            self.assertNotEqual(res.exit_code, 0, "Scenario 1 should fail initially")

    def test_scenario_02_fails_initially(self):
        """Confirms that the initial broken wallet code indeed fails tests."""
        with Sandbox() as sb:
            sb.load_files(SCENARIO_02_WALLET.files)
            res = sb.run_command(SCENARIO_02_WALLET.test_command.split())
            self.assertNotEqual(res.exit_code, 0, "Scenario 2 should fail initially")

    def test_scenario_03_fails_initially(self):
        """Confirms that the initial broken transformer code indeed fails tests."""
        with Sandbox() as sb:
            sb.load_files(SCENARIO_03_TRANSFORM.files)
            res = sb.run_command(SCENARIO_03_TRANSFORM.test_command.split())
            self.assertNotEqual(res.exit_code, 0, "Scenario 3 should fail initially")

    def test_scenario_04_fails_initially(self):
        """Confirms that the initial broken cache bus code fails tests."""
        with Sandbox() as sb:
            sb.load_files(SCENARIO_04_CACHE_BUS.files)
            res = sb.run_command(SCENARIO_04_CACHE_BUS.test_command.split())
            self.assertNotEqual(res.exit_code, 0, "Scenario 4 should fail initially")

    def test_scenario_05_fails_initially(self):
        """Confirms that the initial broken registry code fails tests."""
        with Sandbox() as sb:
            sb.load_files(SCENARIO_05_REGISTRY.files)
            res = sb.run_command(SCENARIO_05_REGISTRY.test_command.split())
            self.assertNotEqual(res.exit_code, 0, "Scenario 5 should fail initially")


if __name__ == "__main__":
    unittest.main()
