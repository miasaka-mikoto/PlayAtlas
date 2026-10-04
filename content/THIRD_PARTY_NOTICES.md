# PlayAtlas — Third-party notices

Generated: 2026-10-05

This file covers dependencies and reference material currently registered for the PlayAtlas project. It is intentionally conservative: a URL in `rules_sources.json` or `content_sources.json` is a research reference, not permission to copy the source's text, images, code, database or branding.

## Runtime engine

### Godot Engine 4.7.2 (target)

- Source/archive: <https://godotengine.org/download/archive/>
- License: MIT
- Use: game runtime/editor/export toolchain
- Notice: the exact editor/export version must be frozen in the build manifest. The final Windows and Android distributions must include the Godot MIT notice required by the redistributed engine binaries. If the build environment selects another Godot 4.x patch, update this record before release.

## Reference-only projects and databases

The following are not runtime dependencies and are not bundled:

- **Original 2048 project** — <https://github.com/gabrielecirulli/2048> — consulted as a mechanic reference only. The upstream repository contains its own license; verify it again before reusing any code or asset.
- **Ludii / Digital Ludeme Project** — <https://ludii.games/> — consulted for traditional-game rule research. No Ludii executable, database, source code or image is redistributed by PlayAtlas. Review the license for any future integration.
- **Wikimedia/Wikipedia pages** — consulted as secondary references where identified in `rules_sources.json`. No article text or images are copied into the build; per-page terms apply if a future asset is considered.
- **Pagat and other specialist rule pages** — consulted for rule verification. PlayAtlas rewrites tutorial text and does not copy page text, diagrams or images.

## Original content policy

Current content-source inventory declares no third-party runtime art, music, sound effects, fonts or character assets. Until a source record is added and license-checked, new assets must be original PlayAtlas work or remain outside release packages.

The following must be added to this file before release if used:

1. exact asset path and version/checksum;
2. creator and source URL;
3. license and attribution text;
4. redistribution/modification permissions;
5. any NOTICE or share-alike obligations.

## Party/LAN implementation

Party Pack 1 and the headless LAN adapter use only Python's standard library
and Godot's built-in ENet API. No external network SDK, paid service, LLM API,
image generator, gambling provider, or remotely hosted asset is included.

## Names and trademarks

Game names may be used descriptively to identify rulesets. **Connect Four/Connect 4**, **Sokoban**, **Sudoku** and other names can be trademarks in particular jurisdictions. PlayAtlas does not claim affiliation with Hasbro, Falcon/Thinking Rabbit, Nikoli or any other rights holder, and uses original visual identity rather than their logos, characters, packaging or distinctive artwork. The final legal/name review remains a release gate.

## No warranty of source completeness

Rules sources can document multiple regional or historical variants. A source citation is not a statement that the rules are universally canonical. The selected default, version, differences and unresolved questions are recorded per game in `GAME_CATALOG.json` and `rules_sources.json`.
