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

    def test_tiered_achievement_can_be_discovered_without_unlocking(self):
        definition = {
            "id": "terminal_goblin",
            "threshold_metric": "total_terminal_calls",
            "tiers": [{"name": "Copper", "threshold": 50}],
        }
        aggregate = {"total_terminal_calls": 12}

        result = plugin_api.evaluate_tiered(definition, aggregate)

        self.assertIs(result["unlocked"], False)
        self.assertIs(result["discovered"], True)
        self.assertEqual(result["state"], "discovered")
        self.assertEqual(result["progress"], 12)
        self.assertEqual(result["next_threshold"], 50)

    def test_secret_achievement_stays_hidden_without_progress(self):
        definition = {
            "id": "permission_denied_any_percent",
            "name": "Permission Denied Any%",
            "secret": True,
            "requirements": [{"metric": "permission_denied_events", "gte": 3}],
        }
        aggregate = {"permission_denied_events": 0}

        result = plugin_api.evaluate_requirements(definition, aggregate)
        display = plugin_api.display_achievement({**definition, **result})

        self.assertEqual(result["state"], "secret")
        self.assertEqual(display["name"], "???")
        self.assertNotIn("Permission", display["description"])

    def test_multi_condition_unlock_requires_all_requirements(self):
        definition = {
            "id": "full_send",
            "requirements": [
                {"metric": "max_terminal_calls_in_session", "gte": 10},
                {"metric": "max_file_tool_calls_in_session", "gte": 5},
                {"metric": "max_web_calls_in_session", "gte": 2},
            ],
        }

        partial = plugin_api.evaluate_requirements(definition, {
            "max_terminal_calls_in_session": 12,
            "max_file_tool_calls_in_session": 2,
            "max_web_calls_in_session": 0,
        })
        complete = plugin_api.evaluate_requirements(definition, {
            "max_terminal_calls_in_session": 12,
            "max_file_tool_calls_in_session": 6,
            "max_web_calls_in_session": 2,
        })

        self.assertEqual(partial["state"], "discovered")
        self.assertIs(partial["unlocked"], False)
        self.assertLess(partial["progress_pct"], 100)
        self.assertEqual(complete["state"], "unlocked")
        self.assertIs(complete["unlocked"], True)


if __name__ == "__main__":
    unittest.main()
