"""Deterministic Minesweeper rules.

Ruleset ``minesweeper.first_click_safe.v1`` uses a seeded mine layout.  Mines
are generated on the first reveal and exclude the clicked cell plus its
orthogonal/diagonal neighbours (when the board has enough free cells).  This
is a deliberate, documented digital rule; it does not claim a no-guess
generator.  Flags are player markers, not proof of a mine.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Optional

from .common import ActionResult


@dataclass(frozen=True)
class MinesweeperResult:
    status: str  # playing, won, lost
    revealed: int
    flags: int
    mines: int


class MinesweeperGame:
    game_id = "minesweeper"
    ruleset_id = "minesweeper.first_click_safe.v1"
    save_schema_version = 1

    def __init__(self, width: int = 9, height: int = 9, mines: int = 10,
                 seed: int = 0, exclude_neighbors: bool = True) -> None:
        if width < 3 or height < 3:
            raise ValueError("Minesweeper board must be at least 3x3")
        if mines <= 0 or mines >= width * height:
            raise ValueError("mines must be between 1 and board cells - 1")
        self.width, self.height, self.mine_count = int(width), int(height), int(mines)
        self.seed = int(seed)
        self.exclude_neighbors = bool(exclude_neighbors)
        self.restart()

    def initialize(self, context: Any = None) -> "MinesweeperGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "MinesweeperGame":
        if config:
            for name in ("width", "height", "mines", "seed", "exclude_neighbors"):
                if name in config:
                    setattr(self, {"mines": "mine_count"}.get(name, name), config[name])
            self.width, self.height = int(self.width), int(self.height)
            self.mine_count, self.seed = int(self.mine_count), int(self.seed)
        # Validate before resetting so malformed configs fail early.
        if self.width < 3 or self.height < 3 or not (0 < self.mine_count < self.width * self.height):
            raise ValueError("invalid Minesweeper configuration")
        self.restart()
        return self

    def restart(self) -> None:
        n = self.width * self.height
        self.mines: set[int] = set()
        self.adjacent: list[int] = [0] * n
        self.revealed: set[int] = set()
        self.flags: set[int] = set()
        self.generated = False
        self.status = "playing"
        self.first_click: Optional[int] = None
        self.last_error = ""
        self.paused = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def _index(self, row: int, col: int) -> int:
        return row * self.width + col

    def _coords(self, index: int) -> tuple[int, int]:
        return divmod(index, self.width)

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def _neighbors(self, index: int) -> list[int]:
        row, col = self._coords(index)
        out: list[int] = []
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if not dr and not dc:
                    continue
                rr, cc = row + dr, col + dc
                if self._in_bounds(rr, cc):
                    out.append(self._index(rr, cc))
        return out

    def _generate(self, safe_index: int) -> None:
        forbidden = {safe_index}
        if self.exclude_neighbors:
            forbidden.update(self._neighbors(safe_index))
        candidates = [i for i in range(self.width * self.height) if i not in forbidden]
        # On very dense custom boards there may not be enough cells after the
        # neighbourhood exclusion.  The clicked cell remains guaranteed safe;
        # only the extra neighbourhood guarantee is relaxed.
        if len(candidates) < self.mine_count:
            forbidden = {safe_index}
            candidates = [i for i in range(self.width * self.height) if i not in forbidden]
        if len(candidates) < self.mine_count:
            raise ValueError("too many mines for first-click safety")
        rng = random.Random(self.seed)
        self.mines = set(rng.sample(candidates, self.mine_count))
        self.adjacent = [sum(n in self.mines for n in self._neighbors(i))
                         for i in range(self.width * self.height)]
        self.generated = True
        self.first_click = safe_index

    def _validate_index(self, index: int) -> bool:
        return isinstance(index, int) and 0 <= index < self.width * self.height

    def _flood_reveal(self, start: int) -> int:
        stack = [start]
        count = 0
        seen: set[int] = set()
        while stack:
            index = stack.pop()
            if index in seen or index in self.flags or index in self.mines:
                continue
            seen.add(index)
            if index not in self.revealed:
                self.revealed.add(index)
                count += 1
            if self.adjacent[index] == 0:
                stack.extend(self._neighbors(index))
        return count

    def _check_win(self) -> None:
        if self.generated and len(self.revealed) == self.width * self.height - self.mine_count:
            self.status = "won"

    def reveal(self, index: int | tuple[int, int]) -> ActionResult:
        if isinstance(index, tuple):
            if len(index) != 2:
                raise ValueError("coordinate must be (row, col)")
            index = self._index(int(index[0]), int(index[1]))
        if not self._validate_index(index):
            return ActionResult(False, "out_of_bounds")
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if index in self.flags:
            return ActionResult(False, "cell_flagged")
        if index in self.revealed:
            return self.chord(index)
        if not self.generated:
            self._generate(index)
        if index in self.mines:
            self.revealed.add(index)
            self.status = "lost"
            self.revealed.update(self.mines)
            return ActionResult(True, outcome="lost", payload={"mine": index})
        count = self._flood_reveal(index)
        self._check_win()
        return ActionResult(True, outcome=self.status, payload={"revealed": count})

    def toggle_flag(self, index: int | tuple[int, int]) -> ActionResult:
        if isinstance(index, tuple):
            index = self._index(int(index[0]), int(index[1]))
        if not self._validate_index(index):
            return ActionResult(False, "out_of_bounds")
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if index in self.revealed:
            return ActionResult(False, "already_revealed")
        if index in self.flags:
            self.flags.remove(index)
            return ActionResult(True, outcome="playing", payload={"flagged": False})
        if len(self.flags) >= self.mine_count:
            return ActionResult(False, "flag_limit")
        self.flags.add(index)
        return ActionResult(True, outcome="playing", payload={"flagged": True})

    def chord(self, index: int | tuple[int, int]) -> ActionResult:
        if isinstance(index, tuple):
            index = self._index(int(index[0]), int(index[1]))
        if not self._validate_index(index):
            return ActionResult(False, "out_of_bounds")
        if index not in self.revealed:
            return ActionResult(False, "not_revealed")
        if self.adjacent[index] == 0:
            return ActionResult(False, "no_chord_targets")
        ns = self._neighbors(index)
        if sum(n in self.flags for n in ns) != self.adjacent[index]:
            return ActionResult(False, "flag_count_mismatch")
        total = 0
        for n in ns:
            if n not in self.flags and n not in self.revealed:
                if n in self.mines:
                    self.status = "lost"
                    self.revealed.update(self.mines)
                    return ActionResult(True, outcome="lost", payload={"mine": n})
                total += self._flood_reveal(n)
        self._check_win()
        return ActionResult(True, outcome=self.status, payload={"revealed": total})

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        visible_mines = set(self.mines) if self.status == "lost" else set()
        return {
            "game_id": self.game_id, "ruleset_id": self.ruleset_id,
            "width": self.width, "height": self.height, "mine_count": self.mine_count,
            "revealed": sorted(self.revealed), "flags": sorted(self.flags),
            "adjacent": [self.adjacent[i] if i in self.revealed else None
                         for i in range(self.width * self.height)],
            "visible_mines": sorted(visible_mines), "status": self.status,
            "generated": self.generated,
        }

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[dict[str, Any]]:
        if self.status != "playing" or self.paused:
            return []
        return [{"type": "reveal", "index": i} for i in range(self.width * self.height)
                if i not in self.revealed and i not in self.flags]

    def get_result(self) -> MinesweeperResult:
        return MinesweeperResult(self.status, len(self.revealed), len(self.flags), self.mine_count)

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "game_version": 1,
            "ruleset_id": self.ruleset_id, "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "width": self.width, "height": self.height, "mine_count": self.mine_count,
            "seed": self.seed, "exclude_neighbors": self.exclude_neighbors,
            "mines": sorted(self.mines), "adjacent": list(self.adjacent),
            "revealed": sorted(self.revealed), "flags": sorted(self.flags),
            "generated": self.generated, "first_click": self.first_click,
            "status": self.status, "paused": self.paused,
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        self.width, self.height = int(data["width"]), int(data["height"])
        self.mine_count, self.seed = int(data["mine_count"]), int(data.get("seed", 0))
        self.exclude_neighbors = bool(data.get("exclude_neighbors", True))
        n = self.width * self.height
        self.mines = {int(x) for x in data.get("mines", [])}
        self.adjacent = [int(x) for x in data.get("adjacent", [0] * n)]
        self.revealed = {int(x) for x in data.get("revealed", [])}
        self.flags = {int(x) for x in data.get("flags", [])}
        if len(self.adjacent) != n or any(not 0 <= x < n for x in self.mines | self.revealed | self.flags):
            raise ValueError("invalid Minesweeper state")
        self.generated = bool(data.get("generated", bool(self.mines)))
        self.first_click = data.get("first_click")
        self.status = str(data.get("status", "playing"))
        if self.status not in ("playing", "won", "lost"):
            raise ValueError("invalid Minesweeper status")
        self.paused = bool(data.get("paused", False))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "MinesweeperGame":
        game = cls(int(data["width"]), int(data["height"]), int(data["mine_count"]), int(data.get("seed", 0)))
        game.load_state(data)
        return game

    def dispose(self) -> None:
        self.paused = True

