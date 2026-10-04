"""Small shared value types used by headless game rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class ActionResult:
    """Result of applying an action.

    ``ok`` is intentionally explicit (rather than raising for ordinary
    illegal moves), which lets a UI explain an error without corrupting the
    match.  Programming errors still raise ``TypeError``/``ValueError``.
    """

    ok: bool
    reason: str = ""
    outcome: Optional[str] = None
    payload: Any = None

    def __bool__(self) -> bool:
        return self.ok
