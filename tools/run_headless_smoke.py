#!/usr/bin/env python3
"""Portable PlayAtlas core smoke test and preview server.

This runner intentionally uses only Python's standard library. It is useful on
machines where Godot is not installed yet: it validates the data contract,
catalogue, preview assets, and a small in-memory persistence round trip.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import socketserver
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "games" / "GAME_CATALOG.json"
PARTY_CATALOG = ROOT / "data" / "games" / "PARTY_CATALOG.json"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_catalogue() -> list[str]:
    errors: list[str] = []
    payload = read_json(CATALOG)
    games = payload.get("games") if isinstance(payload, dict) else None
    if not isinstance(games, list) or len(games) != 36:
        errors.append(f"catalogue must contain 36 games (found {len(games) if isinstance(games, list) else 'invalid'})")
        games = games if isinstance(games, list) else []
    ids: set[str] = set()
    for game in games:
        if not isinstance(game, dict):
            errors.append("catalogue entry is not an object")
            continue
        game_id = game.get("id")
        if not isinstance(game_id, str) or not game_id:
            errors.append("catalogue entry missing id")
        elif game_id in ids:
            errors.append(f"duplicate game id: {game_id}")
        ids.add(game_id)
        for field in ("title", "title_zh", "game_family", "status", "ruleset_id", "ruleset_version"):
            if not game.get(field):
                errors.append(f"{game_id or '<unknown>'}: missing {field}")
        players = game.get("players", {})
        if not isinstance(players, dict) or int(players.get("min", 0)) < 1 or int(players.get("max", 0)) < int(players.get("min", 0)):
            errors.append(f"{game_id or '<unknown>'}: invalid players range")
    return errors


def test_search() -> None:
    games = read_json(CATALOG)["games"]
    result = [g for g in games if "棋" in (g.get("title_zh", "") + g.get("title", ""))]
    assert {g["id"] for g in result} >= {"gomoku", "reversi", "xiangqi", "dots_and_boxes"}
    result = [g for g in games if g.get("game_family") == "traditional"]
    assert len(result) == 8


def test_save_round_trip() -> None:
    with tempfile.TemporaryDirectory(prefix="playatlas-smoke-") as tmp:
        path = Path(tmp) / "snake.json"
        payload = {"game_id": "snake", "save_schema_version": 1, "state": {"score": 42, "seed": 7}}
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert json.loads(path.read_text(encoding="utf-8")) == payload


def test_package_path_guard() -> None:
    safe = ["manifest.json", "data/level.json", "textures/icon.svg"]
    unsafe = ["../manifest.json", "/absolute", "data\\escape.json"]
    is_safe = lambda p: not Path(p).is_absolute() and ".." not in p and "\\" not in p
    assert all(is_safe(p) for p in safe)
    assert not any(is_safe(p) for p in unsafe)


def test_party_catalogue() -> None:
    payload = read_json(PARTY_CATALOG)
    games = payload.get("games") if isinstance(payload, dict) else None
    assert isinstance(games, list) and len(games) == 6
    ids = {str(game.get("id")) for game in games}
    assert {"tank_battle", "uno", "upgrade_poker", "blackjack", "prize_reels", "prize_wheel"} <= ids
    chance = [game for game in games if game.get("game_family") == "party_chance_toy"]
    assert chance and all(game.get("non_monetary", True) for game in chance)


def run_smoke() -> int:
    errors = validate_catalogue()
    try:
        test_search()
        test_save_round_trip()
        test_package_path_guard()
        test_party_catalogue()
    except AssertionError as exc:
        errors.append(f"assertion failed: {exc}")
    for required in (ROOT / "project.godot", ROOT / "preview" / "index.html", ROOT / "preview" / "party.html", ROOT / "preview" / "party.js", ROOT / "preview" / "app.js"):
        if not required.exists():
            errors.append(f"missing required file: {required.relative_to(ROOT)}")
    digest = hashlib.sha256(CATALOG.read_bytes()).hexdigest()[:12]
    if errors:
        print("PlayAtlas headless smoke: FAIL")
        for error in errors:
            print(f" - {error}")
        return 1
    print("PlayAtlas headless smoke: PASS")
    print(f" - catalogue entries: 36")
    print(f" - catalogue sha256: {digest}")
    print(" - core round trips: save, search, package path guard, party catalogue")
    print(" - renderer: browser preview available; Godot export requires Godot 4.x")
    return 0


def serve(port: int) -> bool:
    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    try:
        with socketserver.TCPServer(("127.0.0.1", port), handler) as server:
            print(f"Serving PlayAtlas preview at http://127.0.0.1:{port}/preview/")
            print("Press Ctrl+C to stop.")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                print("\nPreview server stopped.")
    except OSError as exc:
        # Managed workspaces may prohibit local socket binding. Keep the
        # catalogue smoke result useful and explain the real limitation rather
        # than emitting a long traceback.
        print(f"Preview server unavailable on this host: {exc}")
        print("Run the same command on a desktop workspace that permits localhost binding.")
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true", help="serve preview/ over localhost after smoke test")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    status = run_smoke()
    if status == 0 and args.serve and not serve(args.port):
        return 2
    return status


if __name__ == "__main__":
    sys.exit(main())
