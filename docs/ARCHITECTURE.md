# PlayAtlas foundation architecture

```text
Presentation (Godot scene / browser preview)
        |
AppCore → GameRegistry → GameModule (rules + state)
   |          |             |
Save/Stats  Package      Game-specific UI
Settings    Manager       and AI adapters
```

## Boundaries

- `GameModule` is a small lifecycle contract. Rule logic can run without a
  scene and exposes turn-based observations/actions or real-time snapshots.
- `GameContext` carries seed, mode and service references into a module.
- `GameRegistry` owns catalogue metadata and lazy module factories. It never
  loads every game's presentation resource at launch.
- `SaveService`, `SettingsService`, `StatisticsService` and
  `TutorialService` are local-only services. Saves are versioned and include a
  backup before replacement.
- `PackageManager` accepts trusted local data packages, checks path traversal,
  file count, expanded size, manifest fields, and rejects executable scripts.
  Godot packages are not a security sandbox; do not enable unknown code.
- `InputService` is a semantic action layer for keyboard, mouse, touch and
  future gamepad adapters. Games declare supported inputs in their manifest.

## Data contract

`data/games/GAME_CATALOG.json` is the runtime discovery metadata. The richer
`content/GAME_CATALOG.json` records the 36-entry launch catalogue, counting
policy, named ruleset versions and per-entry verification fields. Rule and
content provenance registers are populated with explicit verification states;
they are research records, not permission to claim an unverified historical
origin or a completed game.

## Testing strategy

The Python smoke runner validates the catalogue shape, family counts, search
behavior, persistence round-trip, package path guard, and required assets. A
Godot test runner can later instantiate each `GameModule` headlessly and add
rule-level tests without changing this boundary.
