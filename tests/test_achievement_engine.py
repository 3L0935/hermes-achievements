import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "plugin_api.py"
spec = importlib.util.spec_from_file_location("plugin_api", MODULE_PATH)
plugin_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin_api)


class AchievementEngineTests(unittest.TestCase):
    def test_tool_call_stats_detect_tool_names_and_errors(self):
        messages = [
            {"role": "assistant", "tool_calls": [{"function": {"name": "terminal"}}]},
            {"role": "tool", "tool_name": "terminal", "content": "Error: port 3000 already in use"},
            {"role": "assistant", "tool_calls": [{"function": {"name": "web_search"}}]},
        ]

        stats = plugin_api.analyze_messages("s1", "Fix dev server", messages)

        self.assertEqual(stats["tool_call_count"], 2)
        self.assertEqual(stats["tool_names"], {"terminal", "web_search"})
        self.assertEqual(stats["error_count"], 1)
        self.assertIs(stats["port_conflict"], True)

    def test_tiered_achievement_reaches_highest_matching_tier(self):
        definition = {
            "id": "let_him_cook",
            "threshold_metric": "max_tool_calls_in_session",
            "tiers": [
                {"name": "Copper", "threshold": 10},
                {"name": "Silver", "threshold": 25},
                {"name": "Gold", "threshold": 50},
            ],
        }
        aggregate = {"max_tool_calls_in_session": 28}

        result = plugin_api.evaluate_tiered(definition, aggregate)

        self.assertIs(result["unlocked"], True)
        self.assertEqual(result["tier"], "Silver")
        self.assertEqual(result["progress"], 28)
        self.assertEqual(result["next_tier"], "Gold")

    def test_boolean_achievement_unlocks_when_metric_truthy(self):
        definition = {"id": "port_3000", "metric": "saw_port_conflict"}
        aggregate = {"saw_port_conflict": True}

        result = plugin_api.evaluate_boolean(definition, aggregate)

        self.assertIs(result["unlocked"], True)
        self.assertEqual(result["progress"], 1)


if __name__ == "__main__":
    unittest.main()
