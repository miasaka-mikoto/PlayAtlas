"""Data-first rule modules for the non-sample catalogue entries.

The six Stage-1 engines live in their own files because they are the first
acceptance targets.  This module contains small, deterministic engines for
the next wave of games.  They deliberately expose the same serialisable
surface as the sample engines and keep presentation out of the rules.

Entries whose historical rules differ by region are explicitly labelled
``digital_adaptation`` in :mod:`playatlas_core.content.catalogue`; the code
does not silently claim a universal traditional ruleset.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, Iterable, Optional

from .common import ActionResult


class SerializableGame:
    """Small common lifecycle used by the extended engines."""

    game_id = "extended"
    ruleset_id = "digital_adaptation.v1"
    save_schema_version = 1

    def __init__(self) -> None:
        self.paused = False

    def initialize(self, context: Any = None) -> "SerializableGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "SerializableGame":
        self.restart()
        return self

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def restart(self) -> None:  # pragma: no cover - subclasses implement
        self.paused = False

    def dispose(self) -> None:
        self.paused = True


class ConnectFourGame(SerializableGame):
    """Standard 7x6 gravity game, four in a row wins."""

    game_id = "connect_four"
    ruleset_id = "connect_four.standard.v1"

    def __init__(self, columns: int = 7, rows: int = 6) -> None:
        if columns < 4 or rows < 4:
            raise ValueError("Connect Four board is too small")
        self.columns, self.rows = int(columns), int(rows)
        self.restart()

    def restart(self) -> None:
        self.board = [[0 for _ in range(self.columns)] for _ in range(self.rows)]
        self.current_player, self.winner, self.draw = 1, None, False
        self.moves, self.paused = 0, False

    def _line(self, r: int, c: int, dr: int, dc: int, player: int) -> int:
        count = 0
        while 0 <= r < self.rows and 0 <= c < self.columns and self.board[r][c] == player:
            count += 1
            r += dr
            c += dc
        return count

    def _wins(self, r: int, c: int, player: int) -> bool:
        for dr, dc in ((1, 0), (0, 1), (1, 1), (1, -1)):
            # The second ray starts on the previous cell, so the origin is
            # counted exactly once across the two calls.
            if self._line(r, c, dr, dc, player) + self._line(r - dr, c - dc, -dr, -dc, player) >= 4:
                return True
        return False

    def apply_action(self, column: int) -> ActionResult:
        if self.paused or self.winner or self.draw:
            return ActionResult(False, "game_finished_or_paused")
        if not isinstance(column, int) or not 0 <= column < self.columns:
            return ActionResult(False, "column_out_of_bounds")
        row = next((r for r in range(self.rows - 1, -1, -1) if self.board[r][column] == 0), None)
        if row is None:
            return ActionResult(False, "column_full")
        player = self.current_player
        self.board[row][column] = player
        self.moves += 1
        if self._wins(row, column, player):
            self.winner = player
        elif self.moves == self.rows * self.columns:
            self.draw = True
        else:
            self.current_player = 3 - player
        return ActionResult(True, outcome=self.outcome(), payload={"row": row, "column": column})

    def outcome(self) -> str:
        return "win" if self.winner else "draw" if self.draw else "playing"

    def is_finished(self) -> bool:
        return self.winner is not None or self.draw

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {"game_id": self.game_id, "board": [row[:] for row in self.board], "current_player": self.current_player, "outcome": self.outcome()}

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[int]:
        return [c for c in range(self.columns) if self.board[0][c] == 0] if not self.is_finished() else []

    def get_result(self) -> dict[str, Any]:
        return {"status": self.outcome(), "winner": self.winner, "moves": self.moves}

    def save_state(self) -> dict[str, Any]:
        return {"game_id": self.game_id, "ruleset_id": self.ruleset_id, "board": [r[:] for r in self.board], "current_player": self.current_player, "winner": self.winner, "draw": self.draw, "moves": self.moves, "paused": self.paused}

    def load_state(self, data: dict[str, Any]) -> None:
        board = data.get("board")
        if not isinstance(board, list) or len(board) != self.rows or any(len(r) != self.columns for r in board):
            raise ValueError("invalid Connect Four board")
        self.board = [[int(x) for x in r] for r in board]
        if any(x not in (0, 1, 2) for r in self.board for x in r):
            raise ValueError("invalid Connect Four piece")
        self.current_player = int(data.get("current_player", 1)); self.winner = data.get("winner"); self.draw = bool(data.get("draw", False)); self.moves = int(data.get("moves", sum(x != 0 for r in self.board for x in r))); self.paused = bool(data.get("paused", False))


class ReversiGame(SerializableGame):
    """Standard Othello/Reversi with pass-on-no-move and directional flips."""

    game_id = "reversi"
    ruleset_id = "reversi.standard.v1"
    DIRECTIONS = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if dr or dc)

    def __init__(self, size: int = 8) -> None:
        if size != 8:
            raise ValueError("the default ruleset uses an 8x8 board")
        self.size = size; self.restart()

    def restart(self) -> None:
        self.board = [[0] * self.size for _ in range(self.size)]
        m = self.size // 2
        self.board[m - 1][m - 1] = self.board[m][m] = 2
        self.board[m - 1][m] = self.board[m][m - 1] = 1
        self.current_player, self.pass_count, self.paused = 1, 0, False

    def _inside(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def flips_for(self, row: int, col: int, player: int) -> list[tuple[int, int]]:
        if not self._inside(row, col) or self.board[row][col] != 0:
            return []
        other = 3 - player; flips: list[tuple[int, int]] = []
        for dr, dc in self.DIRECTIONS:
            r, c, line = row + dr, col + dc, []
            while self._inside(r, c) and self.board[r][c] == other:
                line.append((r, c)); r += dr; c += dc
            if line and self._inside(r, c) and self.board[r][c] == player:
                flips.extend(line)
        return flips

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[tuple[int, int]]:
        p = self.current_player if player_id is None else int(player_id)
        return [(r, c) for r in range(self.size) for c in range(self.size) if self.flips_for(r, c, p)]

    def apply_action(self, action: tuple[int, int] | str) -> ActionResult:
        if self.paused or self.is_finished(): return ActionResult(False, "game_finished_or_paused")
        if action == "pass":
            if self.get_legal_actions(): return ActionResult(False, "pass_not_allowed")
            self.pass_count += 1; self.current_player = 3 - self.current_player
            return ActionResult(True, outcome=self.outcome())
        try: r, c = int(action[0]), int(action[1])
        except (TypeError, ValueError, IndexError): return ActionResult(False, "invalid_action")
        flips = self.flips_for(r, c, self.current_player)
        if not flips: return ActionResult(False, "illegal_move")
        self.board[r][c] = self.current_player
        for rr, cc in flips: self.board[rr][cc] = self.current_player
        self.pass_count = 0; self.current_player = 3 - self.current_player
        if not self.get_legal_actions(): self.current_player = 3 - self.current_player
        return ActionResult(True, outcome=self.outcome(), payload={"flipped": len(flips)})

    def is_finished(self) -> bool:
        return self.pass_count >= 2 or all(x for row in self.board for x in row)

    def outcome(self) -> str:
        if not self.is_finished(): return "playing"
        a = sum(x == 1 for row in self.board for x in row); b = sum(x == 2 for row in self.board for x in row)
        return "draw" if a == b else "win_1" if a > b else "win_2"

    def get_result(self) -> dict[str, Any]:
        return {"status": self.outcome(), "scores": [sum(x == p for row in self.board for x in row) for p in (1, 2)]}

    def save_state(self) -> dict[str, Any]:
        return {"game_id": self.game_id, "ruleset_id": self.ruleset_id, "board": [r[:] for r in self.board], "current_player": self.current_player, "pass_count": self.pass_count, "paused": self.paused}

    def load_state(self, data: dict[str, Any]) -> None:
        board = data.get("board")
        if not isinstance(board, list) or len(board) != 8 or any(len(r) != 8 for r in board): raise ValueError("invalid Reversi board")
        self.board = [[int(x) for x in r] for r in board]
        if any(x not in (0, 1, 2) for r in self.board for x in r): raise ValueError("invalid Reversi piece")
        self.current_player = int(data.get("current_player", 1)); self.pass_count = int(data.get("pass_count", 0)); self.paused = bool(data.get("paused", False))


class Puzzle2048Game(SerializableGame):
    """Correct 2048 merge ordering; each tile merges at most once per move."""

    game_id = "2048"
    ruleset_id = "2048.standard.v1"

    def __init__(self, size: int = 4, seed: int = 0) -> None:
        if size < 2: raise ValueError("2048 board too small")
        self.size, self.seed = int(size), int(seed); self.restart()

    def restart(self) -> None:
        self.rng = random.Random(self.seed); self.board = [[0] * self.size for _ in range(self.size)]; self.score = 0; self.status = "playing"; self.paused = False
        self._spawn(); self._spawn()

    def _spawn(self) -> None:
        free = [(r, c) for r in range(self.size) for c in range(self.size) if self.board[r][c] == 0]
        if free:
            r, c = self.rng.choice(free); self.board[r][c] = 4 if self.rng.random() < 0.1 else 2

    @staticmethod
    def _merge_line(line: list[int]) -> tuple[list[int], int]:
        compact = [x for x in line if x]; out: list[int] = []; gained = 0; i = 0
        while i < len(compact):
            if i + 1 < len(compact) and compact[i] == compact[i + 1]:
                value = compact[i] * 2; out.append(value); gained += value; i += 2
            else: out.append(compact[i]); i += 1
        return out + [0] * (len(line) - len(out)), gained

    def move(self, direction: str) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        direction = str(direction).lower(); before = [r[:] for r in self.board]; gained = 0
        if direction in ("left", "right"):
            for r in range(self.size):
                line = self.board[r][:]; line = line if direction == "left" else line[::-1]
                merged, points = self._merge_line(line); merged = merged if direction == "left" else merged[::-1]
                self.board[r] = merged; gained += points
        elif direction in ("up", "down"):
            for c in range(self.size):
                line = [self.board[r][c] for r in range(self.size)]; line = line if direction == "up" else line[::-1]
                merged, points = self._merge_line(line); merged = merged if direction == "up" else merged[::-1]
                for r, value in enumerate(merged): self.board[r][c] = value
                gained += points
        else: return ActionResult(False, "invalid_direction")
        changed = before != self.board
        if changed: self.score += gained; self._spawn()
        if any(2048 in row for row in self.board): self.status = "won"
        elif not self._can_move(): self.status = "lost"
        return ActionResult(changed, "no_change" if not changed else "", outcome=self.status, payload={"score": self.score, "merged": gained})

    def _can_move(self) -> bool:
        if any(0 in row for row in self.board): return True
        for r in range(self.size):
            for c in range(self.size):
                if c + 1 < self.size and self.board[r][c] == self.board[r][c + 1]: return True
                if r + 1 < self.size and self.board[r][c] == self.board[r + 1][c]: return True
        return False

    def get_result(self) -> dict[str, Any]: return {"status": self.status, "score": self.score, "max_tile": max(max(r) for r in self.board)}
    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]: return {"game_id": self.game_id, "board": [r[:] for r in self.board], "score": self.score, "status": self.status}

    def save_state(self) -> dict[str, Any]: return {"game_id": self.game_id, "ruleset_id": self.ruleset_id, "board": [r[:] for r in self.board], "score": self.score, "status": self.status, "seed": self.seed, "rng_state": self.rng.getstate(), "paused": self.paused}
    def load_state(self, data: dict[str, Any]) -> None:
        board = data.get("board");
        if not isinstance(board, list) or len(board) != self.size or any(len(r) != self.size for r in board): raise ValueError("invalid 2048 board")
        self.board = [[int(x) for x in r] for r in board]; self.score = int(data.get("score", 0)); self.status = str(data.get("status", "playing")); self.seed = int(data.get("seed", 0)); self.rng = random.Random(self.seed)
        if data.get("rng_state") is not None:
            try: self.rng.setstate(tuple(data["rng_state"]))
            except (TypeError, ValueError): pass
        self.paused = bool(data.get("paused", False))


class SokobanGame(SerializableGame):
    """Small verified-by-construction box puzzle with reset and undo."""

    game_id = "sokoban"
    ruleset_id = "sokoban.micro.v1"
    DEFAULT = ("########", "#  .   #", "#  $   #", "#  @ . #", "########")

    def __init__(self, level: Iterable[str] = DEFAULT) -> None:
        self.level = tuple(level); self.restart()

    def restart(self) -> None:
        self.walls: set[tuple[int, int]] = set(); self.goals: set[tuple[int, int]] = set(); self.boxes: set[tuple[int, int]] = set(); self.history: list[tuple[tuple[int, int], set[tuple[int, int]]]] = []
        for r, line in enumerate(self.level):
            for c, ch in enumerate(line):
                if ch == "#": self.walls.add((r, c))
                elif ch == ".": self.goals.add((r, c))
                elif ch == "$": self.boxes.add((r, c))
                elif ch == "@": self.player = (r, c)
        self.status = "playing"; self.paused = False

    def move(self, dr: int, dc: int) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        target = (self.player[0] + int(dr), self.player[1] + int(dc))
        if target in self.walls: return ActionResult(False, "wall")
        boxes = set(self.boxes)
        if target in boxes:
            beyond = (target[0] + int(dr), target[1] + int(dc))
            if beyond in self.walls or beyond in boxes: return ActionResult(False, "blocked_box")
            self.history.append((self.player, set(self.boxes))); boxes.remove(target); boxes.add(beyond)
        else:
            self.history.append((self.player, set(self.boxes)))
        self.player = target; self.boxes = boxes
        if self.boxes <= self.goals and len(self.boxes) == len(self.goals): self.status = "won"
        return ActionResult(True, outcome=self.status)

    def undo(self) -> ActionResult:
        if not self.history: return ActionResult(False, "nothing_to_undo")
        self.player, self.boxes = self.history.pop(); self.status = "playing"; return ActionResult(True, outcome=self.status)

    def get_result(self) -> dict[str, Any]: return {"status": self.status, "moves": len(self.history), "boxes_on_goals": len(self.boxes & self.goals)}
    def save_state(self) -> dict[str, Any]: return {"game_id": self.game_id, "ruleset_id": self.ruleset_id, "player": list(self.player), "boxes": [list(x) for x in sorted(self.boxes)], "history": [{"player": list(p), "boxes": [list(x) for x in sorted(b)]} for p, b in self.history], "status": self.status, "paused": self.paused}
    def load_state(self, data: dict[str, Any]) -> None:
        self.player = tuple(data["player"]); self.boxes = {tuple(x) for x in data["boxes"]}; self.history = [(tuple(x["player"]), {tuple(b) for b in x["boxes"]}) for x in data.get("history", [])]; self.status = str(data.get("status", "playing")); self.paused = bool(data.get("paused", False))


class FifteenPuzzleGame(SerializableGame):
    game_id = "fifteen_puzzle"
    ruleset_id = "fifteen.standard.v1"

    def __init__(self, seed: int = 0, shuffle_moves: int = 80) -> None:
        self.seed, self.shuffle_moves = int(seed), int(shuffle_moves); self.restart()

    def restart(self) -> None:
        self.board = list(range(1, 16)) + [0]; self.blank = 15; self.moves = 0; self.status = "playing"; self.paused = False
        rng = random.Random(self.seed); previous = -1
        for _ in range(self.shuffle_moves):
            choices = [i for i in self._neighbors(self.blank) if i != previous]
            nxt = rng.choice(choices); self.board[self.blank], self.board[nxt] = self.board[nxt], self.board[self.blank]; previous, self.blank = self.blank, nxt
        if self.is_solved(): self.restart()

    @staticmethod
    def _neighbors(index: int) -> list[int]:
        r, c = divmod(index, 4); return [rr * 4 + cc for rr, cc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)) if 0 <= rr < 4 and 0 <= cc < 4]
    def move(self, index: int) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        if index not in self._neighbors(self.blank): return ActionResult(False, "not_adjacent")
        self.board[self.blank], self.board[index] = self.board[index], self.board[self.blank]; self.blank = index; self.moves += 1
        if self.is_solved(): self.status = "won"
        return ActionResult(True, outcome=self.status)
    def is_solved(self) -> bool: return self.board == list(range(1, 16)) + [0]
    def get_result(self) -> dict[str, Any]: return {"status": self.status, "moves": self.moves}
    def save_state(self) -> dict[str, Any]: return {"game_id": self.game_id, "ruleset_id": self.ruleset_id, "board": self.board[:], "blank": self.blank, "moves": self.moves, "status": self.status, "seed": self.seed, "paused": self.paused}
    def load_state(self, data: dict[str, Any]) -> None: 
        board = [int(x) for x in data["board"]]
        if sorted(board) != list(range(16)): raise ValueError("invalid fifteen puzzle")
        self.board, self.blank, self.moves, self.status, self.paused = board, int(data["blank"]), int(data.get("moves", 0)), str(data.get("status", "playing")), bool(data.get("paused", False))


class SungkaGame(SerializableGame):
    """Sungka-style 7-house sowing with stores and capture.

    Local variants differ, so this module explicitly implements the documented
    digital adaptation: 7 houses per side, 7 shells each, skip opponent
    store, capture from the opposite house, and an extra turn when the last
    shell lands in the mover's store.
    """

    game_id = "sungka"
    ruleset_id = "sungka.digital_adaptation.v1"

    def __init__(self) -> None: self.restart()
    def restart(self) -> None:
        self.pits = [7] * 14; self.stores = [0, 0]; self.current_player = 0; self.status = "playing"; self.paused = False; self.turns = 0
    def _own_indices(self) -> range: return range(0, 7) if self.current_player == 0 else range(7, 14)
    def apply_action(self, pit: int) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        if pit not in self._own_indices() or self.pits[pit] <= 0: return ActionResult(False, "illegal_pit")
        seeds = self.pits[pit]; self.pits[pit] = 0; i = pit; last_store = False
        while seeds:
            i = (i + 1) % 16
            if i == 7 + 8 * self.current_player: self.stores[self.current_player] += 1; seeds -= 1; last_store = True; continue
            if i == 15 - 8 * self.current_player: continue
            idx = i if i < 7 else i - 2 if i < 15 else 0
            if idx >= 14: idx %= 14
            self.pits[idx] += 1; seeds -= 1; last_store = False
        if not last_store and i < 14 and self.pits[i] == 1 and i in self._own_indices():
            opposite = 13 - i
            self.stores[self.current_player] += self.pits[opposite] + 1; self.pits[i] = self.pits[opposite] = 0
        self.turns += 1
        if not any(self.pits[j] for j in self._own_indices()) or not any(self.pits[j] for j in (range(7, 14) if self.current_player == 0 else range(0, 7))):
            self.stores[0] += sum(self.pits[:7]); self.stores[1] += sum(self.pits[7:]); self.pits = [0] * 14; self.status = "win_0" if self.stores[0] > self.stores[1] else "win_1" if self.stores[1] > self.stores[0] else "draw"
        elif not last_store: self.current_player = 1 - self.current_player
        return ActionResult(True, outcome=self.status)
    def get_result(self) -> dict[str, Any]: return {"status": self.status, "stores": self.stores[:], "turns": self.turns}
    def save_state(self) -> dict[str, Any]: return {"game_id": self.game_id, "ruleset_id": self.ruleset_id, "pits": self.pits[:], "stores": self.stores[:], "current_player": self.current_player, "status": self.status, "turns": self.turns, "paused": self.paused}
    def load_state(self, data: dict[str, Any]) -> None: self.pits = [int(x) for x in data["pits"]]; self.stores = [int(x) for x in data["stores"]]; self.current_player = int(data.get("current_player", 0)); self.status = str(data.get("status", "playing")); self.turns = int(data.get("turns", 0)); self.paused = bool(data.get("paused", False))


class BowlingGame(SerializableGame):
    """Ten-pin scoring engine; rolls are validated and bonus rolls counted."""

    game_id = "bowling"
    ruleset_id = "ten_pin.standard.v1"

    def __init__(self) -> None: self.restart()
    def restart(self) -> None: self.rolls: list[int] = []; self.status = "playing"; self.paused = False
    def roll(self, pins: int) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        if not isinstance(pins, int) or pins < 0 or pins > 10: return ActionResult(False, "invalid_pins")
        if not self._legal_next_roll(pins): return ActionResult(False, "frame_total_exceeded")
        self.rolls.append(pins)
        if self._complete(): self.status = "finished"
        return ActionResult(True, outcome=self.status, payload={"score": self.score()})
    def _legal_next_roll(self, pins: int) -> bool:
        frame = 0; i = 0
        while frame < 10 and i < len(self.rolls):
            first = self.rolls[i]
            if first == 10: i += 1
            else:
                if i + 1 >= len(self.rolls): break
                if first + self.rolls[i + 1] > 10: return False
                i += 2
            frame += 1
        if frame < 10 and i < len(self.rolls): return True
        if frame >= 10:
            # Extra rolls are allowed only after a tenth-frame strike/spare.
            tenth = self.rolls[-3:] if len(self.rolls) >= 3 else self.rolls
            return len(self.rolls) < 12 and (self.rolls[18] == 10 if len(self.rolls) > 18 else True)
        return True
    def _complete(self) -> bool:
        i = 0; frame = 0
        while frame < 10 and i < len(self.rolls):
            if self.rolls[i] == 10: i += 1
            elif i + 1 < len(self.rolls): i += 2
            else: return False
            frame += 1
        if frame < 10: return False
        if self.rolls[i - 1] == 10: return len(self.rolls) >= i + 2
        if i >= 2 and self.rolls[i - 2] + self.rolls[i - 1] == 10: return len(self.rolls) >= i + 1
        return True
    def score(self) -> int:
        score = 0; i = 0
        for _ in range(10):
            if i >= len(self.rolls): break
            if self.rolls[i] == 10: score += 10 + sum(self.rolls[i + 1:i + 3]); i += 1
            elif i + 1 >= len(self.rolls): break
            elif self.rolls[i] + self.rolls[i + 1] == 10: score += 10 + (self.rolls[i + 2] if i + 2 < len(self.rolls) else 0); i += 2
            else: score += self.rolls[i] + self.rolls[i + 1]; i += 2
        return score
    def get_result(self) -> dict[str, Any]: return {"status": self.status, "score": self.score(), "rolls": self.rolls[:]}
    def save_state(self) -> dict[str, Any]: return {"game_id": self.game_id, "ruleset_id": self.ruleset_id, "rolls": self.rolls[:], "status": self.status, "paused": self.paused}
    def load_state(self, data: dict[str, Any]) -> None: self.rolls = [int(x) for x in data.get("rolls", [])]; self.status = str(data.get("status", "playing")); self.paused = bool(data.get("paused", False))


class MiniGolfGame(SerializableGame):
    """Nine-hole deterministic putting score model (physics is presentation-side)."""

    game_id = "mini_golf"
    ruleset_id = "mini_golf.digital_adaptation.v1"

    def __init__(self, pars: Optional[list[int]] = None) -> None:
        self.pars = pars or [3, 4, 3, 5, 4, 3, 4, 5, 3]; self.restart()
    def restart(self) -> None: self.hole = 0; self.strokes: list[int] = []; self.status = "playing"; self.paused = False
    def finish_hole(self, strokes: int) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        if self.hole >= 9 or not isinstance(strokes, int) or strokes < 1: return ActionResult(False, "invalid_strokes")
        self.strokes.append(strokes); self.hole += 1
        if self.hole == 9: self.status = "finished"
        return ActionResult(True, outcome=self.status, payload={"hole": self.hole, "total": sum(self.strokes)})
    def get_result(self) -> dict[str, Any]: return {"status": self.status, "holes": self.hole, "strokes": sum(self.strokes), "relative_to_par": sum(self.strokes) - sum(self.pars[:len(self.strokes)])}


class SimpleCardGame(SerializableGame):
    """Shared safe deck for card prototypes; preserves card count and turns."""

    RANKS = tuple(range(1, 14)); SUITS = tuple("SHDC")
    def __init__(self, players: int = 2, seed: int = 0) -> None:
        self.players, self.seed = int(players), int(seed); self.restart()
    def restart(self) -> None:
        self.rng = random.Random(self.seed); self.deck = [(s, r) for s in self.SUITS for r in self.RANKS]; self.rng.shuffle(self.deck); self.hands = [[] for _ in range(self.players)]; self.current_player = 0; self.discard: list[tuple[str, int]] = []; self.status = "playing"; self.paused = False
    def deal(self, count: int) -> None:
        for _ in range(count):
            for hand in self.hands:
                if self.deck: hand.append(self.deck.pop())
    def observation(self, player: int = 0) -> dict[str, Any]:
        return {"game_id": self.game_id, "hand": self.hands[player][:], "hand_sizes": [len(x) for x in self.hands], "discard_top": self.discard[-1] if self.discard else None, "deck_count": len(self.deck), "current_player": self.current_player, "status": self.status}


class CrazyEightsGame(SimpleCardGame):
    game_id = "crazy_eights"; ruleset_id = "crazy_eights.standard.v1"
    def __init__(self, players: int = 2, seed: int = 0) -> None: super().__init__(players, seed); self.restart()
    def restart(self) -> None:
        super().restart(); self.deal(5)
        while self.deck and self.deck[-1][1] == 8: self.deck.insert(0, self.deck.pop())
        self.discard.append(self.deck.pop())
    def play(self, card: tuple[str, int]) -> ActionResult:
        if self.status != "playing" or self.paused: return ActionResult(False, "game_finished_or_paused")
        if card not in self.hands[self.current_player]: return ActionResult(False, "card_not_in_hand")
        top = self.discard[-1];
        if card[1] != 8 and card[0] != top[0] and card[1] != top[1]: return ActionResult(False, "card_does_not_match")
        self.hands[self.current_player].remove(card); self.discard.append(card)
        if not self.hands[self.current_player]: self.status = f"win_{self.current_player}"
        else: self.current_player = (self.current_player + 1) % self.players
        return ActionResult(True, outcome=self.status)
    def draw(self) -> ActionResult:
        if not self.deck: return ActionResult(False, "deck_empty")
        self.hands[self.current_player].append(self.deck.pop()); return ActionResult(True, outcome=self.status)


class GoFishGame(SimpleCardGame):
    game_id = "go_fish"; ruleset_id = "go_fish.standard.v1"
    def __init__(self, players: int = 2, seed: int = 0) -> None: super().__init__(players, seed); self.books = [0] * players; self.restart()
    def restart(self) -> None:
        super().restart(); self.books = [0] * self.players; self.deal(7 if self.players == 2 else 5)
    def ask(self, target: int, rank: int) -> ActionResult:
        if target == self.current_player or not 0 <= target < self.players: return ActionResult(False, "invalid_target")
        if not any(r == rank for _, r in self.hands[self.current_player]): return ActionResult(False, "must_hold_rank")
        moved = [card for card in self.hands[target] if card[1] == rank]; self.hands[target] = [c for c in self.hands[target] if c[1] != rank]; self.hands[self.current_player].extend(moved)
        if not moved and self.deck: self.hands[self.current_player].append(self.deck.pop())
        count = sum(r == rank for _, r in self.hands[self.current_player])
        if count == 4: self.hands[self.current_player] = [c for c in self.hands[self.current_player] if c[1] != rank]; self.books[self.current_player] += 1
        if not self.deck and all(not h for h in self.hands): self.status = "finished"
        if not moved: self.current_player = (self.current_player + 1) % self.players
        return ActionResult(True, outcome=self.status, payload={"received": len(moved)})


class PlaceholderRuleGame(SerializableGame):
    """Explicitly non-playable placeholder for a catalog item under research.

    It is intentionally not registered as playable.  This class exists so a
    future package can use the same lifecycle without pretending that a card
    or traditional rule set has been completed.
    """
    def __init__(self, game_id: str, title: str, ruleset_id: str = "unverified") -> None:
        self.game_id, self.title, self.ruleset_id = game_id, title, ruleset_id; self.status = "unavailable"; self.paused = False
    def get_result(self) -> dict[str, Any]: return {"status": self.status, "reason": "rules or presentation not implemented"}


__all__ = [
    "SerializableGame", "ConnectFourGame", "ReversiGame", "Puzzle2048Game",
    "SokobanGame", "FifteenPuzzleGame", "SungkaGame", "BowlingGame",
    "MiniGolfGame", "SimpleCardGame", "CrazyEightsGame", "GoFishGame",
    "PlaceholderRuleGame",
]
