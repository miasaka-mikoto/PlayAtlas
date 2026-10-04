# PlayAtlas · 世界游戏馆

PlayAtlas is an offline-first, data-driven game gallery foundation. This
checkout is deliberately independent from the user's older projects and ships
no copied commercial assets.

## What is actually included

- A Godot 4 project skeleton (`project.godot`, `ui/CoreShell.tscn`, autoload
  services and package validation). The project targets the latest stable
  Godot 4.7.2 identified in the official archive on 2026-10-04.
- A local HTML5 Canvas preview in `preview/` (the richer source is mirrored in
  `ui_preview/`). It includes the hall, search/filtering, favourites, rules and
  tutorial panels, and interactive previews for the six Stage-1 sample games.
- Six headless sample engines: Gomoku, Minesweeper, Klondike, Snake, Oware and
  Carrom. Their rule state is serialisable and independent of UI nodes.
- Additional deterministic rule engines for Breakout, Sudoku, Shisen-Sho/
  Mahjong Connect, Dots & Boxes, Reversi, Connect Four, 2048, Sokoban, 15
  Puzzle, Sungka, Go Fish, Crazy Eights, bowling and mini golf. They are
  counted as rule-layer implemented only where `reports/qa` says so.
- Party Pack 1 rule engines: original grid Tank Battle, UNO, a clearly named
  Sheng Ji digital adaptation, score-only Blackjack, and two no-money chance
  toys. These six expansion entries live in `content/PARTY_CATALOG.json` and
  are not added to the launch-36 playable count yet.
- Host-authoritative LAN adapters: Python `network/lan.py` for deterministic
  localhost/CLI testing and Godot `scripts/network/lan_service.gd` for the
  ENet presentation bridge. Hidden-card observations are player-scoped.
- A 36-entry launch catalogue in `content/GAME_CATALOG.json` (with the older
  `_FULL` filename retained as a compatibility copy). Planned or unverified
  entries are never counted as playable.
- Automated smoke, pytest and unittest runners; a source-first portable ZIP
  builder; truthful Windows/Android/visual status records.

## Run checks from the workspace root

```bash
PYTHONPATH=. python3 PlayAtlas/tools/run_headless_smoke.py
PYTHONPATH=. python3 PlayAtlas/tools/run_qa.py --project-root PlayAtlas
PYTHONPATH=. python3 -m pytest -q PlayAtlas/tests
PYTHONPATH=. python3 PlayAtlas/tools/run_party_smoke.py
```

The current report is in `reports/qa/qa_report.md`. A headless pass is not a
claim of manual interaction, audio, FPS, Windows startup, Android export, or
touch validation.

To start a development LAN room after allowing local TCP sockets:

```bash
PYTHONPATH=. python3 PlayAtlas/tools/lan_host.py --game uno --players 2 --port 27800
```

The protocol and reconnect/hidden-information policy are documented in
`docs/LAN_PROTOCOL.md`. This is a local room helper, not an online service.

## Run the local preview

```bash
cd PlayAtlas
python3 tools/run_headless_smoke.py --serve
```

Open `http://127.0.0.1:8765/preview/`. On Windows, use `START_PREVIEW.bat`.
The server is local-only; no internet or account is required.

## Godot

Open this directory in Godot 4.7.2 or another compatible stable 4.x editor.
The entry scene is `res://ui/CoreShell.tscn`. This workspace did not contain a
Godot executable or a display server, so no native export is claimed here.

## Status discipline

`GAME_STATUS.md` is the acceptance ledger. Use only the permitted states:
`已实现`, `已自动测试`, `已人工测试`, `待验证`, `失败`, `阻塞`, `未测试`.
The six interactive browser surfaces are labelled previews until their full
Godot/Windows/tutorial/save flows are verified.

Party Pack 1 uses the same ledger discipline. Its localhost protocol smoke
test is not a substitute for real Windows multi-device, firewall, Wi-Fi,
touch, audio, or manual acceptance.
