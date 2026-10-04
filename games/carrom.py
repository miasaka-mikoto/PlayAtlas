"""Small deterministic carrom board rule/physics engine.

Ruleset ``carrom.digital_standard.v1`` is a clearly labelled digital
adaptation of common carrom-board play: a square 1x1 board, four corner
pockets, fixed white/black targets (player 0/1), a queen worth three points
only when covered by an own coin in the same strike, striker fouls, elastic
coin collisions and friction.  A player retains the turn after legally
pocketing an own coin; otherwise the turn changes when all pieces stop.

It is deliberately a rules engine rather than a visual physics demo.  The
front end supplies aiming UI and calls ``place_striker``/``strike``;
``fixed_update`` advances deterministic physics and resolves the turn.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any, Optional

from .common import ActionResult


@dataclass
class Piece:
    piece_id: str
    kind: str  # coin, queen, striker
    color: Optional[str]
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    pocketed: bool = False

    @property
    def radius(self) -> float:
        return 0.028 if self.kind == "striker" else 0.018

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Piece":
        return cls(str(data["piece_id"]), str(data["kind"]), data.get("color"),
                   float(data["x"]), float(data["y"]), float(data.get("vx", 0.0)),
                   float(data.get("vy", 0.0)), bool(data.get("pocketed", False)))


@dataclass(frozen=True)
class CarromResult:
    status: str
    scores: tuple[int, int]
    current_player: Optional[int]
    pocketed: tuple[str, ...]


class CarromGame:
    game_id = "carrom"
    ruleset_id = "carrom.digital_standard.v1"
    save_schema_version = 1
    board_min = 0.0
    board_max = 1.0
    pocket_radius = 0.060
    friction = 0.82
    stop_speed = 0.012
    max_speed = 1.8

    def __init__(self) -> None:
        self.restart()

    def initialize(self, context: Any = None) -> "CarromGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "CarromGame":
        self.restart()
        return self

    def restart(self) -> None:
        self.pieces: list[Piece] = []
        # A compact, symmetric opening arrangement.  Geometry is normalized
        # so desktop and touch layouts can use the same rule state.
        centre = (0.5, 0.5)
        self.pieces.append(Piece("queen", "queen", None, *centre))
        radius = 0.060
        for i in range(9):
            angle = 2 * math.pi * i / 9
            self.pieces.append(Piece(f"w{i+1}", "coin", "white",
                                     centre[0] + radius * math.cos(angle),
                                     centre[1] + radius * math.sin(angle)))
        for i in range(9):
            angle = 2 * math.pi * (i + 0.5) / 9
            self.pieces.append(Piece(f"b{i+1}", "coin", "black",
                                     centre[0] + 2 * radius * math.cos(angle),
                                     centre[1] + 2 * radius * math.sin(angle)))
        self.striker = Piece("striker", "striker", None, 0.5, 0.12)
        self.current_player = 0
        self.scores = [0, 0]
        self.status = "playing"
        self.phase = "aiming"
        self.queen_covered = False
        self.pending_pocketed: list[str] = []
        self.pending_foul = False
        self.move_count = 0
        self.paused = False
        self.last_error = ""
        self._place_on_baseline()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def _place_on_baseline(self) -> None:
        self.striker.vx = self.striker.vy = 0.0
        self.striker.pocketed = False
        self.striker.x = 0.5
        self.striker.y = 0.12 if self.current_player == 0 else 0.88

    def _active_pieces(self) -> list[Piece]:
        return [p for p in self.pieces if not p.pocketed]

    def _find(self, piece_id: str) -> Optional[Piece]:
        if piece_id == "striker":
            return self.striker
        return next((p for p in self.pieces if p.piece_id == piece_id), None)

    def _baseline_y(self) -> float:
        return 0.12 if self.current_player == 0 else 0.88

    def place_striker(self, x: float) -> ActionResult:
        if self.phase != "aiming" or self.status != "playing":
            return ActionResult(False, "not_aiming")
        x = float(x)
        if not 0.06 <= x <= 0.94:
            return ActionResult(False, "baseline_out_of_bounds")
        self.striker.x, self.striker.y = x, self._baseline_y()
        if any(self._distance(self.striker, p) < self.striker.radius + p.radius
               for p in self._active_pieces()):
            return ActionResult(False, "baseline_occupied")
        return ActionResult(True, outcome="aiming", payload={"x": x, "y": self.striker.y})

    def strike(self, angle: float, power: float) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if self.phase != "aiming":
            return ActionResult(False, "pieces_moving")
        try:
            angle, power = float(angle), float(power)
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_strike")
        if not math.isfinite(angle) or not 0.0 < power <= 1.0:
            return ActionResult(False, "invalid_power")
        # Player 0 normally shoots upward and player 1 downward; any angle is
        # legal as long as the striker starts on its baseline.
        speed = self.max_speed * power
        self.striker.vx = math.cos(angle) * speed
        self.striker.vy = math.sin(angle) * speed
        self.phase = "moving"
        self.pending_pocketed = []
        self.pending_foul = False
        self.move_count += 1
        return ActionResult(True, outcome="moving", payload={"angle": angle, "power": power})

    @staticmethod
    def _distance(a: Piece, b: Piece) -> float:
        return math.hypot(a.x - b.x, a.y - b.y)

    def _pocket_if_needed(self, piece: Piece) -> None:
        if piece.pocketed:
            return
        for px, py in ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)):
            if math.hypot(piece.x - px, piece.y - py) <= self.pocket_radius:
                piece.pocketed = True
                piece.vx = piece.vy = 0.0
                self.pending_pocketed.append(piece.piece_id)
                if piece is self.striker:
                    self.pending_foul = True
                return

    def _bounce_walls(self, piece: Piece) -> None:
        r = piece.radius
        if piece.x < r:
            piece.x, piece.vx = r, abs(piece.vx)
        elif piece.x > 1 - r:
            piece.x, piece.vx = 1 - r, -abs(piece.vx)
        if piece.y < r:
            piece.y, piece.vy = r, abs(piece.vy)
        elif piece.y > 1 - r:
            piece.y, piece.vy = 1 - r, -abs(piece.vy)

    def _collide(self, a: Piece, b: Piece) -> None:
        if a.pocketed or b.pocketed:
            return
        dx, dy = b.x - a.x, b.y - a.y
        distance = math.hypot(dx, dy)
        minimum = a.radius + b.radius
        if distance == 0.0:
            dx, dy, distance = minimum, 0.0, minimum
        if distance >= minimum:
            return
        nx, ny = dx / distance, dy / distance
        overlap = minimum - distance
        a.x -= nx * overlap * 0.5
        a.y -= ny * overlap * 0.5
        b.x += nx * overlap * 0.5
        b.y += ny * overlap * 0.5
        rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
        if rel > 0:
            return
        # Equal-mass, slightly inelastic collision for stable tabletop play.
        impulse = -(1.0 + 0.92) * rel / 2.0
        a.vx -= impulse * nx
        a.vy -= impulse * ny
        b.vx += impulse * nx
        b.vy += impulse * ny

    def _all_stopped(self) -> bool:
        return all(p.pocketed or math.hypot(p.vx, p.vy) <= self.stop_speed
                   for p in [self.striker, *self.pieces])

    def _return_to_centre(self, piece: Piece) -> None:
        piece.pocketed = False
        piece.vx = piece.vy = 0.0
        # Find the first free point near the centre; deterministic and avoids
        # silently overlapping an existing piece.
        candidates = [(0.5, 0.5), (0.46, 0.5), (0.54, 0.5), (0.5, 0.46), (0.5, 0.54)]
        for x, y in candidates:
            if all(math.hypot(x - p.x, y - p.y) >= piece.radius + p.radius
                   for p in self._active_pieces() if p is not piece):
                piece.x, piece.y = x, y
                return
        piece.x, piece.y = 0.5, 0.5

    def _resolve_turn(self) -> ActionResult:
        player = self.current_player
        pocketed = list(self.pending_pocketed)
        own_color = "white" if player == 0 else "black"
        own = [pid for pid in pocketed if (self._find(pid) and self._find(pid).color == own_color)]
        opponent = [pid for pid in pocketed if (self._find(pid) and self._find(pid).color != own_color
                                                 and pid != "queen" and pid != "striker")]
        queen = self._find("queen")
        queen_pocketed = "queen" in pocketed
        # Opponent coins are returned rather than silently removed.  This
        # keeps the target-color rule explicit and conserves all pieces.
        for pid in opponent:
            piece = self._find(pid)
            if piece:
                self._return_to_centre(piece)
        if queen_pocketed:
            if own and queen:
                self.scores[player] += 3
                self.queen_covered = True
            elif queen:
                self._return_to_centre(queen)
                self.queen_covered = False
        if self.pending_foul:
            self._return_to_centre(self.striker)
            if self.scores[player] > 0:
                self.scores[player] -= 1
        self.scores[player] += len(own)
        retained = bool(own) and not self.pending_foul
        # A striker is always put back on its next baseline, even after a foul.
        self.current_player = player if retained else 1 - player
        self._place_on_baseline()
        self.pending_pocketed.clear()
        self.pending_foul = False
        self.phase = "aiming"
        active_regular = [p for p in self.pieces if p.kind == "coin" and not p.pocketed]
        if not active_regular:
            if self.scores[0] > self.scores[1]:
                self.status = "player_0_win"
            elif self.scores[1] > self.scores[0]:
                self.status = "player_1_win"
            else:
                self.status = "draw"
        return ActionResult(True, outcome=self.status,
                            payload={"pocketed": pocketed, "scores": list(self.scores),
                                     "next_player": self.current_player})

    def fixed_update(self, delta: float) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.phase != "moving":
            return ActionResult(False, "not_moving")
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_delta")
        if delta <= 0 or not math.isfinite(delta):
            return ActionResult(False, "invalid_delta")
        # Substeps reduce tunnelling for fast strikes while keeping runtime
        # bounded even if a frame stalls.
        steps = max(1, min(20, math.ceil(delta / 0.004)))
        dt = delta / steps
        for _ in range(steps):
            moving = [p for p in [self.striker, *self.pieces] if not p.pocketed]
            for piece in moving:
                piece.x += piece.vx * dt
                piece.y += piece.vy * dt
                self._bounce_walls(piece)
            for i, first in enumerate(moving):
                for second in moving[i + 1:]:
                    self._collide(first, second)
            for piece in moving:
                self._pocket_if_needed(piece)
            for piece in [self.striker, *self.pieces]:
                if not piece.pocketed:
                    piece.vx *= self.friction ** dt
                    piece.vy *= self.friction ** dt
        if self._all_stopped():
            for piece in [self.striker, *self.pieces]:
                if not piece.pocketed:
                    piece.vx = piece.vy = 0.0
            return self._resolve_turn()
        return ActionResult(True, outcome="moving", payload={"pocketed": list(self.pending_pocketed)})

    def get_snapshot(self) -> dict[str, Any]:
        return self.save_state()

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.load_state(snapshot)

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "ruleset_id": self.ruleset_id,
            "board": {"min": self.board_min, "max": self.board_max,
                       "pocket_radius": self.pocket_radius},
            "pieces": [p.to_dict() for p in self.pieces if not p.pocketed],
            "striker": self.striker.to_dict(), "phase": self.phase,
            "current_player": self.current_player if self.status == "playing" else None,
            "scores": list(self.scores), "status": self.status,
            "queen_covered": self.queen_covered,
        }

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[dict[str, Any]]:
        if self.status != "playing" or self.paused or self.phase != "aiming":
            return []
        return [{"type": "place_striker"}, {"type": "strike"}]

    def get_result(self) -> CarromResult:
        return CarromResult(self.status, tuple(self.scores),
                            self.current_player if self.status == "playing" else None,
                            tuple(self.pending_pocketed))

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "game_version": 1,
            "ruleset_id": self.ruleset_id, "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "pieces": [p.to_dict() for p in self.pieces],
            "striker": self.striker.to_dict(), "current_player": self.current_player,
            "scores": list(self.scores), "status": self.status, "phase": self.phase,
            "queen_covered": self.queen_covered,
            "pending_pocketed": list(self.pending_pocketed),
            "pending_foul": self.pending_foul, "move_count": self.move_count,
            "paused": self.paused,
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        self.pieces = [Piece.from_dict(p) for p in data["pieces"]]
        self.striker = Piece.from_dict(data["striker"])
        if self.striker.kind != "striker":
            raise ValueError("invalid striker")
        ids = [p.piece_id for p in self.pieces]
        if len(ids) != 19 or len(set(ids)) != 19 or "queen" not in ids:
            raise ValueError("carrom requires queen plus 18 coins")
        if any(p.kind not in ("coin", "queen") for p in self.pieces):
            raise ValueError("invalid carrom piece")
        self.current_player = int(data["current_player"])
        self.scores = [int(x) for x in data["scores"]]
        if self.current_player not in (0, 1) or len(self.scores) != 2:
            raise ValueError("invalid carrom players")
        self.status = str(data.get("status", "playing"))
        self.phase = str(data.get("phase", "aiming"))
        if self.status not in ("playing", "player_0_win", "player_1_win", "draw") or self.phase not in ("aiming", "moving"):
            raise ValueError("invalid carrom status")
        self.queen_covered = bool(data.get("queen_covered", False))
        self.pending_pocketed = [str(x) for x in data.get("pending_pocketed", [])]
        self.pending_foul = bool(data.get("pending_foul", False))
        self.move_count = int(data.get("move_count", 0))
        self.paused = bool(data.get("paused", False))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "CarromGame":
        game = cls()
        game.load_state(data)
        return game

    def dispose(self) -> None:
        self.paused = True

