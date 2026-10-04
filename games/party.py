"""Party and LAN-ready PlayAtlas rule engines.

The party pack is intentionally separate from the launch-36 catalogue until
each game has a real Godot presentation and manual multi-device acceptance.
These engines are nevertheless complete, deterministic state machines that
can be driven by a local host, a future Godot presentation, or headless QA.

The two probability machines in this module are *free-play arcade toys*:
they award score points, never accept money, never expose cash-out, and never
pretend to be a gambling product.  This follows PlayAtlas' offline/no-betting
product boundary while still giving a party a light chance-based activity.
"""

from __future__ import annotations

from collections import Counter
import random
from typing import Any, Optional

from .common import ActionResult


def _jsonable(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_tuple(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuple(item) for key, item in value.items()}
    return value


class PartyGameBase:
    """Shared lifecycle and serialisation helpers for party engines."""

    game_id = "party"
    ruleset_id = "digital_adaptation.v1"
    ruleset_version = "1.0"
    save_schema_version = 1
    min_players = 1
    max_players = 4
    supports_lan = True

    def initialize(self, context: Any = None) -> "PartyGameBase":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "PartyGameBase":
        self.restart()
        return self

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def dispose(self) -> None:
        self.paused = True

    def is_finished(self) -> bool:
        return getattr(self, "status", "playing") in {"finished", "won", "lost"}

    def outcome(self) -> str:
        return str(getattr(self, "status", "playing"))

    def get_result(self) -> dict[str, Any]:
        return {"status": self.outcome()}

    def _base_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "ruleset_id": self.ruleset_id,
            "ruleset_version": self.ruleset_version,
            "save_schema_version": self.save_schema_version,
            "paused": bool(getattr(self, "paused", False)),
        }


# ---------------------------------------------------------------------------
# Tank Battle


class TankBattleGame(PartyGameBase):
    """Deterministic 2–4 player grid tank battle.

    This is an original PlayAtlas ruleset, not a recreation of a commercial
    tank game.  A command moves or fires one cell/tick; bullets stop at walls,
    score one point on a hit, and a tank respawns at its spawn after a hit.
    First to five points wins.  The rules are intentionally small enough for
    an authoritative LAN host to validate in one frame.
    """

    game_id = "tank_battle"
    ruleset_id = "tank_battle.playatlas.v1"
    ruleset_version = "1.0"
    min_players, max_players = 2, 4
    width, height = 24, 14

    DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

    def __init__(self, players: int = 2, seed: int = 0, target_score: int = 5) -> None:
        if not self.min_players <= int(players) <= self.max_players:
            raise ValueError("Tank Battle supports two to four players")
        self.player_count = int(players)
        self.seed = int(seed)
        self.target_score = int(target_score)
        self._rng = random.Random(self.seed)
        self.restart()

    @property
    def walls(self) -> set[tuple[int, int]]:
        # Symmetric, data-like original arena.  Spawns are kept open.
        cells = set()
        for x in range(3, self.width - 3, 4):
            for y in (4, 9):
                cells.add((x, y))
        for y in range(2, self.height - 2, 4):
            for x in (7, 16):
                cells.add((x, y))
        return cells - set(self.spawns)

    @property
    def spawns(self) -> list[tuple[int, int]]:
        return [(1, 1), (self.width - 2, self.height - 2),
                (self.width - 2, 1), (1, self.height - 2)][:self.player_count]

    def restart(self) -> None:
        self.paused = False
        self.status = "playing"
        self.tick = 0
        self.scores = [0 for _ in range(self.player_count)]
        self.positions = {pid: list(self.spawns[pid]) for pid in range(self.player_count)}
        self.directions = {pid: "up" for pid in range(self.player_count)}
        self.bullets: list[dict[str, Any]] = []
        self.last_events: list[dict[str, Any]] = []

    def _inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def _occupied(self, x: int, y: int, except_player: Optional[int] = None) -> bool:
        return any(pid != except_player and tuple(pos) == (x, y)
                   for pid, pos in self.positions.items())

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[dict[str, Any]]:
        pid = 0 if player_id is None else int(player_id)
        if pid not in self.positions or self.is_finished() or self.paused:
            return []
        actions = [{"type": "fire"}]
        for direction in self.DIRECTIONS:
            actions.append({"type": "move", "direction": direction})
        return actions

    def apply_action(self, action: Any, player_id: Optional[int] = None) -> ActionResult:
        if self.paused or self.is_finished():
            return ActionResult(False, "game_finished_or_paused")
        payload = action if isinstance(action, dict) else {"type": action}
        pid = int(payload.get("player_id", player_id if player_id is not None else 0))
        if pid not in self.positions:
            return ActionResult(False, "unknown_player")
        kind = str(payload.get("type", payload.get("action", ""))).lower()
        if kind == "move":
            direction = str(payload.get("direction", "")).lower()
            if direction not in self.DIRECTIONS:
                return ActionResult(False, "invalid_direction")
            dx, dy = self.DIRECTIONS[direction]
            nx, ny = self.positions[pid][0] + dx, self.positions[pid][1] + dy
            self.directions[pid] = direction
            if not self._inside(nx, ny) or (nx, ny) in self.walls or self._occupied(nx, ny, pid):
                return ActionResult(False, "blocked")
            self.positions[pid] = [nx, ny]
            return ActionResult(True, outcome=self.status, payload={"position": [nx, ny]})
        if kind == "fire":
            dx, dy = self.DIRECTIONS[self.directions[pid]]
            self.bullets.append({"owner": pid, "x": self.positions[pid][0] + dx,
                                 "y": self.positions[pid][1] + dy,
                                 "dx": dx, "dy": dy})
            return ActionResult(True, outcome=self.status)
        return ActionResult(False, "unknown_action")

    def fixed_update(self, delta: float = 1 / 30) -> ActionResult:
        if self.paused or self.is_finished():
            return ActionResult(False, "game_finished_or_paused")
        self.tick += 1
        self.last_events = []
        next_bullets: list[dict[str, Any]] = []
        for bullet in self.bullets:
            x, y = int(bullet["x"]), int(bullet["y"])
            if not self._inside(x, y) or (x, y) in self.walls:
                continue
            hit = next((pid for pid, pos in self.positions.items()
                        if pid != bullet["owner"] and tuple(pos) == (x, y)), None)
            if hit is not None:
                owner = int(bullet["owner"])
                self.scores[owner] += 1
                self.last_events.append({"type": "hit", "owner": owner, "target": hit})
                self.positions[hit] = list(self.spawns[hit])
                if self.scores[owner] >= self.target_score:
                    self.status = "finished"
                    self.winner = owner
                continue
            next_bullets.append({**bullet, "x": x + int(bullet["dx"]), "y": y + int(bullet["dy"])})
        self.bullets = next_bullets
        return ActionResult(True, outcome=self.status, payload={"events": self.last_events[:]})

    def handle_input(self, input_frame: Any, player_id: int = 0) -> ActionResult:
        return self.apply_action(input_frame, player_id=player_id)

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "tick": self.tick, "status": self.status,
            "positions": {str(pid): list(pos) for pid, pos in self.positions.items()},
            "directions": dict(self.directions), "bullets": [dict(b) for b in self.bullets],
            "scores": self.scores[:], "walls": [list(cell) for cell in sorted(self.walls)],
            "player_id": player_id,
        }

    def get_snapshot(self) -> dict[str, Any]:
        return self.get_observation()

    def restore_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.tick = int(snapshot["tick"])
        self.status = str(snapshot["status"])
        self.positions = {int(pid): [int(pos[0]), int(pos[1])] for pid, pos in snapshot["positions"].items()}
        self.directions = {int(pid): str(direction) for pid, direction in snapshot["directions"].items()}
        self.bullets = [dict(item) for item in snapshot.get("bullets", [])]
        self.scores = [int(x) for x in snapshot.get("scores", [])]

    def save_state(self) -> dict[str, Any]:
        return {**self._base_state(), "seed": self.seed, "player_count": self.player_count,
                "target_score": self.target_score, "snapshot": self.get_snapshot(),
                "winner": getattr(self, "winner", None)}

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("wrong Tank Battle save")
        self.restore_snapshot(data["snapshot"])
        self.winner = data.get("winner")
        self.paused = bool(data.get("paused", False))

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status, "winner": getattr(self, "winner", None),
                "scores": self.scores[:], "ticks": self.tick}


# ---------------------------------------------------------------------------
# UNO


UnoCard = tuple[str, str]


class UnoGame(PartyGameBase):
    """UNO-inspired standard 108-card ruleset with explicit house choices.

    Default rules: seven-card deal, draw one and pass, no draw stacking, a
    Wild Draw Four is legal only when the player has no card of the current
    colour, and a Wild card must declare a colour.  A player wins as soon as
    their hand is empty; the optional spoken UNO call is presentation-only.
    """

    game_id = "uno"
    ruleset_id = "uno.standard.digital.v1"
    ruleset_version = "1.0"
    min_players, max_players = 2, 4
    COLORS = ("red", "yellow", "green", "blue")
    VALUES = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
              "skip", "reverse", "draw2", "wild", "wild_draw4")

    def __init__(self, players: int = 4, seed: int = 0) -> None:
        if not self.min_players <= int(players) <= self.max_players:
            raise ValueError("UNO supports two to four players")
        self.player_count, self.seed = int(players), int(seed)
        self.rng = random.Random(self.seed)
        self.restart()

    @classmethod
    def build_deck(cls) -> list[UnoCard]:
        deck: list[UnoCard] = []
        for color in cls.COLORS:
            deck.append((color, "0"))
            for value in (str(n) for n in range(1, 10)):
                deck.extend([(color, value), (color, value)])
            for value in ("skip", "reverse", "draw2"):
                deck.extend([(color, value), (color, value)])
        deck.extend([("wild", "wild")] * 4)
        deck.extend([("wild", "wild_draw4")] * 4)
        assert len(deck) == 108
        return deck

    def restart(self) -> None:
        self.paused = False
        self.status = "playing"
        self.winner: Optional[int] = None
        self.rng = random.Random(self.seed)
        self.draw_pile = self.build_deck()
        self.rng.shuffle(self.draw_pile)
        self.hands = [[] for _ in range(self.player_count)]
        for _ in range(7):
            for hand in self.hands:
                hand.append(self.draw_pile.pop())
        self.discard: list[UnoCard] = []
        while self.draw_pile:
            card = self.draw_pile.pop()
            if card[1] in {"wild", "wild_draw4"}:
                self.draw_pile.insert(0, card)
                continue
            self.discard.append(card)
            break
        if not self.discard:  # defensive fallback for an impossible deck
            self.discard.append(("red", "0"))
        self.current_player = 0
        self.direction = 1
        self.current_color = self.discard[-1][0]
        self.penalty = 0

    @property
    def top_card(self) -> UnoCard:
        return self.discard[-1]

    def _next(self, player: int, steps: int = 1) -> int:
        return (player + self.direction * steps) % self.player_count

    def _refill(self) -> None:
        if len(self.discard) <= 1:
            return
        top = self.discard[-1]
        self.draw_pile.extend(self.discard[:-1])
        self.discard = [top]
        self.rng.shuffle(self.draw_pile)

    def _draw_one(self, player: int) -> Optional[UnoCard]:
        if not self.draw_pile:
            self._refill()
        if not self.draw_pile:
            return None
        card = self.draw_pile.pop()
        self.hands[player].append(card)
        return card

    def _is_playable(self, card: UnoCard) -> bool:
        color, value = card
        if value == "wild":
            return True
        if value == "wild_draw4":
            return not any(c == self.current_color for c, _ in self.hands[self.current_player])
        return color == self.current_color or value == self.top_card[1]

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[dict[str, Any]]:
        pid = self.current_player if player_id is None else int(player_id)
        if pid != self.current_player or self.is_finished() or self.paused:
            return []
        if self.penalty:
            return [{"type": "draw"}]
        # Present playable cards first so a generic “take the first legal
        # action” bot makes progress instead of repeatedly drawing while a
        # playable card is already available.
        actions: list[dict[str, Any]] = []
        for card in self.hands[pid]:
            if self._is_playable(card):
                action = {"type": "play", "card": list(card)}
                if card[1] in {"wild", "wild_draw4"}:
                    action["color"] = self.COLORS[0]
                actions.append(action)
        actions.append({"type": "draw"})
        return actions

    def apply_action(self, action: Any, player_id: Optional[int] = None) -> ActionResult:
        if self.paused or self.is_finished():
            return ActionResult(False, "game_finished_or_paused")
        pid = self.current_player if player_id is None else int(player_id)
        if pid != self.current_player:
            return ActionResult(False, "not_your_turn")
        if not isinstance(action, dict):
            return ActionResult(False, "invalid_action")
        kind = str(action.get("type", action.get("action", ""))).lower()
        if kind == "draw":
            count = self.penalty or 1
            drawn = [self._draw_one(pid) for _ in range(count)]
            self.penalty = 0
            self.current_player = self._next(pid)
            return ActionResult(True, outcome=self.status,
                                payload={"drawn": [list(card) for card in drawn if card]})
        if kind != "play":
            return ActionResult(False, "unknown_action")
        raw = action.get("card")
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            return ActionResult(False, "invalid_card")
        card: UnoCard = (str(raw[0]), str(raw[1]))
        if card not in self.hands[pid]:
            return ActionResult(False, "card_not_in_hand")
        if self.penalty:
            return ActionResult(False, "draw_penalty_pending")
        if not self._is_playable(card):
            return ActionResult(False, "card_not_playable")
        chosen_color = str(action.get("color", ""))
        if card[1] in {"wild", "wild_draw4"} and chosen_color not in self.COLORS:
            return ActionResult(False, "wild_color_required")
        self.hands[pid].remove(card)
        self.discard.append(card)
        self.current_color = chosen_color if card[1].startswith("wild") else card[0]
        if not self.hands[pid]:
            self.status, self.winner = "finished", pid
            return ActionResult(True, outcome=self.status, payload={"winner": pid})
        steps = 1
        if card[1] == "reverse":
            self.direction *= -1
            if self.player_count == 2:
                steps = 2
        elif card[1] == "skip":
            steps = 2
        elif card[1] == "draw2":
            self.penalty = 2
        elif card[1] == "wild_draw4":
            self.penalty = 4
        self.current_player = self._next(pid, steps)
        return ActionResult(True, outcome=self.status,
                            payload={"next_player": self.current_player, "color": self.current_color})

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        pid = None if player_id is None else int(player_id)
        return {
            "game_id": self.game_id, "status": self.status, "current_player": self.current_player,
            "direction": self.direction, "current_color": self.current_color,
            "discard_top": list(self.top_card), "draw_count": len(self.draw_pile),
            "hand": [list(card) for card in self.hands[pid]] if pid in range(self.player_count) else [],
            "hand_counts": [len(hand) for hand in self.hands], "player_id": pid,
            "winner": self.winner,
        }

    def save_state(self) -> dict[str, Any]:
        return {**self._base_state(), "player_count": self.player_count, "seed": self.seed,
                "draw_pile": _jsonable(self.draw_pile), "hands": _jsonable(self.hands),
                "discard": _jsonable(self.discard), "current_player": self.current_player,
                "direction": self.direction, "current_color": self.current_color,
                "penalty": self.penalty, "status": self.status, "winner": self.winner,
                "rng_state": _jsonable(self.rng.getstate())}

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("wrong UNO save")
        self.draw_pile = [tuple(card) for card in data["draw_pile"]]
        self.hands = [[tuple(card) for card in hand] for hand in data["hands"]]
        self.discard = [tuple(card) for card in data["discard"]]
        self.current_player = int(data["current_player"]); self.direction = int(data["direction"])
        self.current_color = str(data["current_color"]); self.penalty = int(data.get("penalty", 0))
        self.status = str(data["status"]); self.winner = data.get("winner")
        self.paused = bool(data.get("paused", False))
        if data.get("rng_state") is not None:
            self.rng.setstate(_tuple(data["rng_state"]))

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status, "winner": self.winner,
                "hand_counts": [len(hand) for hand in self.hands]}


# ---------------------------------------------------------------------------
# Upgrade / Sheng Ji digital adaptation


UpgradeCard = tuple[str, int, int]  # suit, rank (2–14; jokers 15/16), copy id


class UpgradePokerGame(PartyGameBase):
    """Four-player partnership trick game based on Shengji.

    ``shengji.digital_adaptation.v1`` deliberately fixes two choices that
    vary between tables: hearts are trump and level 2 is the level rank.  It
    uses two 54-card decks, 25 cards per player and an eight-card kitty.  There
    is no bidding or kitty exchange in this first party implementation; this
    is documented as a digital adaptation rather than universal tradition.
    """

    game_id = "upgrade_poker"
    ruleset_id = "shengji.digital_adaptation.v1"
    ruleset_version = "1.0"
    min_players = max_players = 4
    SUITS = ("spades", "hearts", "diamonds", "clubs")

    def __init__(self, seed: int = 0, trump_suit: str = "hearts", level_rank: int = 2) -> None:
        if trump_suit not in self.SUITS:
            raise ValueError("invalid trump suit")
        self.seed, self.trump_suit, self.level_rank = int(seed), trump_suit, int(level_rank)
        self.rng = random.Random(self.seed)
        self.restart()

    @classmethod
    def build_deck(cls) -> list[UpgradeCard]:
        deck: list[UpgradeCard] = []
        for copy_id in (0, 1):
            for suit in cls.SUITS:
                for rank in range(2, 15):
                    deck.append((suit, rank, copy_id))
            deck.extend([("joker", 15, copy_id), ("joker", 16, copy_id)])
        assert len(deck) == 108
        return deck

    def restart(self) -> None:
        self.paused = False; self.status = "playing"; self.winner_team = None
        self.rng = random.Random(self.seed); deck = self.build_deck(); self.rng.shuffle(deck)
        self.hands = [[] for _ in range(4)]
        for _ in range(25):
            for hand in self.hands:
                hand.append(deck.pop())
        self.kitty = deck
        self.current_player = 0
        self.lead_suit: Optional[str] = None
        self.trick: list[tuple[int, UpgradeCard]] = []
        self.scores = [0, 0]
        self.tricks_won = [0, 0]

    @staticmethod
    def _card(value: Any) -> UpgradeCard:
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ValueError("invalid Upgrade card")
        return (str(value[0]), int(value[1]), int(value[2]))

    def _is_trump(self, card: UpgradeCard) -> bool:
        suit, rank, _ = card
        return suit == "joker" or suit == self.trump_suit or rank == self.level_rank

    def _effective_suit(self, card: UpgradeCard) -> str:
        suit, rank, _ = card
        if suit == "joker" or rank == self.level_rank:
            return "trump"
        return suit

    def _power(self, card: UpgradeCard) -> tuple[int, int, int]:
        suit, rank, copy_id = card
        # Big joker > small joker > trump level > other trump > lead suit.
        if suit == "joker":
            return (5, rank, copy_id)
        if rank == self.level_rank and suit == self.trump_suit:
            return (4, rank, copy_id)
        if suit == self.trump_suit:
            return (3, rank, copy_id)
        if rank == self.level_rank:
            return (2, rank, copy_id)
        return (1, rank, copy_id)

    def _follows_lead(self, card: UpgradeCard) -> bool:
        if not self.trick or self.lead_suit is None:
            return True
        has_lead = any(self._effective_suit(item) == self.lead_suit for item in self.hands[self.current_player])
        return not has_lead or self._effective_suit(card) == self.lead_suit

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[dict[str, Any]]:
        pid = self.current_player if player_id is None else int(player_id)
        if self.is_finished() or self.paused or pid != self.current_player:
            return []
        return [{"type": "play", "card": list(card)} for card in self.hands[pid]
                if self._follows_lead(card)]

    def apply_action(self, action: Any, player_id: Optional[int] = None) -> ActionResult:
        if self.paused or self.is_finished():
            return ActionResult(False, "game_finished_or_paused")
        pid = self.current_player if player_id is None else int(player_id)
        if pid != self.current_player:
            return ActionResult(False, "not_your_turn")
        if not isinstance(action, dict) or str(action.get("type", "play")) != "play":
            return ActionResult(False, "invalid_action")
        try:
            card = self._card(action.get("card"))
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_card")
        if card not in self.hands[pid]:
            return ActionResult(False, "card_not_in_hand")
        if not self._follows_lead(card):
            return ActionResult(False, "must_follow_suit")
        self.hands[pid].remove(card)
        if not self.trick:
            self.lead_suit = self._effective_suit(card)
        self.trick.append((pid, card))
        if len(self.trick) < 4:
            self.current_player = (pid + 1) % 4
            return ActionResult(True, outcome=self.status)
        winner, _ = max(self.trick, key=lambda item: self._power(item[1]) if self._effective_suit(item[1]) in {self.lead_suit, "trump"} else (0, 0, 0))
        points = sum(5 if card[1] == 5 else 10 if card[1] in {10, 13} else 0 for _, card in self.trick)
        team = winner % 2
        self.scores[team] += points; self.tricks_won[team] += 1
        self.trick = []; self.lead_suit = None; self.current_player = winner
        if not any(self.hands):
            self.status = "finished"
            self.winner_team = 0 if self.scores[0] > self.scores[1] else 1 if self.scores[1] > self.scores[0] else None
        return ActionResult(True, outcome=self.status,
                            payload={"trick_winner": winner, "points": points, "team": team})

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        pid = None if player_id is None else int(player_id)
        return {
            "game_id": self.game_id, "status": self.status, "current_player": self.current_player,
            "trump_suit": self.trump_suit, "level_rank": self.level_rank,
            "hand": [_jsonable(card) for card in self.hands[pid]] if pid in range(4) else [],
            "hand_counts": [len(hand) for hand in self.hands],
            "trick": [{"player": p, "card": list(card)} for p, card in self.trick],
            "scores": self.scores[:], "tricks_won": self.tricks_won[:], "player_id": pid,
        }

    def save_state(self) -> dict[str, Any]:
        return {**self._base_state(), "seed": self.seed, "trump_suit": self.trump_suit,
                "level_rank": self.level_rank, "hands": _jsonable(self.hands),
                "kitty": _jsonable(self.kitty), "current_player": self.current_player,
                "lead_suit": self.lead_suit, "trick": _jsonable(self.trick),
                "scores": self.scores[:], "tricks_won": self.tricks_won[:],
                "status": self.status, "winner_team": self.winner_team,
                "rng_state": _jsonable(self.rng.getstate())}

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("wrong Upgrade save")
        self.hands = [[tuple(card) for card in hand] for hand in data["hands"]]
        self.kitty = [tuple(card) for card in data["kitty"]]
        self.current_player = int(data["current_player"]); self.lead_suit = data.get("lead_suit")
        self.trick = [(int(item[0]), tuple(item[1])) for item in data.get("trick", [])]
        self.scores = [int(x) for x in data["scores"]]; self.tricks_won = [int(x) for x in data["tricks_won"]]
        self.status = str(data["status"]); self.winner_team = data.get("winner_team")
        self.paused = bool(data.get("paused", False))
        if data.get("rng_state") is not None:
            self.rng.setstate(_tuple(data["rng_state"]))

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status, "winner_team": self.winner_team,
                "scores": self.scores[:], "tricks_won": self.tricks_won[:],
                "cards_remaining": sum(len(hand) for hand in self.hands)}


# ---------------------------------------------------------------------------
# Blackjack / 21 (free-play points, no wagers)


BlackjackCard = tuple[int, str]


class BlackjackGame(PartyGameBase):
    """Score-only blackjack for one to four local/LAN party players.

    One 52-card deck is used for a round.  Dealer stands on soft 17; players
    can hit, stand, or double once before drawing.  Split and insurance are
    intentionally omitted and documented as future variants.  ``points`` are
    an arcade score, never a wager or a redeemable balance.
    """

    game_id = "blackjack"
    ruleset_id = "blackjack.free_play_digital.v1"
    ruleset_version = "1.0"
    min_players, max_players = 1, 4

    def __init__(self, players: int = 1, seed: int = 0) -> None:
        if not self.min_players <= int(players) <= self.max_players:
            raise ValueError("Blackjack supports one to four players")
        self.player_count, self.seed = int(players), int(seed)
        self.rng = random.Random(self.seed); self.restart()

    @staticmethod
    def build_deck() -> list[BlackjackCard]:
        return [(rank, suit) for suit in ("spades", "hearts", "diamonds", "clubs")
                for rank in range(1, 14)]

    def restart(self) -> None:
        self.paused = False; self.status = "playing"; self.rng = random.Random(self.seed)
        self.deck = self.build_deck(); self.rng.shuffle(self.deck)
        self.hands = [[] for _ in range(self.player_count)]
        self.dealer: list[BlackjackCard] = []
        for _ in range(2):
            for hand in self.hands:
                hand.append(self.deck.pop())
            self.dealer.append(self.deck.pop())
        self.player_status = ["playing"] * self.player_count
        self.current_player = 0; self.points = [0] * self.player_count
        self.outcomes = [None] * self.player_count

    @staticmethod
    def hand_value(hand: list[BlackjackCard]) -> tuple[int, bool]:
        total = sum(min(rank, 10) for rank, _ in hand)
        aces = sum(rank == 1 for rank, _ in hand)
        soft = False
        while aces and total + 10 <= 21:
            total += 10; aces -= 1; soft = True
        return total, soft

    def _advance(self) -> None:
        while self.current_player < self.player_count and self.player_status[self.current_player] != "playing":
            self.current_player += 1
        if self.current_player >= self.player_count:
            self._dealer_and_resolve()

    def _dealer_and_resolve(self) -> None:
        while True:
            value, soft = self.hand_value(self.dealer)
            if value < 17: self.dealer.append(self.deck.pop()); continue
            break  # dealer stands on soft 17
        dealer_value, _ = self.hand_value(self.dealer)
        dealer_bust = dealer_value > 21
        for pid, hand in enumerate(self.hands):
            value, _ = self.hand_value(hand)
            if value > 21:
                self.outcomes[pid] = "bust"; self.points[pid] = -1
            elif len(hand) == 2 and value == 21:
                self.outcomes[pid] = "blackjack"; self.points[pid] = 3
            elif dealer_bust or value > dealer_value:
                self.outcomes[pid] = "win"; self.points[pid] = 2
            elif value == dealer_value:
                self.outcomes[pid] = "push"; self.points[pid] = 0
            else:
                self.outcomes[pid] = "lose"; self.points[pid] = -1
        self.status = "finished"

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[dict[str, str]]:
        pid = self.current_player if player_id is None else int(player_id)
        if self.is_finished() or self.paused or pid != self.current_player:
            return []
        actions = [{"type": "hit"}, {"type": "stand"}]
        if len(self.hands[pid]) == 2:
            actions.append({"type": "double"})
        return actions

    def apply_action(self, action: Any, player_id: Optional[int] = None) -> ActionResult:
        if self.paused or self.is_finished(): return ActionResult(False, "game_finished_or_paused")
        pid = self.current_player if player_id is None else int(player_id)
        if pid != self.current_player: return ActionResult(False, "not_your_turn")
        if not isinstance(action, dict): return ActionResult(False, "invalid_action")
        kind = str(action.get("type", action.get("action", ""))).lower()
        if kind == "double" and len(self.hands[pid]) != 2:
            return ActionResult(False, "double_only_on_first_turn")
        if kind not in {"hit", "stand", "double"}:
            return ActionResult(False, "unknown_action")
        if kind in {"hit", "double"}:
            self.hands[pid].append(self.deck.pop())
            value, _ = self.hand_value(self.hands[pid])
            if kind == "hit" and value <= 21:
                # A non-busting hit keeps the same player active; changing
                # turns here would make repeated hits impossible.
                return ActionResult(True, outcome=self.status,
                                    payload={"player": pid, "value": value, "next_player": pid})
            if value > 21 or kind == "double":
                self.player_status[pid] = "done"
            if value > 21: self.player_status[pid] = "bust"
        else:
            self.player_status[pid] = "done"
        self.current_player += 1; self._advance()
        return ActionResult(True, outcome=self.status, payload={"player": pid, "value": self.hand_value(self.hands[pid])[0]})

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        pid = None if player_id is None else int(player_id)
        dealer_visible = [list(self.dealer[0])] if self.dealer else []
        return {
            "game_id": self.game_id, "status": self.status, "current_player": self.current_player,
            "hand": [list(card) for card in self.hands[pid]] if pid in range(self.player_count) else [],
            "hand_counts": [len(hand) for hand in self.hands], "dealer_visible": dealer_visible,
            "dealer_card_count": len(self.dealer), "points": self.points[:],
            "outcome": self.outcomes[pid] if pid in range(self.player_count) and self.status == "finished" else None,
            "player_id": pid,
        }

    def save_state(self) -> dict[str, Any]:
        return {**self._base_state(), "seed": self.seed, "player_count": self.player_count,
                "deck": _jsonable(self.deck), "hands": _jsonable(self.hands), "dealer": _jsonable(self.dealer),
                "player_status": self.player_status[:], "current_player": self.current_player,
                "points": self.points[:], "outcomes": self.outcomes[:], "status": self.status,
                "rng_state": _jsonable(self.rng.getstate())}

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id): raise ValueError("wrong Blackjack save")
        self.deck = [tuple(card) for card in data["deck"]]; self.hands = [[tuple(card) for card in hand] for hand in data["hands"]]
        self.dealer = [tuple(card) for card in data["dealer"]]; self.player_status = list(data["player_status"])
        self.current_player = int(data["current_player"]); self.points = [int(x) for x in data["points"]]
        self.outcomes = list(data["outcomes"]); self.status = str(data["status"]); self.paused = bool(data.get("paused", False))
        if data.get("rng_state") is not None: self.rng.setstate(_tuple(data["rng_state"]))

    def get_result(self) -> dict[str, Any]:
        dealer_value, _ = self.hand_value(self.dealer)
        return {"status": self.status, "dealer_value": dealer_value if self.status == "finished" else None,
                "outcomes": self.outcomes[:], "points": self.points[:]}


# ---------------------------------------------------------------------------
# Free-play probability machines


class PrizeReelsGame(PartyGameBase):
    """A no-money three-reel score toy for a party kiosk."""

    game_id = "prize_reels"
    ruleset_id = "free_play_reels.v1"
    ruleset_version = "1.0"
    min_players = max_players = 1
    supports_lan = False
    SYMBOLS = ("sun", "moon", "star", "comet", "crown")
    PAYOUTS = {"sun": 2, "moon": 3, "star": 5, "comet": 8, "crown": 20}

    def __init__(self, seed: int = 0, max_spins: int = 100) -> None:
        self.seed, self.max_spins = int(seed), int(max_spins)
        self.rng = random.Random(self.seed); self.restart()

    def restart(self) -> None:
        self.paused = False; self.status = "playing"; self.spins = 0; self.points = 0; self.last_result = []
        self.rng = random.Random(self.seed)

    def spin(self) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        if self.spins >= self.max_spins: self.status = "finished"; return ActionResult(False, "spins_exhausted")
        self.last_result = [self.rng.choice(self.SYMBOLS) for _ in range(3)]
        self.spins += 1
        counts = Counter(self.last_result)
        reward = max((self.PAYOUTS[s] for s, count in counts.items() if count >= 2), default=0)
        if len(counts) == 1: reward = self.PAYOUTS[self.last_result[0]] * 3
        self.points += reward
        if self.spins >= self.max_spins: self.status = "finished"
        return ActionResult(True, outcome=self.status, payload={"symbols": self.last_result[:], "points": reward})

    def apply_action(self, action: Any) -> ActionResult:
        if action == "spin" or (isinstance(action, dict) and action.get("type") == "spin"):
            return self.spin()
        return ActionResult(False, "unknown_action")

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {"game_id": self.game_id, "status": self.status, "spins": self.spins,
                "max_spins": self.max_spins, "points": self.points, "last_result": self.last_result[:]}

    def save_state(self) -> dict[str, Any]:
        return {**self._base_state(), "seed": self.seed, "max_spins": self.max_spins, "spins": self.spins,
                "points": self.points, "last_result": self.last_result[:], "status": self.status,
                "rng_state": _jsonable(self.rng.getstate())}

    def load_state(self, data: dict[str, Any]) -> None:
        self.spins = int(data["spins"]); self.points = int(data["points"]); self.last_result = list(data.get("last_result", [])); self.status = str(data["status"]); self.paused = bool(data.get("paused", False))
        if data.get("rng_state") is not None: self.rng.setstate(_tuple(data["rng_state"]))

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status, "spins": self.spins, "points": self.points}


class PrizeWheelGame(PartyGameBase):
    """A one-button score wheel with no wager, currency, or cash-out."""

    game_id = "prize_wheel"
    ruleset_id = "free_play_wheel.v1"
    ruleset_version = "1.0"
    min_players = max_players = 1
    supports_lan = False
    OUTCOMES = (("small", 1), ("bright", 3), ("bonus", 7), ("jackpot", 15), ("rest", 0))

    def __init__(self, seed: int = 0, max_spins: int = 50) -> None:
        self.seed, self.max_spins = int(seed), int(max_spins); self.rng = random.Random(self.seed); self.restart()

    def restart(self) -> None:
        self.paused = False; self.status = "playing"; self.spins = 0; self.points = 0; self.last_outcome = None; self.rng = random.Random(self.seed)

    def spin(self) -> ActionResult:
        if self.paused or self.status != "playing": return ActionResult(False, "game_finished_or_paused")
        if self.spins >= self.max_spins: self.status = "finished"; return ActionResult(False, "spins_exhausted")
        label, reward = self.rng.choice(self.OUTCOMES); self.last_outcome = label; self.spins += 1; self.points += reward
        if self.spins >= self.max_spins: self.status = "finished"
        return ActionResult(True, outcome=self.status, payload={"outcome": label, "points": reward})

    def apply_action(self, action: Any) -> ActionResult:
        if action == "spin" or (isinstance(action, dict) and action.get("type") == "spin"): return self.spin()
        return ActionResult(False, "unknown_action")

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {"game_id": self.game_id, "status": self.status, "spins": self.spins, "max_spins": self.max_spins, "points": self.points, "last_outcome": self.last_outcome}

    def save_state(self) -> dict[str, Any]:
        return {**self._base_state(), "seed": self.seed, "max_spins": self.max_spins, "spins": self.spins, "points": self.points, "last_outcome": self.last_outcome, "status": self.status, "rng_state": _jsonable(self.rng.getstate())}

    def load_state(self, data: dict[str, Any]) -> None:
        self.spins = int(data["spins"]); self.points = int(data["points"]); self.last_outcome = data.get("last_outcome"); self.status = str(data["status"]); self.paused = bool(data.get("paused", False))
        if data.get("rng_state") is not None: self.rng.setstate(_tuple(data["rng_state"]))

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status, "spins": self.spins, "points": self.points}


__all__ = [
    "TankBattleGame", "UnoGame", "UpgradePokerGame", "BlackjackGame",
    "PrizeReelsGame", "PrizeWheelGame",
]
