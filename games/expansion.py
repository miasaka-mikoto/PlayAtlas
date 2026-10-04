"""Deterministic rule engines for the next PlayAtlas content wave.

The classes in this module deliberately contain no Godot/UI objects.  They
are small, serialisable state machines which can be driven by a desktop or
touch presentation layer.  Each ruleset is labelled as a digital adaptation
where the historical game has no single universally binding rules document.

Implemented games
------------------
``BreakoutGame``
    A classic paddle-and-brick arcade ruleset (one ball, three lives, clear
    all bricks to win).  Physics is fixed-step and deterministic.
``SudokuGame``
    Classic 9x9 Sudoku/Number Place.  Puzzle generation removes clues only
    when a real backtracking solver still reports exactly one solution.
``MatchingTilesGame`` / ``ShisenShoGame``
    Shisen-Sho matching with an orthogonal path of at most two turns.  A
    one-cell outside border is allowed, as in the common digital adaptation.
``DotsAndBoxesGame``
    Standard edge-drawing play: a completed box scores and grants another
    turn; the highest score wins.

The public methods intentionally mirror the Stage-1 engines: ``restart``,
``apply_action``/input methods, ``get_observation``, ``get_result``,
``save_state`` and ``load_state``.  Ordinary illegal moves return an explicit
``ActionResult(False, reason=...)`` rather than mutating state.
"""

from __future__ import annotations

from collections import deque
import math
import random
from typing import Any, Optional, Sequence

from .common import ActionResult


# ---------------------------------------------------------------------------
# Shared helpers


def _copy_grid(grid: Sequence[Sequence[int]]) -> list[list[int]]:
    return [[int(value) for value in row] for row in grid]


def _jsonable_tuple(value: Any) -> Any:
    """Convert ``random.Random.getstate``'s nested tuples to JSON values."""

    if isinstance(value, tuple):
        return [_jsonable_tuple(item) for item in value]
    if isinstance(value, list):
        return [_jsonable_tuple(item) for item in value]
    return value


def _tuple_state(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tuple_state(item) for item in value)
    return value


# ---------------------------------------------------------------------------
# Breakout


class BreakoutGame:
    """A compact deterministic brick-breaker rules engine.

    Ruleset ``brick-breaker-classic-v1`` is a PlayAtlas digital adaptation:
    one paddle reflects one ball, each brick takes one hit, a lost ball costs
    a life, and clearing every brick wins the run.  It intentionally does not
    reproduce any commercial game's level layouts, art, sounds, or power-ups.

    Coordinates are normalised to ``0..1`` so the same state can be rendered
    at any desktop or touch resolution.  ``fixed_update`` subdivides large
    time steps, which keeps collisions deterministic and limits tunnelling.
    """

    game_id = "breakout"
    ruleset_id = "brick-breaker-classic-v1"
    ruleset_version = "1.0"
    digital_adaptation = "One-ball paddle-and-bricks adaptation; clear all original PlayAtlas bricks before lives run out."
    save_schema_version = 1

    def __init__(
        self,
        columns: int = 10,
        rows: int = 5,
        seed: int = 0,
        lives: int = 3,
    ) -> None:
        if columns < 1 or rows < 1:
            raise ValueError("Breakout requires at least one row and column")
        if lives < 1:
            raise ValueError("lives must be positive")
        self.columns = int(columns)
        self.rows = int(rows)
        self.seed = int(seed)
        self.starting_lives = int(lives)
        self.restart()

    def initialize(self, context: Any = None) -> "BreakoutGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "BreakoutGame":
        if config:
            for name in ("columns", "rows", "seed", "lives"):
                if name in config:
                    setattr(self, "starting_lives" if name == "lives" else name,
                            int(config[name]))
            if self.columns < 1 or self.rows < 1 or self.starting_lives < 1:
                raise ValueError("invalid Breakout configuration")
        self.restart()
        return self

    def restart(self) -> None:
        self.paused = False
        self.status = "playing"
        self.score = 0
        self.lives = self.starting_lives
        self.paddle_x = 0.5
        self.paddle_width = 0.18
        self.paddle_speed = 0.85
        self.paddle_y = 0.93
        self.input_axis = 0.0
        self.launched = False
        self._build_bricks()
        self._reset_ball()

    def _build_bricks(self) -> None:
        # The layout is original and data-like; presentation can map row to a
        # palette without the rules engine knowing anything about colours.
        self.bricks: list[dict[str, Any]] = []
        margin = 0.012
        gap = 0.006
        width = (0.94 - 2 * margin - (self.columns - 1) * gap) / self.columns
        height = 0.038
        top = 0.075
        for row in range(self.rows):
            for col in range(self.columns):
                self.bricks.append({
                    "row": row,
                    "col": col,
                    "x": margin + col * (width + gap),
                    "y": top + row * (height + gap),
                    "w": width,
                    "h": height,
                    "hp": 1,
                })

    def _reset_ball(self) -> None:
        self.ball_x = 0.5
        self.ball_y = self.paddle_y - 0.025
        self.ball_radius = 0.012
        # Seed affects the deterministic launch angle while remaining inside
        # a safe upward cone.  No random calls occur during physics.
        angle_rng = random.Random(self.seed)
        self.ball_vx = angle_rng.uniform(-0.28, 0.28)
        self.ball_vy = -0.54
        self.launched = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def dispose(self) -> None:
        self.paused = True

    def is_finished(self) -> bool:
        return self.status in ("won", "lost")

    def outcome(self) -> str:
        return self.status

    def launch(self) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if self.launched:
            return ActionResult(False, "already_launched")
        self.launched = True
        return ActionResult(True, outcome="playing")

    def move_paddle(self, x: float) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        try:
            x = float(x)
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_position")
        if not math.isfinite(x):
            return ActionResult(False, "invalid_position")
        self.paddle_x = min(1.0 - self.paddle_width / 2,
                            max(self.paddle_width / 2, x))
        if not self.launched:
            self.ball_x = self.paddle_x
        return ActionResult(True, outcome=self.status,
                            payload={"paddle_x": self.paddle_x})

    def handle_input(self, input_frame: Any) -> ActionResult:
        """Consume keyboard/touch/gamepad-neutral input.

        Accepted values are ``"left"``, ``"right"``, ``"stop"``,
        ``"launch"``, a numeric axis in ``[-1, 1]``, or a mapping with an
        ``axis``/``action``/``x`` field.  Movement itself is applied on the
        next fixed update, except absolute ``x`` positioning which is useful
        for touch.
        """

        if isinstance(input_frame, (int, float)):
            self.input_axis = max(-1.0, min(1.0, float(input_frame)))
            return ActionResult(True, outcome=self.status)
        if isinstance(input_frame, dict):
            if "x" in input_frame:
                return self.move_paddle(float(input_frame["x"]))
            action = input_frame.get("action", input_frame.get("axis"))
        else:
            action = input_frame
        if isinstance(action, (int, float)):
            self.input_axis = max(-1.0, min(1.0, float(action)))
            return ActionResult(True, outcome=self.status)
        action = str(action).lower() if action is not None else ""
        if action in ("left", "move_left"):
            self.input_axis = -1.0
        elif action in ("right", "move_right"):
            self.input_axis = 1.0
        elif action in ("stop", "release", "none"):
            self.input_axis = 0.0
        elif action in ("launch", "start", "fire"):
            return self.launch()
        else:
            return ActionResult(False, "invalid_input")
        return ActionResult(True, outcome=self.status,
                            payload={"axis": self.input_axis})

    # The common QA/network adapter uses one neutral action entry point for
    # turn-based and real-time modules.  Keeping this thin wrapper here does
    # not change the input semantics; it simply makes the engine composable
    # with the shared GameModule contract.
    def apply_action(self, action: Any) -> ActionResult:
        return self.handle_input(action)

    @staticmethod
    def _overlap(ball_x: float, ball_y: float, radius: float,
                 brick: dict[str, Any]) -> bool:
        nearest_x = min(brick["x"] + brick["w"], max(brick["x"], ball_x))
        nearest_y = min(brick["y"] + brick["h"], max(brick["y"], ball_y))
        return ((ball_x - nearest_x) ** 2 + (ball_y - nearest_y) ** 2
                <= radius * radius)

    def _lose_ball(self) -> None:
        self.lives -= 1
        if self.lives <= 0:
            self.status = "lost"
            self.launched = False
        else:
            self._reset_ball()

    def _step(self, dt: float) -> None:
        self.paddle_x += self.input_axis * self.paddle_speed * dt
        self.paddle_x = min(1.0 - self.paddle_width / 2,
                            max(self.paddle_width / 2, self.paddle_x))
        if not self.launched:
            self.ball_x = self.paddle_x
            self.ball_y = self.paddle_y - self.ball_radius - 0.002
            return

        old_x, old_y = self.ball_x, self.ball_y
        self.ball_x += self.ball_vx * dt
        self.ball_y += self.ball_vy * dt
        r = self.ball_radius
        if self.ball_x - r <= 0.0:
            self.ball_x, self.ball_vx = r, abs(self.ball_vx)
        elif self.ball_x + r >= 1.0:
            self.ball_x, self.ball_vx = 1.0 - r, -abs(self.ball_vx)
        if self.ball_y - r <= 0.0:
            self.ball_y, self.ball_vy = r, abs(self.ball_vy)

        # Paddle collision is only valid while travelling downwards and when
        # crossing the paddle's top surface this step.
        paddle_left = self.paddle_x - self.paddle_width / 2
        paddle_right = self.paddle_x + self.paddle_width / 2
        if (self.ball_vy > 0 and old_y + r <= self.paddle_y
                and self.ball_y + r >= self.paddle_y
                and paddle_left <= self.ball_x <= paddle_right):
            self.ball_y = self.paddle_y - r
            self.ball_vy = -abs(self.ball_vy)
            offset = (self.ball_x - self.paddle_x) / (self.paddle_width / 2)
            self.ball_vx = max(-0.9, min(0.9, self.ball_vx + offset * 0.24))

        # Resolve at most one brick per sub-step.  The previous position
        # identifies the reflection axis and avoids a brick being hit twice
        # in one frame.
        for brick in self.bricks:
            if brick["hp"] <= 0 or not self._overlap(self.ball_x, self.ball_y, r, brick):
                continue
            brick["hp"] -= 1
            self.score += 10
            horizontal = old_y + r <= brick["y"] or old_y - r >= brick["y"] + brick["h"]
            if horizontal:
                self.ball_vy = -self.ball_vy
            else:
                self.ball_vx = -self.ball_vx
            break

        if all(brick["hp"] <= 0 for brick in self.bricks):
            self.status = "won"
            self.launched = False
            return
        if self.ball_y - r > 1.0:
            self._lose_ball()

    def fixed_update(self, delta: float) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_delta")
        if not math.isfinite(delta) or delta < 0:
            return ActionResult(False, "invalid_delta")
        # Cap pathological catch-up frames while preserving deterministic
        # behaviour for normal frames.
        steps = min(240, max(1, int(math.ceil(delta / 0.008)))) if delta else 1
        step = delta / steps if delta else 0.0
        for _ in range(steps):
            if self.status != "playing":
                break
            self._step(step)
        return ActionResult(True, outcome=self.status,
                            payload={"score": self.score, "lives": self.lives})

    # ``step`` is a convenient alias for fixed-step adapters and mirrors the
    # real-time Snake engine's public surface.
    step = fixed_update

    @property
    def ball(self) -> dict[str, float | bool]:
        return {"x": self.ball_x, "y": self.ball_y, "vx": self.ball_vx,
                "vy": self.ball_vy, "radius": self.ball_radius,
                "launched": self.launched}

    @ball.setter
    def ball(self, value: dict[str, Any]) -> None:
        for key in ("x", "y", "vx", "vy", "radius"):
            if key in value:
                setattr(self, "ball_" + key, float(value[key]))
        if "launched" in value:
            self.launched = bool(value["launched"])

    @property
    def paddle(self) -> dict[str, float]:
        return {"x": self.paddle_x, "y": self.paddle_y, "width": self.paddle_width}

    @paddle.setter
    def paddle(self, value: dict[str, Any]) -> None:
        if "x" in value:
            self.paddle_x = float(value["x"])
        if "width" in value:
            self.paddle_width = float(value["width"])
        self.paddle_x = min(1.0 - self.paddle_width / 2,
                            max(self.paddle_width / 2, self.paddle_x))

    def get_snapshot(self) -> dict[str, Any]:
        return self.save_state()

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.load_state(snapshot)

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "ruleset_id": self.ruleset_id,
            "status": self.status,
            "score": self.score,
            "lives": self.lives,
            "paddle": {"x": self.paddle_x, "width": self.paddle_width, "y": self.paddle_y},
            "ball": {"x": self.ball_x, "y": self.ball_y, "vx": self.ball_vx,
                     "vy": self.ball_vy, "radius": self.ball_radius, "launched": self.launched},
            "bricks": [dict(brick) for brick in self.bricks if brick["hp"] > 0],
        }

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[str]:
        if self.status != "playing" or self.paused:
            return []
        return ["left", "right", "stop", "launch"]

    def get_result(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "lives": self.lives,
            "bricks_remaining": sum(brick["hp"] > 0 for brick in self.bricks),
        }

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_version": 1,
            "ruleset_id": self.ruleset_id,
            "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "columns": self.columns,
            "rows": self.rows,
            "seed": self.seed,
            "starting_lives": self.starting_lives,
            "lives": self.lives,
            "score": self.score,
            "status": self.status,
            "paused": self.paused,
            "paddle_x": self.paddle_x,
            "input_axis": self.input_axis,
            "ball_x": self.ball_x,
            "ball_y": self.ball_y,
            "ball_vx": self.ball_vx,
            "ball_vy": self.ball_vy,
            "ball_radius": self.ball_radius,
            "launched": self.launched,
            "bricks": [dict(brick) for brick in self.bricks],
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        columns, rows = int(data.get("columns", self.columns)), int(data.get("rows", self.rows))
        if columns < 1 or rows < 1:
            raise ValueError("invalid Breakout dimensions")
        self.columns, self.rows = columns, rows
        self.seed = int(data.get("seed", 0))
        self.starting_lives = int(data.get("starting_lives", 3))
        self.lives = int(data.get("lives", self.starting_lives))
        if self.starting_lives < 1 or self.lives < 0 or self.lives > self.starting_lives:
            raise ValueError("invalid Breakout lives")
        self.score = int(data.get("score", 0))
        self.status = str(data.get("status", "playing"))
        if self.status not in ("playing", "won", "lost"):
            raise ValueError("invalid Breakout status")
        self.paused = bool(data.get("paused", False))
        self.paddle_width = 0.18
        self.paddle_speed = 0.85
        self.paddle_y = 0.93
        self.paddle_x = float(data.get("paddle_x", 0.5))
        self.input_axis = float(data.get("input_axis", 0.0))
        self.ball_x = float(data.get("ball_x", 0.5))
        self.ball_y = float(data.get("ball_y", self.paddle_y - 0.025))
        self.ball_vx = float(data.get("ball_vx", 0.0))
        self.ball_vy = float(data.get("ball_vy", -0.54))
        self.ball_radius = float(data.get("ball_radius", 0.012))
        values = (self.paddle_x, self.input_axis, self.ball_x, self.ball_y,
                  self.ball_vx, self.ball_vy, self.ball_radius)
        if any(not math.isfinite(value) for value in values) or self.ball_radius <= 0:
            raise ValueError("invalid Breakout numeric state")
        self.launched = bool(data.get("launched", False))
        raw_bricks = data.get("bricks")
        if not isinstance(raw_bricks, list) or not raw_bricks:
            raise ValueError("invalid Breakout bricks")
        self.bricks = []
        for raw in raw_bricks:
            if not isinstance(raw, dict):
                raise ValueError("invalid Breakout brick")
            brick = {key: raw[key] for key in ("row", "col", "x", "y", "w", "h", "hp")}
            brick["row"], brick["col"], brick["hp"] = int(brick["row"]), int(brick["col"]), int(brick["hp"])
            for key in ("x", "y", "w", "h"):
                brick[key] = float(brick[key])
            if brick["hp"] < 0 or brick["w"] <= 0 or brick["h"] <= 0:
                raise ValueError("invalid Breakout brick values")
            self.bricks.append(brick)
        self.paddle_x = min(1.0 - self.paddle_width / 2, max(self.paddle_width / 2, self.paddle_x))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "BreakoutGame":
        game = cls(int(data.get("columns", 10)), int(data.get("rows", 5)),
                   int(data.get("seed", 0)), int(data.get("starting_lives", 3)))
        game.load_state(data)
        return game


# ---------------------------------------------------------------------------
# Sudoku


def _sudoku_masks(grid: Sequence[Sequence[int]]) -> tuple[list[int], list[int], list[int]]:
    rows = [0] * 9
    cols = [0] * 9
    boxes = [0] * 9
    for r in range(9):
        for c in range(9):
            value = int(grid[r][c])
            if value == 0:
                continue
            if not 1 <= value <= 9:
                raise ValueError("Sudoku values must be 0..9")
            bit = 1 << (value - 1)
            box = (r // 3) * 3 + c // 3
            if rows[r] & bit or cols[c] & bit or boxes[box] & bit:
                raise ValueError("Sudoku grid has duplicate values")
            rows[r] |= bit
            cols[c] |= bit
            boxes[box] |= bit
    return rows, cols, boxes


def _sudoku_solve(grid: Sequence[Sequence[int]], limit: int = 2) -> tuple[int, Optional[list[list[int]]]]:
    """Return ``(number_of_solutions_up_to_limit, first_solution)``."""

    if len(grid) != 9 or any(len(row) != 9 for row in grid):
        raise ValueError("Sudoku grid must be 9x9")
    board = _copy_grid(grid)
    rows, cols, boxes = _sudoku_masks(board)
    full = (1 << 9) - 1
    first: Optional[list[list[int]]] = None
    count = 0

    def visit() -> None:
        nonlocal count, first
        if count >= limit:
            return
        best: Optional[tuple[int, int, int]] = None
        best_mask = 0
        for r in range(9):
            for c in range(9):
                if board[r][c] != 0:
                    continue
                box = (r // 3) * 3 + c // 3
                mask = full & ~(rows[r] | cols[c] | boxes[box])
                options = mask.bit_count()
                if options == 0:
                    return
                if best is None or options < best_mask.bit_count():
                    best = (r, c, box)
                    best_mask = mask
                    if options == 1:
                        break
            if best is not None and best_mask.bit_count() == 1:
                break
        if best is None:
            count += 1
            if first is None:
                first = _copy_grid(board)
            return
        r, c, box = best
        mask = best_mask
        while mask:
            bit = mask & -mask
            mask -= bit
            value = bit.bit_length()
            board[r][c] = value
            rows[r] |= bit
            cols[c] |= bit
            boxes[box] |= bit
            visit()
            rows[r] ^= bit
            cols[c] ^= bit
            boxes[box] ^= bit
            board[r][c] = 0
            if count >= limit:
                return

    visit()
    return count, first


def sudoku_count_solutions(grid: Sequence[Sequence[int]], limit: int = 2) -> int:
    """Count Sudoku solutions, stopping at ``limit`` (normally 2)."""

    if limit < 1:
        raise ValueError("solution limit must be positive")
    return _sudoku_solve(grid, int(limit))[0]


def sudoku_solve(grid: Sequence[Sequence[int]]) -> Optional[list[list[int]]]:
    """Return one valid solution or ``None`` when the puzzle is impossible."""

    return _sudoku_solve(grid, 1)[1]


# Descriptive aliases make the solver useful to content-generation tools
# without requiring callers to know the module's internal naming convention.
count_solutions = sudoku_count_solutions
solve_sudoku = sudoku_solve


class SudokuGame:
    """Classic 9x9 Sudoku with solver-backed uniqueness checks.

    ``sudoku-nikoli-9x9-v1`` is the fixed digital adaptation used by
    PlayAtlas: rows, columns, and 3x3 boxes each contain 1--9; generated
    puzzles are advertised as unique only after an actual solution-count
    check.  No external puzzle database or copied artwork is required.
    """

    game_id = "sudoku"
    ruleset_id = "sudoku-nikoli-9x9-v1"
    ruleset_version = "1.0"
    digital_adaptation = "Fixed 9x9 grid with solver-verified uniqueness for generated puzzles."
    save_schema_version = 1

    _TARGET_EMPTY = {"easy": 38, "medium": 48, "hard": 54}

    def __init__(
        self,
        puzzle: Optional[Sequence[Sequence[int]]] = None,
        seed: int = 0,
        difficulty: str = "medium",
    ) -> None:
        self.seed = int(seed)
        self.difficulty = str(difficulty).lower()
        if self.difficulty not in self._TARGET_EMPTY:
            raise ValueError("difficulty must be easy, medium, or hard")
        self._provided_puzzle = _copy_grid(puzzle) if puzzle is not None else None
        self.restart()

    def initialize(self, context: Any = None) -> "SudokuGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "SudokuGame":
        if config:
            if "seed" in config:
                self.seed = int(config["seed"])
            if "difficulty" in config:
                self.difficulty = str(config["difficulty"]).lower()
                if self.difficulty not in self._TARGET_EMPTY:
                    raise ValueError("invalid Sudoku difficulty")
            if "puzzle" in config:
                self._provided_puzzle = _copy_grid(config["puzzle"])
        self.restart()
        return self

    @staticmethod
    def is_valid_grid(grid: Sequence[Sequence[int]], complete: bool = False) -> bool:
        try:
            if len(grid) != 9 or any(len(row) != 9 for row in grid):
                return False
            _sudoku_masks(grid)
            if complete and any(int(value) == 0 for row in grid for value in row):
                return False
            return True
        except (TypeError, ValueError, IndexError):
            return False

    @staticmethod
    def count_solutions(grid: Sequence[Sequence[int]], limit: int = 2) -> int:
        return sudoku_count_solutions(grid, limit)

    @staticmethod
    def solve_board(grid: Sequence[Sequence[int]]) -> Optional[list[list[int]]]:
        return sudoku_solve(grid)

    @staticmethod
    def _generate_solution(seed: int) -> list[list[int]]:
        rng = random.Random(seed)
        base = [[(r * 3 + r // 3 + c) % 9 + 1 for c in range(9)] for r in range(9)]
        nums = list(range(1, 10))
        rng.shuffle(nums)
        row_groups = [list(range(i, i + 3)) for i in (0, 3, 6)]
        rng.shuffle(row_groups)
        rows: list[int] = []
        for group in row_groups:
            shuffled = group[:]
            rng.shuffle(shuffled)
            rows.extend(shuffled)
        col_groups = [list(range(i, i + 3)) for i in (0, 3, 6)]
        rng.shuffle(col_groups)
        cols: list[int] = []
        for group in col_groups:
            shuffled = group[:]
            rng.shuffle(shuffled)
            cols.extend(shuffled)
        return [[nums[base[r][c] - 1] for c in cols] for r in rows]

    def restart(self) -> None:
        if self._provided_puzzle is not None:
            puzzle = _copy_grid(self._provided_puzzle)
            if not self.is_valid_grid(puzzle):
                raise ValueError("invalid Sudoku puzzle")
            solution = sudoku_solve(puzzle)
            if solution is None:
                raise ValueError("Sudoku puzzle has no solution")
            unique = sudoku_count_solutions(puzzle, 2) == 1
        else:
            solution = self._generate_solution(self.seed)
            puzzle = _copy_grid(solution)
            rng = random.Random(self.seed ^ 0x5A17)
            cells = list(range(81))
            rng.shuffle(cells)
            target_empty = self._TARGET_EMPTY[self.difficulty]
            for index in cells:
                if sum(value == 0 for row in puzzle for value in row) >= target_empty:
                    break
                row, col = divmod(index, 9)
                old = puzzle[row][col]
                puzzle[row][col] = 0
                if sudoku_count_solutions(puzzle, 2) != 1:
                    puzzle[row][col] = old
            unique = sudoku_count_solutions(puzzle, 2) == 1
        self.solution = _copy_grid(solution)
        self.puzzle = _copy_grid(puzzle)
        self.givens = [[value != 0 for value in row] for row in puzzle]
        self.board = _copy_grid(puzzle)
        self.notes: list[list[set[int]]] = [[set() for _ in range(9)] for _ in range(9)]
        self.unique_solution = bool(unique)
        self.status = "playing"
        self.mistakes = 0
        self.paused = False

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def dispose(self) -> None:
        self.paused = True

    def is_finished(self) -> bool:
        return self.status == "won"

    def outcome(self) -> str:
        return self.status

    def _cell_ok(self, row: int, col: int) -> bool:
        return isinstance(row, int) and isinstance(col, int) and 0 <= row < 9 and 0 <= col < 9

    def get_candidates(self, row: int, col: int) -> list[int]:
        if not self._cell_ok(row, col):
            raise ValueError("Sudoku cell out of bounds")
        if self.board[row][col] != 0:
            return [self.board[row][col]]
        used = set(self.board[row])
        used.update(self.board[r][col] for r in range(9))
        used.update(self.board[r][c] for r in range(row // 3 * 3, row // 3 * 3 + 3)
                    for c in range(col // 3 * 3, col // 3 * 3 + 3))
        return [value for value in range(1, 10) if value not in used]

    def set_value(self, row: int, col: int, value: int) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if not self._cell_ok(row, col):
            return ActionResult(False, "out_of_bounds")
        try:
            value = int(value)
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_value")
        if value < 0 or value > 9:
            return ActionResult(False, "invalid_value")
        if self.givens[row][col]:
            return ActionResult(False, "given_cell")
        if value == 0:
            self.board[row][col] = 0
            self.notes[row][col].clear()
            return ActionResult(True, outcome="playing", payload={"cleared": True})
        if value not in self.get_candidates(row, col):
            self.mistakes += 1
            return ActionResult(False, "violates_row_column_or_box", payload={"mistakes": self.mistakes})
        self.board[row][col] = value
        self.notes[row][col].discard(value)
        if self.is_solved():
            self.status = "won"
        return ActionResult(True, outcome=self.status, payload={"value": value})

    def apply_action(self, action: Any) -> ActionResult:
        """Apply a neutral ``(row, column, value)`` action."""
        if not isinstance(action, (list, tuple)) or len(action) != 3:
            return ActionResult(False, "invalid_action")
        return self.set_value(int(action[0]), int(action[1]), int(action[2]))

    # Friendly aliases used by keyboard/touch adapters.
    enter = set_value
    enter_number = set_value
    place = set_value

    def clear(self, row: int, col: int) -> ActionResult:
        return self.set_value(row, col, 0)

    def toggle_note(self, row: int, col: int, value: int) -> ActionResult:
        if self.paused or self.status != "playing":
            return ActionResult(False, "game_finished_or_paused")
        if not self._cell_ok(row, col) or self.givens[row][col]:
            return ActionResult(False, "invalid_note_cell")
        if value not in range(1, 10):
            return ActionResult(False, "invalid_value")
        if self.board[row][col] != 0:
            return ActionResult(False, "cell_filled")
        if value in self.notes[row][col]:
            self.notes[row][col].remove(value)
            enabled = False
        else:
            self.notes[row][col].add(value)
            enabled = True
        return ActionResult(True, outcome="playing", payload={"enabled": enabled})

    def hint(self, apply: bool = False) -> Optional[dict[str, Any]]:
        for row in range(9):
            for col in range(9):
                if self.board[row][col] == 0:
                    result = {"row": row, "col": col, "value": self.solution[row][col]}
                    if apply:
                        self.set_value(row, col, self.solution[row][col])
                    return result
        return None

    def has_unique_solution(self) -> bool:
        return self.unique_solution

    def solve(self) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        self.board = _copy_grid(self.solution)
        self.status = "won"
        return ActionResult(True, outcome="won", payload={"solved": True})

    def is_solved(self) -> bool:
        if not self.is_valid_grid(self.board, complete=True):
            return False
        # Generated/default puzzles are unique and can compare directly to
        # their solver answer.  A caller may intentionally load a non-unique
        # study puzzle; in that case any complete valid grid respecting the
        # givens is a legitimate completion.
        if self.unique_solution:
            return self.board == self.solution
        return all(not self.puzzle[r][c] or self.board[r][c] == self.puzzle[r][c]
                   for r in range(9) for c in range(9))

    def get_current_player(self) -> int:
        return 0

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[tuple[int, int, int]]:
        if self.status != "playing" or self.paused:
            return []
        return [(r, c, value) for r in range(9) for c in range(9)
                if self.board[r][c] == 0 for value in self.get_candidates(r, c)]

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "ruleset_id": self.ruleset_id,
            "board": _copy_grid(self.board),
            "givens": [[bool(v) for v in row] for row in self.givens],
            "status": self.status,
            "mistakes": self.mistakes,
            "unique_solution": self.unique_solution,
        }

    def get_result(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "solved": self.is_solved(),
            "mistakes": self.mistakes,
            "clues": sum(value != 0 for row in self.puzzle for value in row),
            "unique_solution": self.unique_solution,
        }

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "game_version": 1,
            "ruleset_id": self.ruleset_id,
            "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "seed": self.seed,
            "difficulty": self.difficulty,
            "puzzle": _copy_grid(self.puzzle),
            "solution": _copy_grid(self.solution),
            "board": _copy_grid(self.board),
            "givens": [[bool(v) for v in row] for row in self.givens],
            "notes": [[sorted(notes) for notes in row] for row in self.notes],
            "unique_solution": self.unique_solution,
            "status": self.status,
            "mistakes": self.mistakes,
            "paused": self.paused,
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        puzzle = _copy_grid(data["puzzle"])
        board = _copy_grid(data["board"])
        if not self.is_valid_grid(puzzle) or not self.is_valid_grid(board):
            raise ValueError("invalid Sudoku state")
        solution = _copy_grid(data.get("solution") or sudoku_solve(puzzle) or [])
        if not self.is_valid_grid(solution, complete=True) or not self.is_solved_grid(solution, puzzle):
            raise ValueError("invalid Sudoku solution")
        if any(puzzle[r][c] and board[r][c] != puzzle[r][c] for r in range(9) for c in range(9)):
            raise ValueError("Sudoku state changes a given clue")
        self.seed = int(data.get("seed", 0))
        self.difficulty = str(data.get("difficulty", "medium"))
        self.puzzle, self.solution, self.board = puzzle, solution, board
        self.givens = [[value != 0 for value in row] for row in puzzle]
        raw_notes = data.get("notes", [[[] for _ in range(9)] for _ in range(9)])
        if len(raw_notes) != 9 or any(len(row) != 9 for row in raw_notes):
            raise ValueError("invalid Sudoku notes")
        self.notes = [[set(int(value) for value in raw_notes[r][c]) for c in range(9)] for r in range(9)]
        if any(value < 1 or value > 9 for row in self.notes for cell in row for value in cell):
            raise ValueError("invalid Sudoku note value")
        self.unique_solution = bool(data.get("unique_solution", sudoku_count_solutions(puzzle, 2) == 1))
        self.status = str(data.get("status", "won" if self.is_solved() else "playing"))
        if self.status not in ("playing", "won"):
            raise ValueError("invalid Sudoku status")
        self.mistakes = int(data.get("mistakes", 0))
        self.paused = bool(data.get("paused", False))

    @staticmethod
    def is_solved_grid(solution: Sequence[Sequence[int]], puzzle: Sequence[Sequence[int]]) -> bool:
        return (SudokuGame.is_valid_grid(solution, complete=True)
                and all(not puzzle[r][c] or puzzle[r][c] == solution[r][c]
                        for r in range(9) for c in range(9)))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "SudokuGame":
        game = cls(puzzle=data.get("puzzle"), seed=int(data.get("seed", 0)),
                   difficulty=str(data.get("difficulty", "medium")))
        game.load_state(data)
        return game


# ---------------------------------------------------------------------------
# Matching Tiles / Shisen-Sho


class MatchingTilesGame:
    """Shisen-Sho matching with a two-turn orthogonal path rule.

    This is PlayAtlas's explicitly named digital adaptation: pairs connect
    through empty orthogonal cells with at most two turns and may use a
    one-cell outside border; this convention is not presented as every
    regional tile-matching rule.
    """

    # ``matching_tiles`` is the canonical content id.  The launch catalogue
    # also exports the compatibility id ``mahjong_connect`` below; it is an
    # alias of this same independent game and never increments the count.
    game_id = "matching_tiles"
    ruleset_id = "shisen-sho-three-lines-v1"
    ruleset_version = "1.0"
    digital_adaptation = "Orthogonal pair path of at most two turns with a one-cell outside border."
    save_schema_version = 1

    DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))

    def __init__(self, rows: int = 6, columns: int = 8,
                 tile_types: int = 12, seed: int = 0,
                 board: Optional[Sequence[Sequence[int]]] = None) -> None:
        if rows < 2 or columns < 2:
            raise ValueError("Matching Tiles board must be at least 2x2")
        if board is None and (rows * columns) % 2:
            raise ValueError("generated Matching Tiles board must have an even area")
        if tile_types < 1 or tile_types > rows * columns // 2:
            raise ValueError("invalid Matching Tiles tile type count")
        self.rows, self.columns = int(rows), int(columns)
        self.tile_types, self.seed = int(tile_types), int(seed)
        self._provided_board = _copy_grid(board) if board is not None else None
        self.restart()

    def initialize(self, context: Any = None) -> "MatchingTilesGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "MatchingTilesGame":
        if config:
            for name in ("rows", "columns", "tile_types", "seed"):
                if name in config:
                    setattr(self, name, int(config[name]))
            if "board" in config:
                self._provided_board = _copy_grid(config["board"])
        self.restart()
        return self

    def restart(self) -> None:
        self.paused = False
        self.status = "playing"
        self.shuffle_count = 0
        self.rng = random.Random(self.seed)
        if self._provided_board is not None:
            self.board = _copy_grid(self._provided_board)
            self._validate_board(self.board)
        else:
            values = [value for value in range(1, self.tile_types + 1)
                      for _ in range((self.rows * self.columns) // (2 * self.tile_types) * 2)]
            # If the area is not divisible by tile_types, distribute complete
            # pairs round-robin while preserving exact pair counts.
            while len(values) < self.rows * self.columns:
                value = (len(values) // 2) % self.tile_types + 1
                values.extend([value, value])
            values = values[: self.rows * self.columns]
            self.rng.shuffle(values)
            self.board = [values[r * self.columns:(r + 1) * self.columns]
                          for r in range(self.rows)]
            self._validate_board(self.board)

    def _validate_board(self, board: Sequence[Sequence[int]]) -> None:
        if len(board) != self.rows or any(len(row) != self.columns for row in board):
            raise ValueError("invalid Matching Tiles board dimensions")
        counts: dict[int, int] = {}
        for value in board:
            for tile in value:
                tile = int(tile)
                if tile < 0 or tile > self.tile_types:
                    raise ValueError("invalid Matching Tiles tile value")
                if tile:
                    counts[tile] = counts.get(tile, 0) + 1
        if any(count % 2 for count in counts.values()):
            raise ValueError("each remaining tile type must have an even count")

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def dispose(self) -> None:
        self.paused = True

    def is_finished(self) -> bool:
        return self.status == "won"

    def outcome(self) -> str:
        return self.status

    def _inside(self, row: int, col: int) -> bool:
        return 0 <= row < self.rows and 0 <= col < self.columns

    def _tile(self, cell: tuple[int, int]) -> int:
        return self.board[cell[0]][cell[1]]

    @staticmethod
    def _normalise_cell(cell: Any) -> tuple[int, int]:
        if not isinstance(cell, (tuple, list)) or len(cell) != 2:
            raise ValueError("tile coordinate must be (row, column)")
        return int(cell[0]), int(cell[1])

    def find_path(self, first: Any, second: Any) -> Optional[list[tuple[int, int]]]:
        """Return a shortest legal path, or ``None``.

        The path may contain the one-cell outside border.  Interior cells
        other than the two endpoints must be empty.  The returned polyline has
        at most two direction changes.
        """

        start, target = self._normalise_cell(first), self._normalise_cell(second)
        if (not self._inside(*start) or not self._inside(*target)
                or start == target or self._tile(start) == 0
                or self._tile(start) != self._tile(target)):
            return None
        # State stores row, col, direction index, and number of turns.  Start
        # by stepping in each direction from the first tile.
        min_coord, max_row, max_col = -1, self.rows, self.columns
        queue: deque[tuple[int, int, int, int]] = deque()
        parents: dict[tuple[int, int, int, int], Optional[tuple[int, int, int, int]]] = {}
        for direction, (dr, dc) in enumerate(self.DIRECTIONS):
            state = (start[0] + dr, start[1] + dc, direction, 0)
            r, c = state[:2]
            if r < min_coord or r > max_row or c < min_coord or c > max_col:
                continue
            if self._inside(r, c) and (r, c) != target and self.board[r][c] != 0:
                continue
            parents[state] = None
            queue.append(state)
        visited: dict[tuple[int, int, int], int] = {}
        found: Optional[tuple[int, int, int, int]] = None
        while queue:
            r, c, direction, turns = queue.popleft()
            key = (r, c, direction)
            if turns > visited.get(key, 99):
                continue
            visited[key] = turns
            if (r, c) == target:
                found = (r, c, direction, turns)
                break
            for new_direction, (dr, dc) in enumerate(self.DIRECTIONS):
                new_turns = turns + (new_direction != direction)
                if new_turns > 2:
                    continue
                nr, nc = r + dr, c + dc
                if nr < min_coord or nr > max_row or nc < min_coord or nc > max_col:
                    continue
                if self._inside(nr, nc) and (nr, nc) != target and self.board[nr][nc] != 0:
                    continue
                next_state = (nr, nc, new_direction, new_turns)
                next_key = (nr, nc, new_direction)
                if new_turns >= visited.get(next_key, 99):
                    continue
                if next_state not in parents:
                    parents[next_state] = (r, c, direction, turns)
                    queue.append(next_state)
        if found is None:
            return None
        # Reconstruct with the origin prepended.
        path: list[tuple[int, int]] = []
        state: Optional[tuple[int, int, int, int]] = found
        while state is not None:
            path.append((state[0], state[1]))
            state = parents.get(state)
        path.reverse()
        return [start, *path]

    def can_connect(self, first: Any, second: Any) -> bool:
        return self.find_path(first, second) is not None

    def match(self, first: Any, second: Any) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        start, target = self._normalise_cell(first), self._normalise_cell(second)
        path = self.find_path(start, target)
        if path is None:
            return ActionResult(False, "no_legal_path")
        self.board[start[0]][start[1]] = 0
        self.board[target[0]][target[1]] = 0
        if not any(tile for row in self.board for tile in row):
            self.status = "won"
        return ActionResult(True, outcome=self.status,
                            payload={"first": start, "second": target, "path": path})

    connect = match
    remove_pair = match

    def apply_action(self, action: Any, second: Any = None) -> ActionResult:
        """Apply a neutral pair action without exposing a UI-specific API."""
        if second is None and isinstance(action, (tuple, list)) and len(action) == 2:
            action, second = action[0], action[1]
        if second is None:
            return ActionResult(False, "invalid_action")
        return self.match(action, second)

    def find_all_moves(self) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        by_value: dict[int, list[tuple[int, int]]] = {}
        for r in range(self.rows):
            for c in range(self.columns):
                value = self.board[r][c]
                if value:
                    by_value.setdefault(value, []).append((r, c))
        moves: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for cells in by_value.values():
            for i, first in enumerate(cells):
                for second in cells[i + 1:]:
                    if self.can_connect(first, second):
                        moves.append((first, second))
        return moves

    def has_moves(self) -> bool:
        return bool(self.find_all_moves())

    def shuffle(self, ensure_move: bool = False, max_attempts: int = 100) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        cells = [(r, c) for r in range(self.rows) for c in range(self.columns)
                 if self.board[r][c] != 0]
        values = [self.board[r][c] for r, c in cells]
        if not values:
            return ActionResult(False, "board_empty")
        before = _copy_grid(self.board)
        before_shuffle_count = self.shuffle_count
        attempts = max(1, int(max_attempts))
        for _ in range(attempts):
            self.rng.shuffle(values)
            for cell, value in zip(cells, values):
                self.board[cell[0]][cell[1]] = value
            self.shuffle_count += 1
            if not ensure_move or self.has_moves():
                return ActionResult(True, outcome=self.status,
                                    payload={"shuffle_count": self.shuffle_count})
        self.board = before
        self.shuffle_count = before_shuffle_count
        return ActionResult(False, "no_move_after_shuffle")

    def reshuffle_if_stuck(self, max_attempts: int = 100) -> ActionResult:
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if self.has_moves():
            return ActionResult(False, "moves_available")
        return self.shuffle(ensure_move=True, max_attempts=max_attempts)

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        if self.status != "playing" or self.paused:
            return []
        return self.find_all_moves()

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {"game_id": self.game_id, "ruleset_id": self.ruleset_id,
                "rows": self.rows, "columns": self.columns,
                "board": _copy_grid(self.board), "status": self.status,
                "remaining_tiles": sum(tile != 0 for row in self.board for tile in row)}

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status,
                "remaining_tiles": sum(tile != 0 for row in self.board for tile in row),
                "shuffles": self.shuffle_count}

    def save_state(self) -> dict[str, Any]:
        return {"game_id": self.game_id, "game_version": 1,
                "ruleset_id": self.ruleset_id, "ruleset_version": 1,
                "save_schema_version": self.save_schema_version,
                "rows": self.rows, "columns": self.columns,
                "tile_types": self.tile_types, "seed": self.seed,
                "board": _copy_grid(self.board), "status": self.status,
                "shuffle_count": self.shuffle_count, "paused": self.paused,
                "rng_state": _jsonable_tuple(self.rng.getstate())}

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        self.rows, self.columns = int(data["rows"]), int(data["columns"])
        self.tile_types, self.seed = int(data["tile_types"]), int(data.get("seed", 0))
        if (self.rows < 2 or self.columns < 2 or self.tile_types < 1
                or self.tile_types > self.rows * self.columns // 2):
            raise ValueError("invalid Matching Tiles dimensions or tile types")
        self.board = _copy_grid(data["board"])
        self._validate_board(self.board)
        self.status = str(data.get("status", "playing"))
        if self.status not in ("playing", "won"):
            raise ValueError("invalid Matching Tiles status")
        self.shuffle_count = int(data.get("shuffle_count", 0))
        self.paused = bool(data.get("paused", False))
        self.rng = random.Random(self.seed)
        if data.get("rng_state") is not None:
            try:
                self.rng.setstate(_tuple_state(data["rng_state"]))
            except (TypeError, ValueError):
                raise ValueError("invalid Matching Tiles RNG state")

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "MatchingTilesGame":
        game = cls(int(data.get("rows", 6)), int(data.get("columns", 8)),
                   int(data.get("tile_types", 12)), int(data.get("seed", 0)),
                   board=data.get("board"))
        game.load_state(data)
        return game


ShisenShoGame = MatchingTilesGame


class MahjongConnectGame(MatchingTilesGame):
    """Compatibility export for the launch catalogue's historical id.

    ``matching_tiles`` is the canonical content id used by the full content
    manifest; early launch-catalogue snapshots called the same independent
    game ``mahjong_connect``.  This subclass changes only the identifier, not
    the rules, and therefore does not create a second game or inflate counts.
    """

    game_id = "mahjong_connect"


# ---------------------------------------------------------------------------
# Dots and Boxes


class DotsAndBoxesGame:
    """Two-player edge-drawing game with complete box scoring.

    ``dots-and-boxes-standard-v1`` is the explicitly scoped PlayAtlas digital
    adaptation of the common edge-drawing rules: a completed square scores
    and grants another turn, with no claim that one regional history is the
    sole original rules source.
    """

    game_id = "dots_and_boxes"
    ruleset_id = "dots-and-boxes-standard-v1"
    ruleset_version = "1.0"
    digital_adaptation = "Completing a box scores it and grants the same player another turn."
    save_schema_version = 1

    def __init__(self, width: int = 2, height: int = 2,
                 *, dots_rows: Optional[int] = None,
                 dots_columns: Optional[int] = None,
                 rows: Optional[int] = None,
                 columns: Optional[int] = None) -> None:
        # Public width/height denote boxes.  ``dots_rows``/``dots_columns``
        # are explicit escape hatches for callers that think in dots.
        if rows is not None:
            dots_rows = rows
        if columns is not None:
            dots_columns = columns
        if dots_rows is not None:
            height = int(dots_rows) - 1
        if dots_columns is not None:
            width = int(dots_columns) - 1
        if width < 1 or height < 1:
            raise ValueError("Dots and Boxes requires at least one box")
        self.width, self.height = int(width), int(height)
        self.dot_rows, self.dot_columns = self.height + 1, self.width + 1
        self.restart()

    def initialize(self, context: Any = None) -> "DotsAndBoxesGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "DotsAndBoxesGame":
        if config:
            if "width" in config:
                self.width = int(config["width"])
            if "height" in config:
                self.height = int(config["height"])
            if "dots_rows" in config:
                self.height = int(config["dots_rows"]) - 1
            if "dots_columns" in config:
                self.width = int(config["dots_columns"]) - 1
            if self.width < 1 or self.height < 1:
                raise ValueError("invalid Dots and Boxes dimensions")
            self.dot_rows, self.dot_columns = self.height + 1, self.width + 1
        self.restart()
        return self

    def restart(self) -> None:
        self.edges: set[tuple[str, int, int]] = set()
        self.boxes: list[list[int]] = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.scores = [0, 0]
        self.current_player = 0
        self.status = "playing"
        self.paused = False
        self.move_count = 0

    @property
    def board(self) -> list[list[int]]:
        """Alias used by generic board renderers; owners are 0/1/2."""

        return self.boxes

    @board.setter
    def board(self, value: Sequence[Sequence[int]]) -> None:
        boxes = _copy_grid(value)
        if len(boxes) != self.height or any(len(row) != self.width for row in boxes):
            raise ValueError("invalid Dots and Boxes board dimensions")
        if any(owner not in (0, 1, 2) for row in boxes for owner in row):
            raise ValueError("invalid Dots and Boxes board owner")
        self.boxes = boxes

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def dispose(self) -> None:
        self.paused = True

    def is_finished(self) -> bool:
        return self.status == "finished"

    def _valid_edge(self, edge: tuple[str, int, int]) -> bool:
        orientation, row, col = edge
        if orientation == "h":
            return 0 <= row <= self.height and 0 <= col < self.width
        return orientation == "v" and 0 <= row < self.height and 0 <= col <= self.width

    @staticmethod
    def _normalise_orientation(value: Any) -> str:
        value = str(value).lower()
        if value in ("h", "horizontal"):
            return "h"
        if value in ("v", "vertical"):
            return "v"
        raise ValueError("edge orientation must be h or v")

    def _normalise_edge(self, action: Any) -> tuple[str, int, int]:
        if isinstance(action, dict):
            orientation = self._normalise_orientation(action.get("orientation", action.get("direction")))
            return orientation, int(action["row"]), int(action["col"])
        if isinstance(action, (tuple, list)) and len(action) == 3:
            if isinstance(action[0], str):
                return self._normalise_orientation(action[0]), int(action[1]), int(action[2])
            if isinstance(action[2], str):
                return self._normalise_orientation(action[2]), int(action[0]), int(action[1])
        # Endpoint form: ((row, col), (row, col)).
        if isinstance(action, (tuple, list)) and len(action) == 2:
            first, second = action
            if all(isinstance(point, (tuple, list)) and len(point) == 2 for point in (first, second)):
                r1, c1 = int(first[0]), int(first[1])
                r2, c2 = int(second[0]), int(second[1])
                if r1 == r2 and abs(c1 - c2) == 1:
                    return "h", r1, min(c1, c2)
                if c1 == c2 and abs(r1 - r2) == 1:
                    return "v", min(r1, r2), c1
        raise ValueError("edge must be (h|v,row,col) or two adjacent endpoints")

    def _boxes_for_edge(self, edge: tuple[str, int, int]) -> list[tuple[int, int]]:
        orientation, row, col = edge
        result: list[tuple[int, int]] = []
        if orientation == "h":
            if row > 0:
                result.append((row - 1, col))
            if row < self.height:
                result.append((row, col))
        else:
            if col > 0:
                result.append((row, col - 1))
            if col < self.width:
                result.append((row, col))
        return result

    def _box_edges(self, row: int, col: int) -> tuple[tuple[str, int, int], ...]:
        return (("h", row, col), ("h", row + 1, col),
                ("v", row, col), ("v", row, col + 1))

    def _box_complete(self, row: int, col: int) -> bool:
        return all(edge in self.edges for edge in self._box_edges(row, col))

    def apply_action(self, action: Any) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.outcome())
        try:
            edge = self._normalise_edge(action)
        except (TypeError, ValueError, KeyError):
            return ActionResult(False, "invalid_edge")
        if not self._valid_edge(edge):
            return ActionResult(False, "edge_out_of_bounds")
        if edge in self.edges:
            return ActionResult(False, "edge_already_drawn")
        self.edges.add(edge)
        self.move_count += 1
        completed: list[tuple[int, int]] = []
        for row, col in self._boxes_for_edge(edge):
            if self.boxes[row][col] == 0 and self._box_complete(row, col):
                self.boxes[row][col] = self.current_player + 1
                self.scores[self.current_player] += 1
                completed.append((row, col))
        if len(self.edges) == self.total_edges:
            self.status = "finished"
        elif not completed:
            self.current_player = 1 - self.current_player
        return ActionResult(True, outcome=self.outcome(), payload={
            "edge": edge, "completed": completed,
            "next_player": self.current_player,
        })

    draw_edge = apply_action

    def get_current_player(self) -> Optional[int]:
        return None if self.status == "finished" else self.current_player

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[tuple[str, int, int]]:
        if self.paused or self.status != "playing":
            return []
        if player_id is not None and int(player_id) != self.current_player:
            return []
        return [edge for edge in self.all_edges() if edge not in self.edges]

    def all_edges(self) -> list[tuple[str, int, int]]:
        horizontal = [("h", row, col) for row in range(self.height + 1) for col in range(self.width)]
        vertical = [("v", row, col) for row in range(self.height) for col in range(self.width + 1)]
        return horizontal + vertical

    @property
    def total_edges(self) -> int:
        return (self.height + 1) * self.width + self.height * (self.width + 1)

    def outcome(self) -> str:
        if self.status != "finished":
            return "playing"
        if self.scores[0] == self.scores[1]:
            return "draw"
        return "player_0_win" if self.scores[0] > self.scores[1] else "player_1_win"

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {"game_id": self.game_id, "ruleset_id": self.ruleset_id,
                "width": self.width, "height": self.height,
                "edges": [list(edge) for edge in sorted(self.edges)],
                "boxes": [row[:] for row in self.boxes],
                "scores": list(self.scores), "current_player": self.get_current_player(),
                "status": self.status}

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status, "outcome": self.outcome(),
                "scores": list(self.scores), "moves": self.move_count}

    def save_state(self) -> dict[str, Any]:
        return {"game_id": self.game_id, "game_version": 1,
                "ruleset_id": self.ruleset_id, "ruleset_version": 1,
                "save_schema_version": self.save_schema_version,
                "width": self.width, "height": self.height,
                "edges": [list(edge) for edge in sorted(self.edges)],
                "boxes": [row[:] for row in self.boxes],
                "scores": list(self.scores), "current_player": self.current_player,
                "status": self.status, "paused": self.paused,
                "move_count": self.move_count}

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        self.width, self.height = int(data["width"]), int(data["height"])
        if self.width < 1 or self.height < 1:
            raise ValueError("invalid Dots and Boxes dimensions")
        self.dot_rows, self.dot_columns = self.height + 1, self.width + 1
        raw_edges = data.get("edges", [])
        self.edges = set()
        for raw in raw_edges:
            edge = self._normalise_edge(raw)
            if not self._valid_edge(edge):
                raise ValueError("invalid Dots and Boxes edge")
            self.edges.add(edge)
        if len(self.edges) != len(raw_edges):
            raise ValueError("duplicate Dots and Boxes edge")
        self.boxes = [[int(value) for value in row] for row in data.get("boxes", [])]
        if len(self.boxes) != self.height or any(len(row) != self.width for row in self.boxes):
            raise ValueError("invalid Dots and Boxes boxes")
        if any(value not in (0, 1, 2) for row in self.boxes for value in row):
            raise ValueError("invalid Dots and Boxes owner")
        # Owners and scores are derived from the edge set in a live match.
        # Reject tampered/incompatible saves instead of silently presenting a
        # state that could never have arisen through legal actions.
        derived_complete = {
            (row, col)
            for row in range(self.height)
            for col in range(self.width)
            if self._box_complete(row, col)
        }
        for row in range(self.height):
            for col in range(self.width):
                owner = self.boxes[row][col]
                if (row, col) in derived_complete and owner == 0:
                    raise ValueError("completed Dots and Boxes square has no owner")
                if (row, col) not in derived_complete and owner != 0:
                    raise ValueError("incomplete Dots and Boxes square has an owner")
        self.scores = [int(value) for value in data.get("scores", [0, 0])]
        if len(self.scores) != 2 or any(value < 0 for value in self.scores):
            raise ValueError("invalid Dots and Boxes scores")
        derived_scores = [sum(owner == player + 1 for row in self.boxes for owner in row)
                          for player in range(2)]
        if self.scores != derived_scores:
            raise ValueError("Dots and Boxes scores do not match box owners")
        self.current_player = int(data.get("current_player", 0))
        if self.current_player not in (0, 1):
            raise ValueError("invalid Dots and Boxes player")
        self.status = str(data.get("status", "playing"))
        if self.status not in ("playing", "finished"):
            raise ValueError("invalid Dots and Boxes status")
        if self.status == "playing" and len(self.edges) == self.total_edges:
            raise ValueError("finished edge set marked as playing")
        if self.status == "finished" and len(self.edges) != self.total_edges:
            raise ValueError("incomplete edge set marked as finished")
        self.paused = bool(data.get("paused", False))
        self.move_count = int(data.get("move_count", len(self.edges)))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "DotsAndBoxesGame":
        game = cls(int(data.get("width", 2)), int(data.get("height", 2)))
        game.load_state(data)
        return game


__all__ = [
    "BreakoutGame", "SudokuGame", "sudoku_count_solutions", "sudoku_solve",
    "count_solutions", "solve_sudoku",
    "MatchingTilesGame", "ShisenShoGame", "MahjongConnectGame",
    "DotsAndBoxesGame",
]
