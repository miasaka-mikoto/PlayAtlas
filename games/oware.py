"""Oware (Abapa) mancala rules, independent of rendering.

Ruleset ``oware.abapa.v1``
--------------------------
* Two rows of six pits, four seeds per pit at the start.
* Seeds are sown counter-clockwise; the source pit is skipped when a lap
  would return to it.
* A capture is made backwards from the final pit on the opponent's side,
  taking consecutive pits containing exactly two or three seeds.
* Starvation is enforced: if the opponent has no seeds, a move that can feed
  the opponent is required.  A capture that would take every opponent seed is
  not allowed.
* If no legal move exists, remaining seeds are awarded to their owners;
  reaching 25 seeds wins and 24-24 is a draw.

This is a documented, common Abapa ruleset; regional variants remain separate
content records rather than being silently mixed into this engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .common import ActionResult


@dataclass(frozen=True)
class OwareResult:
    status: str  # playing, player_0_win, player_1_win, draw
    scores: tuple[int, int]
    pits: tuple[int, ...]


class OwareGame:
    game_id = "oware"
    ruleset_id = "oware.abapa.v1"
    save_schema_version = 1

    def __init__(self, seeds_per_pit: int = 4) -> None:
        if seeds_per_pit <= 0:
            raise ValueError("seeds_per_pit must be positive")
        self.seeds_per_pit = int(seeds_per_pit)
        self.restart()

    def initialize(self, context: Any = None) -> "OwareGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "OwareGame":
        if config and "seeds_per_pit" in config:
            self.seeds_per_pit = int(config["seeds_per_pit"])
            if self.seeds_per_pit <= 0:
                raise ValueError("seeds_per_pit must be positive")
        self.restart()
        return self

    def restart(self) -> None:
        self.pits: list[int] = [self.seeds_per_pit] * 12
        self.scores = [0, 0]
        self.current_player = 0
        self.status = "playing"
        self.move_count = 0
        self.paused = False
        self.last_error = ""

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    @staticmethod
    def _side(player: int) -> range:
        return range(0, 6) if player == 0 else range(6, 12)

    @staticmethod
    def _opponent_side(player: int) -> range:
        return range(6, 12) if player == 0 else range(0, 6)

    def _opponent(self, player: int) -> int:
        return 1 - player

    def _sow_without_capture(self, start: int) -> tuple[list[int], int, list[int]]:
        board = list(self.pits)
        count = board[start]
        board[start] = 0
        cursor = start
        visited: list[int] = []
        while count:
            cursor = (cursor + 1) % 12
            if cursor == start:
                # Abapa skips the source pit on subsequent laps.
                continue
            board[cursor] += 1
            visited.append(cursor)
            count -= 1
        return board, cursor, visited

    def _capture_from(self, board: list[int], last: int, player: int) -> tuple[int, list[int]]:
        opponent = self._opponent(player)
        if last not in self._opponent_side(player):
            return 0, []
        captured_indices: list[int] = []
        cursor = last
        while cursor in self._opponent_side(player) and board[cursor] in (2, 3):
            captured_indices.append(cursor)
            cursor = (cursor - 1) % 12
        total = sum(board[i] for i in captured_indices)
        opponent_total = sum(board[i] for i in self._opponent_side(player))
        # Feeding is mandatory; taking the opponent's last seeds is therefore
        # forbidden.  The sow still stands, but no capture is made.
        if total and total == opponent_total:
            return 0, []
        for i in captured_indices:
            board[i] = 0
        return total, captured_indices

    def _would_feed(self, start: int) -> bool:
        board, _, visited = self._sow_without_capture(start)
        opponent = self._opponent(self.current_player)
        return any(i in self._opponent_side(self.current_player) for i in visited)

    def get_current_player(self) -> Optional[int]:
        return None if self.status != "playing" else self.current_player

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[int]:
        if self.status != "playing" or self.paused:
            return []
        player = self.current_player if player_id is None else int(player_id)
        if player != self.current_player or player not in (0, 1):
            return []
        own = [i for i in self._side(player) if self.pits[i] > 0]
        if not own:
            return []
        opponent_empty = all(self.pits[i] == 0 for i in self._opponent_side(player))
        if not opponent_empty:
            return own
        feeding = [i for i in own if self._would_feed(i)]
        return feeding or own

    def _finish_if_needed(self) -> None:
        if self.scores[0] >= 25 or self.scores[1] >= 25:
            self.status = "player_0_win" if self.scores[0] > self.scores[1] else "player_1_win"
            return
        if self.scores[0] == 24 and self.scores[1] == 24:
            self.status = "draw"
            return
        if not self.get_legal_actions(self.current_player):
            self.scores[0] += sum(self.pits[i] for i in self._side(0))
            self.scores[1] += sum(self.pits[i] for i in self._side(1))
            for i in range(12):
                self.pits[i] = 0
            if self.scores[0] > self.scores[1]:
                self.status = "player_0_win"
            elif self.scores[1] > self.scores[0]:
                self.status = "player_1_win"
            else:
                self.status = "draw"

    def apply_action(self, pit: int) -> ActionResult:
        try:
            pit = int(pit)
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_pit")
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if pit not in self.get_legal_actions():
            if pit not in range(12):
                return ActionResult(False, "out_of_bounds")
            if pit not in self._side(self.current_player):
                return ActionResult(False, "opponents_pit")
            if self.pits[pit] == 0:
                return ActionResult(False, "empty_pit")
            return ActionResult(False, "must_feed_opponent")
        player = self.current_player
        board, last, visited = self._sow_without_capture(pit)
        self.pits = board
        captured, captured_indices = self._capture_from(self.pits, last, player)
        self.scores[player] += captured
        self.move_count += 1
        self.current_player = self._opponent(player)
        self._finish_if_needed()
        return ActionResult(True, outcome=self.status,
                            payload={"player": player, "pit": pit, "last_pit": last,
                                     "sown": visited, "captured": captured,
                                     "captured_pits": captured_indices,
                                     "scores": list(self.scores)})

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "ruleset_id": self.ruleset_id,
            "pits": list(self.pits), "scores": list(self.scores),
            "current_player": self.get_current_player(), "status": self.status,
            "move_count": self.move_count,
        }

    def get_result(self) -> OwareResult:
        return OwareResult(self.status, tuple(self.scores), tuple(self.pits))

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "game_version": 1,
            "ruleset_id": self.ruleset_id, "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "seeds_per_pit": self.seeds_per_pit, "pits": list(self.pits),
            "scores": list(self.scores), "current_player": self.current_player,
            "status": self.status, "move_count": self.move_count,
            "paused": self.paused,
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        self.seeds_per_pit = int(data.get("seeds_per_pit", 4))
        self.pits = [int(x) for x in data["pits"]]
        self.scores = [int(x) for x in data["scores"]]
        if len(self.pits) != 12 or len(self.scores) != 2 or any(x < 0 for x in self.pits + self.scores):
            raise ValueError("invalid Oware state")
        self.current_player = int(data["current_player"])
        if self.current_player not in (0, 1):
            raise ValueError("invalid current player")
        self.status = str(data.get("status", "playing"))
        if self.status not in ("playing", "player_0_win", "player_1_win", "draw"):
            raise ValueError("invalid Oware status")
        self.move_count = int(data.get("move_count", 0))
        self.paused = bool(data.get("paused", False))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "OwareGame":
        game = cls(int(data.get("seeds_per_pit", 4)))
        game.load_state(data)
        return game

    def dispose(self) -> None:
        self.paused = True

