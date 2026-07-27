from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class CiWorkflowContractTests(unittest.TestCase):
    def test_official_javascript_actions_use_node24_majors(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        expected_counts = {
            "actions/checkout@v7": 4,
            "actions/setup-node@v7": 1,
            "actions/setup-python@v7": 2,
            "gitleaks/gitleaks-action@v3": 1,
        }
        legacy_actions = (
            "actions/checkout@v4",
            "actions/setup-node@v4",
            "actions/setup-python@v5",
            "gitleaks/gitleaks-action@v2",
        )

        for action, expected_count in expected_counts.items():
            with self.subTest(action=action):
                self.assertEqual(workflow.count(action), expected_count)
        for action in legacy_actions:
            with self.subTest(legacy_action=action):
                self.assertNotIn(action, workflow)


if __name__ == "__main__":
    unittest.main()
