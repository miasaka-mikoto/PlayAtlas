"""Headless deterministic Snake rules.

Ruleset ``snake.classic.v1`` uses a rectangular grid, wall collision, no
immediate 180-degree turns, one food item at a time, and a win when every
cell is occupied.  Input is sampled once per ``step``; a UI may call
``handle_input`` then ``fixed_update`` at its chosen tick rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from .common import ActionResult


class Direction(str, Enum):
    UP = "up"
    RIGHT = "right"
    DOWN = "down"
    LEFT = "left"

    @property
    def vector(self) -> tuple[int, int]:
        return {
            Direction.UP: (0, -1), Direction.RIGHT: (1, 0),
            Direction.DOWN: (0, 1), Direction.LEFT: (-1, 0),
        }[self]


@dataclass(frozen=True)
class SnakeResult:
    status: str  # playing, won, lost
    score: int
    length: int
    ticks: int


class SnakeGame:
    game_id = "snake"
    ruleset_id = "snake.classic.v1"
    save_schema_version = 1

    def __init__(self, width: int = 20, height: int = 14, seed: int = 0,
                 initial_length: int = 3) -> None:
        if width < 5 or height < 5:
            raise ValueError("Snake board must be at least 5x5")
        if initial_length < 2 or initial_length >= width:
            raise ValueError("invalid initial length")
        self.width, self.height, self.seed = int(width), int(height), int(seed)
        self.initial_length = int(initial_length)
        self.restart()

    def initialize(self, context: Any = None) -> "SnakeGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "SnakeGame":
        if config:
            for name in ("width", "height", "seed", "initial_length"):
                if name in config:
                    setattr(self, name, int(config[name]))
        self.restart()
        return self

    def restart(self) -> None:
        cx, cy = self.width // 2, self.height // 2
        self.snake: list[tuple[int, int]] = [(cx - i, cy) for i in range(self.initial_length)]
        self.direction = Direction.RIGHT
        self.pending_direction: Optional[Direction] = None
        self.rng_state = self.seed & 0xFFFFFFFF
        if self.rng_state == 0:
            self.rng_state = 0x6D2B79F5
        self.food: Optional[tuple[int, int]] = None
        self.status = "playing"
        self.score = 0
        self.ticks = 0
        self.paused = False
        self._spawn_food()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def _next_random(self) -> int:
        # A tiny deterministic xorshift PRNG; state is a single JSON integer.
        x = self.rng_state & 0xFFFFFFFF
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= (x >> 17)
        x ^= (x << 5) & 0xFFFFFFFF
        self.rng_state = x & 0xFFFFFFFF
        return self.rng_state

    def _spawn_food(self) -> None:
        free = [(x, y) for y in range(self.height) for x in range(self.width)
                if (x, y) not in self.snake]
        if not free:
            self.food = None
            self.status = "won"
            return
        self.food = free[self._next_random() % len(free)]

    def _coerce_direction(self, value: Direction | str) -> Direction:
        if isinstance(value, Direction):
            return value
        return Direction(str(value).lower())

    @staticmethod
    def _opposite(a: Direction, b: Direction) -> bool:
        return (a.vector[0] + b.vector[0] == 0 and a.vector[1] + b.vector[1] == 0)

    def handle_input(self, input_frame: Direction | str | dict[str, Any]) -> ActionResult:
        if isinstance(input_frame, dict):
            input_frame = input_frame.get("direction")
        try:
            direction = self._coerce_direction(input_frame)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return ActionResult(False, "invalid_direction")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if self._opposite(direction, self.direction):
            return ActionResult(False, "reverse_forbidden")
        self.pending_direction = direction
        return ActionResult(True, outcome="queued")

    def step(self, direction: Optional[Direction | str] = None) -> ActionResult:
        if direction is not None:
            queued = self.handle_input(direction)
            if not queued:
                # A reverse input is ignored by classic Snake; the tick still
                # proceeds with the current heading.
                if queued.reason != "reverse_forbidden":
                    return queued
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if self.pending_direction is not None and not self._opposite(self.pending_direction, self.direction):
            self.direction = self.pending_direction
        self.pending_direction = None
        dx, dy = self.direction.vector
        head = self.snake[0]
        new_head = (head[0] + dx, head[1] + dy)
        growing = new_head == self.food
        body_to_check = self.snake if growing else self.snake[:-1]
        if not (0 <= new_head[0] < self.width and 0 <= new_head[1] < self.height):
            self.status = "lost"
            self.ticks += 1
            return ActionResult(True, outcome="lost", payload={"cause": "wall"})
        if new_head in body_to_check:
            self.status = "lost"
            self.ticks += 1
            return ActionResult(True, outcome="lost", payload={"cause": "self"})
        self.snake.insert(0, new_head)
        if growing:
            self.score += 1
            self._spawn_food()
        else:
            self.snake.pop()
        self.ticks += 1
        return ActionResult(True, outcome=self.status, payload={"head": new_head, "score": self.score})

    def fixed_update(self, delta: float) -> ActionResult:
        # The rule engine intentionally advances one cell per call.  A front
        # end can accumulate ``delta`` and call this at the desired tick.
        return self.step()

    def get_snapshot(self) -> dict[str, Any]:
        return self.save_state()

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.load_state(snapshot)

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "ruleset_id": self.ruleset_id,
            "width": self.width, "height": self.height,
            "snake": [list(p) for p in self.snake],
            "food": list(self.food) if self.food else None,
            "direction": self.direction.value, "status": self.status,
            "score": self.score, "ticks": self.ticks,
        }

    def get_result(self) -> SnakeResult:
        return SnakeResult(self.status, self.score, len(self.snake), self.ticks)

    def is_finished(self) -> bool:
        return self.status != "playing"

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "game_version": 1,
            "ruleset_id": self.ruleset_id, "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "width": self.width, "height": self.height, "seed": self.seed,
            "initial_length": self.initial_length,
            "snake": [list(p) for p in self.snake],
            "direction": self.direction.value,
            "pending_direction": self.pending_direction.value if self.pending_direction else None,
            "food": list(self.food) if self.food else None,
            "rng_state": self.rng_state, "status": self.status,
            "score": self.score, "ticks": self.ticks, "paused": self.paused,
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        self.width, self.height = int(data["width"]), int(data["height"])
        self.seed = int(data.get("seed", 0))
        self.initial_length = int(data.get("initial_length", 3))
        self.snake = [tuple(map(int, p)) for p in data["snake"]]
        if not self.snake or len(set(self.snake)) != len(self.snake):
            raise ValueError("invalid snake body")
        if any(not (0 <= x < self.width and 0 <= y < self.height) for x, y in self.snake):
            raise ValueError("snake outside board")
        self.direction = self._coerce_direction(data["direction"])
        pending = data.get("pending_direction")
        self.pending_direction = self._coerce_direction(pending) if pending else None
        f = data.get("food")
        self.food = tuple(map(int, f)) if f is not None else None
        if self.food is not None and not (0 <= self.food[0] < self.width and 0 <= self.food[1] < self.height):
            raise ValueError("food outside board")
        self.rng_state = int(data.get("rng_state", self.seed)) & 0xFFFFFFFF
        self.status = str(data.get("status", "playing"))
        if self.status not in ("playing", "won", "lost"):
            raise ValueError("invalid Snake status")
        self.score, self.ticks = int(data.get("score", 0)), int(data.get("ticks", 0))
        self.paused = bool(data.get("paused", False))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "SnakeGame":
        game = cls(int(data["width"]), int(data["height"]), int(data.get("seed", 0)), int(data.get("initial_length", 3)))
        game.load_state(data)
        return game

    def dispose(self) -> None:
        self.paused = True

