# PlayAtlas UI preview

`ui_preview/` is an offline-first HTML5 visual shell for the PlayAtlas hall. It
uses only local HTML, CSS, JavaScript, Canvas, and the local
`data/games/GAME_CATALOG.json` file. No fonts, images, analytics, or network
service are required.

## Run locally

From the `playatlas_core` directory:

```bash
python -m http.server 8765
```

Open <http://127.0.0.1:8765/ui_preview/>. A local HTTP server is used because
browser security blocks `fetch()` from a `file://` page. If the catalogue is
not available, the shell uses an embedded 36-entry fallback and marks all
non-sample entries as a roadmap item.

## What is interactive

- Search by Chinese/English title, family, region, and description.
- Filter by family and supported mode; sort by recommended, playable-first, or
  name.
- Open a game card to inspect ruleset/status/tutorial tabs.
- `给我一局` chooses only a playable or explicitly labelled interactive sample.
- Favorites are stored in the browser's local storage.
- Six sample cards expose a clearly labelled interactive preview: Gomoku,
  Minesweeper, Klondike, Snake, Oware, and Carrom. These surfaces are not
  counted as formally accepted games until the rule, save, tutorial, and
  Windows/Android checks are recorded in `GAME_STATUS.md`.

## Screenshot capture

Use any Chromium-based browser's full-page screenshot after loading the local
URL. The recommended viewport is 1440×900. Do not use a generated illustration
as a runtime screenshot; the canvas previews are part of the shell itself.

## Godot integration

The browser shell intentionally does not import Godot. `ui/CoreShell.tscn` and
the autoload services remain the canonical Godot hook. A future Godot main
scene can open this shell only as a development preview; game status must
still come from `GameRegistry` and the same catalogue.
