"""PlayAtlas rule and content core.

The package intentionally contains no rendering or Godot imports.  Game
modules can therefore be tested in a headless Python process and adapted to
the desktop/mobile front end later.
"""

__all__ = ["games", "network"]
