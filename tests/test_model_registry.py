import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from core.model_registry import ModelRegistry, REQUIRED_SLOTS  # noqa: E402


class ModelRegistryTest(unittest.TestCase):
    def test_loads_all_slots_and_gets_asr(self):
        registry = ModelRegistry.load()

        self.assertEqual(set(registry.slots), set(REQUIRED_SLOTS))

        asr = registry.get_slot("asr")
        self.assertEqual(asr.name, "asr")
        self.assertEqual(asr.dev_model, "vosk-model-small-ru-0.22")
        self.assertEqual(asr.status, "development")
        self.assertEqual(asr.kpi["latency_p95_ms_max"], 1000)


if __name__ == "__main__":
    unittest.main()
