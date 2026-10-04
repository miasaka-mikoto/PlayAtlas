import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoreContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "data/games/GAME_CATALOG.json").read_text(encoding="utf-8"))

    def test_catalogue_has_36_unique_games(self):
        games = self.catalog["games"]
        self.assertEqual(len(games), 36)
        ids = [game["id"] for game in games]
        self.assertEqual(len(ids), len(set(ids)))

    def test_families_have_expected_counts(self):
        games = self.catalog["games"]
        counts = {}
        for game in games:
            counts[game["game_family"]] = counts.get(game["game_family"], 0) + 1
        self.assertEqual(counts, {"arcade": 2, "puzzle": 6, "board": 8, "cards": 8, "traditional": 8, "table_physics": 4})

    def test_required_metadata(self):
        for game in self.catalog["games"]:
            for key in ("id", "title", "title_zh", "status", "ruleset_id", "ruleset_version", "players"):
                self.assertIn(key, game, game.get("id"))

    def test_sources_are_explicit_and_nonempty(self):
        sources = json.loads((ROOT / "data/rules/rules_sources.json").read_text(encoding="utf-8"))
        records = sources.get("sources", sources.get("entries", []))
        self.assertTrue(records)
        for record in records:
            self.assertTrue(record.get("source_id"))
            self.assertTrue(record.get("source_url"))
            self.assertIn(record.get("verification_status"), {
                "verified_url", "verified_but_secondary", "needs_research", "not_a_rule_source"
            })


if __name__ == "__main__":
    unittest.main()
