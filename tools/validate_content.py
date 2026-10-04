#!/usr/bin/env python3
"""Validate PlayAtlas catalog/source consistency without starting Godot."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "content" / "GAME_CATALOG.json"
RULES = ROOT / "content" / "rules_sources.json"
CONTENT = ROOT / "content" / "content_sources.json"
PARTY_CATALOG = ROOT / "content" / "PARTY_CATALOG.json"


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    errors: list[str] = []
    for path in (CATALOG, RULES, CONTENT, PARTY_CATALOG):
        if not path.is_file():
            errors.append(f"missing file: {path}")
    if errors:
        print("CONTENT_VALIDATION_FAIL")
        print("\n".join(errors))
        return 1

    catalog = load(CATALOG)
    rules = load(RULES)
    content = load(CONTENT)
    party_catalog = load(PARTY_CATALOG)

    games = catalog.get("games", [])
    game_ids = [game.get("game_id") for game in games]
    if len(games) != 36:
        errors.append(f"expected 36 catalog games, found {len(games)}")
    if len(set(game_ids)) != len(game_ids):
        errors.append("duplicate game_id")

    allowed_status = set(catalog.get("status_enum", {}))
    source_ids = {source.get("source_id") for source in rules.get("sources", [])}
    required_game_fields = {"game_id", "title_zh", "title_en", "game_family", "default_ruleset", "catalog_status", "playable_counted"}
    for game in games:
        missing = required_game_fields - set(game)
        if missing:
            errors.append(f"{game.get('game_id')}: missing fields {sorted(missing)}")
        status = game.get("catalog_status")
        if status not in allowed_status:
            errors.append(f"{game.get('game_id')}: invalid catalog_status={status}")
        if game.get("playable_counted") and status != "playable":
            errors.append(f"{game.get('game_id')}: playable_counted requires playable status")
        for source_id in game.get("default_ruleset", {}).get("source_ids", []):
            if source_id not in source_ids:
                errors.append(f"{game.get('game_id')}: unresolved source_id={source_id}")

    in_progress = [game for game in games if game.get("catalog_status") == "in_progress"]
    if len(in_progress) != 6:
        errors.append(f"expected six sample games in_progress, found {len(in_progress)}")
    if catalog.get("counting_policy", {}).get("current_playable_independent_game_count") != 0:
        errors.append("initial playable independent-game count must remain 0 until QA evidence is attached")

    if rules.get("generated_at") != "2026-10-04":
        errors.append("rules_sources generated_at must be 2026-10-04 for this snapshot")

    party_games = party_catalog.get("games", []) if isinstance(party_catalog, dict) else []
    if len(party_games) != 6:
        errors.append(f"expected six party expansion entries, found {len(party_games)}")
    party_ids = {game.get("game_id") for game in party_games if isinstance(game, dict)}
    for required in {"tank_battle", "uno", "upgrade_poker", "blackjack", "prize_reels", "prize_wheel"}:
        if required not in party_ids:
            errors.append(f"missing party expansion entry: {required}")
    for game in party_games:
        if not game.get("non_monetary", False) and game.get("game_family") == "party_chance_toy":
            errors.append(f"party chance toy must be non_monetary: {game.get('game_id')}")
        for source_id in game.get("source_ids", []):
            if source_id not in source_ids:
                errors.append(f"{game.get('game_id')}: unresolved party source_id={source_id}")

    if errors:
        print("CONTENT_VALIDATION_FAIL")
        print("\n".join(errors))
        return 1

    print("CONTENT_VALIDATION_PASS")
    print(f"games={len(games)} in_progress={len(in_progress)} playable_counted=0 sources={len(source_ids)} party_entries={len(party_games)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
