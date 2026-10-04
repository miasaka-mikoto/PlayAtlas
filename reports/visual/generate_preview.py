#!/usr/bin/env python3
"""Generate a truthful, self-contained PlayAtlas visual evidence artifact.

This is deliberately a static procedural composition.  It mirrors the local
HTML/CSS preview language (navy shell, amber/mint accents, library cards) but
does not pretend to be a capture of a Godot or Windows runtime.  No legacy
project assets are read.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent
OUT_PNG = OUT_DIR / "playatlas_hall_automated_preview_1440x900.png"
OUT_MANIFEST = OUT_DIR / "visual_evidence_manifest.json"

W, H = 1440, 900
S = 2  # Render supersampled, then downsample for cleaner rounded edges.


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    paths = (
        "/usr/share/fonts/opentype/urw-base35/NimbusSans-Bold.otf"
        if bold
        else "/usr/share/fonts/opentype/urw-base35/NimbusSans-Regular.otf"
    )
    return ImageFont.truetype(paths, size * S)


def xy(v: float | int) -> int:
    return int(round(v * S))


def box(values: Sequence[float | int]) -> tuple[int, int, int, int]:
    return tuple(xy(v) for v in values)  # type: ignore[return-value]


def rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)) + (alpha,)


def rounded(draw: ImageDraw.ImageDraw, rect: Sequence[float | int], radius: int,
            fill: str | tuple[int, int, int, int], outline: str | None = None,
            width: int = 1) -> None:
    draw.rounded_rectangle(box(rect), radius=xy(radius), fill=fill,
                           outline=outline, width=xy(width) if outline else 1)


def text(draw: ImageDraw.ImageDraw, pos: tuple[float | int, float | int], value: str,
         size: int, fill: str | tuple[int, int, int, int], bold: bool = False,
         anchor: str | None = None, spacing: int = 4) -> None:
    draw.multiline_text((xy(pos[0]), xy(pos[1])), value, font=font(size, bold),
                        fill=fill, anchor=anchor, spacing=xy(spacing))


def line(draw: ImageDraw.ImageDraw, points: Iterable[tuple[float, float]], fill, width=1) -> None:
    draw.line([(xy(x), xy(y)) for x, y in points], fill=fill, width=xy(width), joint="curve")


def alpha_layer(base: Image.Image, layer: Image.Image) -> None:
    base.alpha_composite(layer)


def radial_glow(size: tuple[int, int], center: tuple[float, float], radius: float,
                color: tuple[int, int, int], max_alpha: int) -> Image.Image:
    """Return an RGBA radial glow without external image assets."""
    w, h = size
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = layer.load()
    cx, cy = center
    rr = radius * radius
    for y in range(max(0, int(cy - radius)), min(h, int(cy + radius))):
        for x in range(max(0, int(cx - radius)), min(w, int(cx + radius))):
            d = (x - cx) ** 2 + (y - cy) ** 2
            if d >= rr:
                continue
            a = int(max_alpha * (1.0 - math.sqrt(d / rr)) ** 2)
            px[x, y] = (*color, a)
    return layer


def draw_tile_gomoku(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    rounded(draw, (x, y, x + 146, y + 127), 16, "#604738", "#826a58")
    for i in range(6):
        xx = x + 23 + i * 20
        line(draw, [(xx, y + 33), (xx, y + 112)], (45, 29, 22, 160), 1)
        yy = y + 33 + i * 16
        line(draw, [(x + 23, yy), (x + 123, yy)], (45, 29, 22, 160), 1)
    draw.ellipse(box((x + 63, y + 62, x + 95, y + 94)), fill="#171a22", outline="#727987", width=1)
    draw.ellipse(box((x + 97, y + 81, x + 129, y + 113)), fill="#ece6d9", outline="#9da7b8", width=1)
    draw.ellipse(box((x + 43, y + 90, x + 65, y + 112)), fill="#20232d", outline="#727987", width=1)
    text(draw, (x + 12, y + 10), "GOMOKU", 8, "#d7dce8", bold=True)


def draw_tile_oware(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    rounded(draw, (x, y, x + 132, y + 103), 48, "#8d5e42", "#c18b5d")
    for i in range(5):
        px = x + 21 + i * 21
        draw.ellipse(box((px, y + 46, px + 17, y + 63)), fill="#f2c171", outline="#f9d99a", width=1)
    text(draw, (x + 13, y + 12), "OWARE", 8, "#f6deba", bold=True)


def draw_tile_snake(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    rounded(draw, (x, y, x + 176, y + 86), 15, "#173a3c", "#2c6965")
    points = [(x + 28, y + 56), (x + 49, y + 31), (x + 77, y + 54),
              (x + 106, y + 27), (x + 135, y + 52)]
    line(draw, points, "#77e2c1", 8)
    draw.ellipse(box((x + 128, y + 45, x + 139, y + 56)), fill="#ffb454")
    text(draw, (x + 12, y + 10), "SNAKE", 8, "#d7dce8", bold=True)


def draw_card(draw: ImageDraw.ImageDraw, x: float, y: float, title: str,
              family: str, status: str, accent: str, kind: str,
              description: str) -> None:
    # Shadow is painted as a separate translucent rounded shape by caller.
    rounded(draw, (x, y, x + 260, y + 205), 17, "#101a2f", "#273651")
    rounded(draw, (x + 1, y + 1, x + 259, y + 92), 16, "#192a45")
    if kind == "gomoku":
        # A compact wood board illustration.
        rounded(draw, (x + 24, y + 17, x + 143, y + 83), 10, "#76523b")
        for i in range(5):
            line(draw, [(x + 36 + i * 22, y + 26), (x + 36 + i * 22, y + 75)], (47, 29, 21, 130), 1)
            line(draw, [(x + 36, y + 26 + i * 12), (x + 132, y + 26 + i * 12)], (47, 29, 21, 130), 1)
        draw.ellipse(box((x + 72, y + 43, x + 88, y + 59)), fill="#141924")
        draw.ellipse(box((x + 97, y + 55, x + 113, y + 71)), fill="#eee8db")
    elif kind == "mine":
        rounded(draw, (x + 23, y + 16, x + 144, y + 83), 8, "#1d3150")
        for r in range(4):
            for c in range(7):
                xx, yy = x + 30 + c * 16, y + 22 + r * 14
                fill = "#2e4b6a" if (r + c) % 3 else "#ff7a70"
                rounded(draw, (xx, yy, xx + 12, yy + 10), 2, fill)
        text(draw, (x + 100, y + 45), "3", 16, "#77e2c1", bold=True)
    elif kind == "cards":
        for i, (label, color) in enumerate((("A", "#f2eee3"), ("7", "#f2eee3"), ("K", "#f2eee3"))):
            xx = x + 35 + i * 36
            rounded(draw, (xx, y + 18 + (i % 2) * 7, xx + 34, y + 72 + (i % 2) * 7), 5, color)
            text(draw, (xx + 8, y + 24 + (i % 2) * 7), label, 14, "#be5360" if i == 1 else "#253553", bold=True)
    elif kind == "snake":
        rounded(draw, (x + 22, y + 17, x + 145, y + 82), 9, "#173b3d")
        line(draw, [(x + 41, y + 61), (x + 62, y + 39), (x + 83, y + 62), (x + 107, y + 34), (x + 127, y + 51)], "#77e2c1", 6)
        draw.ellipse(box((x + 123, y + 46, x + 132, y + 55)), fill="#ffb454")
    elif kind == "oware":
        rounded(draw, (x + 22, y + 30, x + 145, y + 69), 20, "#88583e")
        for i in range(6):
            draw.ellipse(box((x + 31 + i * 19, y + 42, x + 43 + i * 19, y + 54)), fill="#f2c171")
    elif kind == "carrom":
        rounded(draw, (x + 21, y + 15, x + 146, y + 84), 8, "#d5b47a")
        draw.ellipse(box((x + 26, y + 20, x + 38, y + 32)), fill="#542c27")
        draw.ellipse(box((x + 132, y + 68, x + 144, y + 80)), fill="#542c27")
        draw.ellipse(box((x + 81, y + 45, x + 92, y + 56)), fill="#df5961")
        draw.ellipse(box((x + 74, y + 65, x + 91, y + 82)), fill="#f4ddae")
    text(draw, (x + 170, y + 21), status, 8, accent, bold=True)
    text(draw, (x + 170, y + 42), family, 9, "#93a1be")
    text(draw, (x + 18, y + 115), title, 15, "#eff3ff", bold=True)
    text(draw, (x + 18, y + 143), description, 9, "#93a1be")
    rounded(draw, (x + 18, y + 175, x + 103, y + 192), 8, (255, 180, 84, 20), "#6d593c")
    text(draw, (x + 60, y + 184), "VIEW DETAILS", 7, "#ffb454", bold=True, anchor="mm")


def draw_preview() -> Image.Image:
    img = Image.new("RGBA", (W * S, H * S), "#080d1b")
    # Base gradients and subtle glows.
    px = img.load()
    for y in range(H * S):
        t = y / (H * S - 1)
        for x in range(W * S):
            u = x / (W * S - 1)
            r = int(8 + 5 * (1 - t) + 2 * u)
            g = int(13 + 8 * (1 - t) + 3 * u)
            b = int(27 + 19 * (1 - t) + 10 * u)
            px[x, y] = (r, g, b, 255)
    alpha_layer(img, radial_glow(img.size, (W * .71, H * .08), 650 * S, (28, 55, 112), 110))
    alpha_layer(img, radial_glow(img.size, (W * .74, H * .60), 410 * S, (17, 73, 67), 52))

    draw = ImageDraw.Draw(img, "RGBA")
    # Rail.
    draw.rectangle(box((0, 0, 92, H)), fill=(7, 12, 26, 225))
    line(draw, [(91, 0), (91, H)], (168, 186, 226, 40), 1)
    rounded(draw, (22, 22, 71, 71), 16, (35, 33, 51, 255), (255, 180, 84, 175))
    rounded(draw, (27, 27, 66, 66), 13, (255, 180, 84, 16), (255, 180, 84, 75))
    text(draw, (46.5, 46.5), "PA", 14, "#ffb454", bold=True, anchor="mm")
    draw.ellipse(box((61, 29, 68, 36)), fill="#77e2c1")
    rail_items = [("⌂", "HALL", True), ("▶", "RESUME", False), ("☆", "SAVED", False), ("◌", "STATS", False)]
    for i, (icon, label, active) in enumerate(rail_items):
        y = 127 + i * 79
        if active:
            rounded(draw, (11, y - 9, 81, y + 48), 14, (255, 180, 84, 25))
            rounded(draw, (9, y + 5, 12, y + 29), 2, "#ffb454")
        text(draw, (46, y + 7), icon, 21, "#ffb454" if active else "#5e6b86", anchor="mm")
        text(draw, (46, y + 34), label, 8, "#ffb454" if active else "#5e6b86", bold=active, anchor="mm")
    text(draw, (46, H - 90), "⚙", 19, "#5e6b86", anchor="mm")
    draw.ellipse(box((43, H - 52, 49, H - 46)), fill="#77e2c1")
    text(draw, (46, H - 32), "OFFLINE", 7, "#5e6b86", anchor="mm")

    # Main top bar.
    left = 122
    text(draw, (left, 32), "PLAY", 14, "#eff3ff", bold=True)
    text(draw, (left + 40, 32), "ATLAS", 14, "#ffb454", bold=True)
    text(draw, (left + 122, 34), "WORLD GAME HOUSE", 10, "#93a1be")
    rounded(draw, (1127, 27, 1271, 58), 18, (16, 25, 46, 185), (168, 186, 226, 38))
    draw.ellipse(box((1142, 40, 1148, 46)), fill="#77e2c1")
    text(draw, (1158, 43), "LOCAL CATALOG", 9, "#93a1be", anchor="lm")
    text(draw, (1250, 43), "36", 10, "#eff3ff", bold=True, anchor="rm")
    rounded(draw, (1290, 27, 1324, 61), 17, "#111b31", "#30405f")
    text(draw, (1307, 44), "?", 14, "#93a1be", anchor="mm")
    draw.ellipse(box((1342, 27, 1376, 61)), fill="#ff9c67")
    text(draw, (1359, 44), "L", 12, "#080d1b", bold=True, anchor="mm")

    # Hero card and lighting.
    rounded(draw, (122, 91, 1377, 378), 29, "#121d35", "#30405f")
    alpha_layer(img, radial_glow(img.size, (1060 * S, 210 * S), 280 * S, (255, 180, 84), 34))
    alpha_layer(img, radial_glow(img.size, (1240 * S, 125 * S), 190 * S, (119, 226, 193), 23))
    draw = ImageDraw.Draw(img, "RGBA")
    text(draw, (169, 133), "YOUR NEXT SMALL ADVENTURE", 9, "#ffb454", bold=True)
    line(draw, [(149, 139), (163, 139)], "#ffb454", 1)
    text(draw, (169, 165), "A small adventure,\nanywhere.", 47, "#eff3ff", bold=True, spacing=-1)
    text(draw, (169, 275), "From one quiet board to a world of rules.\nClear tutorials, local saves, no connection required.", 13, "#93a1be", spacing=5)
    rounded(draw, (169, 323, 288, 361), 11, "#ffb454")
    text(draw, (185, 342), "⌁  PICK A GAME", 10, "#080d1b", bold=True, anchor="lm")
    rounded(draw, (302, 323, 421, 361), 11, "#18243d", "#30405f")
    text(draw, (320, 342), "RESUME  →", 10, "#eff3ff", bold=True, anchor="lm")

    # Hero art, all vector-like shapes created here.
    draw.ellipse(box((855, 114, 1165, 424)), outline=(119, 226, 193, 70), width=xy(1))
    draw.ellipse(box((842, 192, 1217, 312)), outline=(255, 180, 84, 110), width=xy(1))
    draw_tile_gomoku(draw, 846, 142)
    draw_tile_oware(draw, 1091, 122)
    draw_tile_snake(draw, 1137, 268)
    text(draw, (1237, 351), "25°N  121°E   ·   35°N  139°E", 8, (239, 243, 255, 105), bold=True, anchor="rm")

    # Continue card.
    rounded(draw, (122, 396, 1377, 478), 17, (17, 44, 53, 215), (119, 226, 193, 48))
    draw.ellipse(box((142, 414, 187, 459)), fill="#77e2c1")
    text(draw, (164.5, 436.5), "▶", 14, "#080d1b", bold=True, anchor="mm")
    text(draw, (207, 413), "CONTINUE YOUR JOURNEY", 8, "#ffb454", bold=True)
    text(draw, (207, 435), "Gomoku", 16, "#eff3ff", bold=True)
    text(draw, (275, 437), "·  casual match", 10, "#93a1be")
    rounded(draw, (207, 460, 477, 464), 2, (255, 255, 255, 23))
    rounded(draw, (207, 460, 321, 464), 2, "#77e2c1")
    text(draw, (1200, 449), "MOVE 12  ·  SAVED LOCALLY", 8, "#5e6b86", anchor="rm")
    rounded(draw, (1260, 416, 1334, 454), 11, (119, 226, 193, 18), (119, 226, 193, 70))
    text(draw, (1297, 435), "CONTINUE  →", 8, "#77e2c1", bold=True, anchor="mm")

    # Library heading + toolbar.
    text(draw, (122, 526), "THE LIBRARY", 9, "#ffb454", bold=True)
    text(draw, (122, 549), "Find a game", 26, "#eff3ff", bold=True)
    text(draw, (1267, 557), "VIEW ALL  →", 9, "#ffb454", bold=True, anchor="rm")
    rounded(draw, (122, 589, 411, 629), 10, "#111b31", "#30405f")
    text(draw, (142, 609), "⌕", 17, "#5e6b86", anchor="lm")
    text(draw, (168, 609), "Search games, aliases, regions", 10, "#5e6b86", anchor="lm")
    rounded(draw, (394, 600, 404, 618), 4, (255, 255, 255, 6), (168, 186, 226, 38))
    text(draw, (399, 609), "/", 8, "#5e6b86", bold=True, anchor="mm")
    # Chips sit to the right of the search field, matching the flex toolbar in
    # the local HTML/CSS preview (the first draft accidentally overlapped the
    # search field in the static composition).
    chips = [("ALL", 430, 0, True), ("CLASSIC", 498, 0, False), ("BOARD", 590, 0, False),
             ("CARDS", 673, 0, False), ("WORLD", 749, 0, False), ("TABLETOP", 831, 0, False)]
    for label, x, _, active in chips:
        width = 62 if label == "ALL" else 78 if label in ("CLASSIC", "BOARD") else 66 if label == "CARDS" else 72
        rounded(draw, (x, 593, x + width, 626), 17, "#302a22" if active else "#111b31",
                "#8f6a3c" if active else "#273651")
        text(draw, (x + width / 2, 609), label, 8, "#ffb454" if active else "#93a1be", bold=active, anchor="mm")
    rounded(draw, (1284, 593, 1377, 626), 17, "#111b31", "#30405f")
    text(draw, (1330, 609), "RECOMMENDED  ⌄", 8, "#93a1be", anchor="mm")
    text(draw, (122, 650), "ALL MODES", 8, "#ffb454", bold=True)
    text(draw, (220, 650), "SOLO", 8, "#93a1be")
    text(draw, (265, 650), "VS COMPUTER", 8, "#93a1be")
    text(draw, (368, 650), "LOCAL TWO-PLAYER", 8, "#93a1be")
    text(draw, (1290, 650), "6 INTERACTIVE SAMPLES · 36 CATALOG ENTRIES", 8, "#5e6b86", anchor="rm")

    # Cards.  The six sample cards are intentionally labelled as samples.
    cards = [
        (122, 665, "Gomoku", "BOARD GAME", "INTERACTIVE SAMPLE", "#ffb454", "gomoku", "Freestyle rules · local board"),
        (402, 665, "Minesweeper", "PUZZLE", "INTERACTIVE SAMPLE", "#77e2c1", "mine", "First-click safe · local grid"),
        (682, 665, "Klondike", "CARDS", "INTERACTIVE SAMPLE", "#75a7ff", "cards", "Draw one · solitaire study"),
        (962, 665, "Snake", "ARCADE", "INTERACTIVE SAMPLE", "#ff7a70", "snake", "Classic grid · keyboard ready"),
        # These two are kept in the evidence data but fall below the 900px
        # viewport, just as the real scrollable library continues below the
        # fold.  They are not painted over the first row.
        (122, 885, "Oware", "WORLD TRADITION", "INTERACTIVE SAMPLE", "#ffb454", "oware", "Abapa rules · sow and capture"),
        (402, 885, "Carrom", "TABLETOP", "INTERACTIVE SAMPLE", "#77e2c1", "carrom", "Aim and strike · physics study"),
    ]
    for x, y, title, family, status, accent, kind, desc in cards:
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow, "RGBA")
        rounded(sd, (x + 3, y + 5, x + 263, y + 210), 17, (0, 0, 0, 90))
        shadow = shadow.filter(ImageFilter.GaussianBlur(xy(8)))
        alpha_layer(img, shadow)
        draw = ImageDraw.Draw(img, "RGBA")
        draw_card(draw, x, y, title, family, status, accent, kind, desc)

    # Evidence disclosure footer overlay; this is intentionally impossible to
    # mistake for a runtime screenshot.
    rounded(draw, (122, 851, 1377, 886), 10, (8, 13, 27, 235), (255, 180, 84, 125))
    text(draw, (142, 868.5), "AUTOMATED VISUAL PREVIEW", 9, "#ffb454", bold=True, anchor="lm")
    text(draw, (356, 868.5), "Procedural PIL composition based on the local HTML/CSS preview · 1440×900 · not a manual runtime screenshot", 8, "#93a1be", anchor="lm")

    # Supersampling downsample.
    return img.convert("RGB").resize((W, H), Image.Resampling.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image = draw_preview()
    image.save(OUT_PNG, format="PNG", optimize=True)
    digest = hashlib.sha256(OUT_PNG.read_bytes()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    design_files = [ROOT / "playatlas_core/preview/index.html", ROOT / "playatlas_core/preview/styles.css"]
    source_hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in design_files
    }
    manifest = {
        "artifact": OUT_PNG.name,
        "generated_at_utc": now,
        "resolution": [W, H],
        "method": "Procedural PIL composition, supersampled 2x and downsampled with Lanczos.",
        "design_reference": [
            "playatlas_core/preview/index.html",
            "playatlas_core/preview/styles.css",
        ],
        "design_reference_sha256": source_hashes,
        "generator": "playatlas_core/reports/visual/generate_preview.py",
        "source_policy": "Original vector-like shapes and typography only; no old-project images, models, music, or copied assets.",
        "runtime_claims": {
            "godot_runtime_capture": False,
            "windows_launch": False,
            "manual_interaction": False,
            "android_validation": False,
        },
        "visible_disclosure": "AUTOMATED VISUAL PREVIEW · Procedural PIL composition · not a manual runtime screenshot",
        "catalog_context": {
            "catalog_entries": 36,
            "interactive_sample_cards_shown": 6,
            "source_status": "catalogue and browser preview only; not a claim that all 36 games are complete",
        },
        "sha256": digest,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PNG}")
    print(f"wrote {OUT_MANIFEST}")
    print(f"sha256 {digest}")


if __name__ == "__main__":
    main()
