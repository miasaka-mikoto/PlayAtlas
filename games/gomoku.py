"""Freestyle Gomoku (five-in-a-row) rule engine.

Ruleset ``gomoku.freestyle.v1``
--------------------------------
* 15x15 board, black moves first.
* A player wins as soon as five or more contiguous stones occur in one of the
  four straight directions.  Overlines are wins in this freestyle ruleset;
  no Renju forbidden-move rules are claimed.
* A full board without a line is a draw.

The engine stores no UI objects and can be serialised to JSON-compatible
dictionaries.  Coordinates are zero based ``(row, column)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

from .common import ActionResult


@dataclass(frozen=True)
class GomokuAction:
    row: int
    col: int


class GomokuGame:
    game_id = "gomoku"
    ruleset_id = "gomoku.freestyle.v1"
    save_schema_version = 1

    def __init__(self, size: int = 15, win_length: int = 5) -> None:
        if size < win_length or size < 3:
            raise ValueError("size must be at least win_length and 3")
        if win_length < 3:
            raise ValueError("win_length must be at least 3")
        self.size = int(size)
        self.win_length = int(win_length)
        self.restart()

    def initialize(self, context: Any = None) -> "GomokuGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "GomokuGame":
        if config:
            size = int(config.get("size", self.size))
            win_length = int(config.get("win_length", self.win_length))
            if size != self.size or win_length != self.win_length:
                self.size, self.win_length = size, win_length
        self.restart()
        return self

    def restart(self) -> None:
        self.board: list[int] = [0] * (self.size * self.size)
        self.current_player = 1
        self.winner: Optional[int] = None
        self.draw = False
        self.move_count = 0
        self.paused = False
        self.last_error = ""

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def _index(self, row: int, col: int) -> int:
        return row * self.size + col

    def _in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.size and 0 <= col < self.size

    def get_current_player(self) -> Optional[int]:
        return None if self.is_finished() else self.current_player

    def is_finished(self) -> bool:
        return self.winner is not None or self.draw

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[GomokuAction]:
        if self.is_finished() or (player_id is not None and player_id != self.current_player):
            return []
        return [GomokuAction(i // self.size, i % self.size)
                for i, value in enumerate(self.board) if value == 0]

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "ruleset_id": self.ruleset_id,
            "size": self.size,
            "win_length": self.win_length,
            "board": list(self.board),
            "current_player": self.get_current_player(),
            "winner": self.winner,
            "draw": self.draw,
            "move_count": self.move_count,
        }

    def _line_length(self, row: int, col: int, dr: int, dc: int, player: int) -> int:
        count = 1
        r, c = row + dr, col + dc
        while self._in_bounds(r, c) and self.board[self._index(r, c)] == player:
            count += 1
            r, c = r + dr, c + dc
        r, c = row - dr, col - dc
        while self._in_bounds(r, c) and self.board[self._index(r, c)] == player:
            count += 1
            r, c = r - dr, c - dc
        return count

    def _wins_at(self, row: int, col: int, player: int) -> bool:
        return any(self._line_length(row, col, dr, dc, player) >= self.win_length
                   for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)))

    def apply_action(self, action: GomokuAction | tuple[int, int] | dict[str, int]) -> ActionResult:
        if isinstance(action, dict):
            action = GomokuAction(int(action["row"]), int(action["col"]))
        elif isinstance(action, tuple):
            if len(action) != 2:
                raise ValueError("Gomoku action tuple must contain row and col")
            action = GomokuAction(int(action[0]), int(action[1]))
        if not isinstance(action, GomokuAction):
            raise TypeError("expected GomokuAction, (row, col), or mapping")
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.is_finished():
            return ActionResult(False, "game_finished", self.outcome())
        if not self._in_bounds(action.row, action.col):
            return ActionResult(False, "out_of_bounds")
        index = self._index(action.row, action.col)
        if self.board[index] != 0:
            return ActionResult(False, "occupied")
        player = self.current_player
        self.board[index] = player
        self.move_count += 1
        if self._wins_at(action.row, action.col, player):
            self.winner = player
            return ActionResult(True, outcome="win", payload={"player": player})
        if self.move_count == self.size * self.size:
            self.draw = True
            return ActionResult(True, outcome="draw")
        self.current_player = 3 - player
        return ActionResult(True, outcome="continue", payload={"next_player": self.current_player})

    def outcome(self) -> Optional[str]:
        if self.winner is not None:
            return f"player_{self.winner}_win"
        if self.draw:
            return "draw"
        return None

    def get_result(self) -> dict[str, Any]:
        return {"outcome": self.outcome(), "winner": self.winner,
                "draw": self.draw, "moves": self.move_count}

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_version": 1,
            "ruleset_id": self.ruleset_id,
            "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "size": self.size,
            "win_length": self.win_length,
            "board": list(self.board),
            "current_player": self.current_player,
            "winner": self.winner,
            "draw": self.draw,
            "move_count": self.move_count,
            "paused": self.paused,
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        size = int(data["size"])
        win_length = int(data["win_length"])
        board = [int(x) for x in data["board"]]
        if len(board) != size * size or any(x not in (0, 1, 2) for x in board):
            raise ValueError("invalid Gomoku board")
        if size < win_length or win_length < 3:
            raise ValueError("invalid Gomoku dimensions")
        self.size, self.win_length, self.board = size, win_length, board
        self.current_player = int(data["current_player"])
        if self.current_player not in (1, 2):
            raise ValueError("invalid current player")
        self.winner = data.get("winner")
        self.draw = bool(data.get("draw", False))
        self.move_count = int(data.get("move_count", sum(x != 0 for x in board)))
        self.paused = bool(data.get("paused", False))
        if self.winner not in (None, 1, 2):
            raise ValueError("invalid winner")

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "GomokuGame":
        game = cls(int(data["size"]), int(data["win_length"]))
        game.load_state(data)
        return game

    def dispose(self) -> None:
        self.paused = True

