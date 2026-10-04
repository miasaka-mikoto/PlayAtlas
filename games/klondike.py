"""Playable Klondike solitaire (draw-one) rule engine.

Ruleset ``klondike.standard_draw1.v1``
--------------------------------------
* A standard 52-card deck is dealt to seven tableau columns; only each
  column's top card is face up.
* Tableau builds descend by alternating colour and may move as a valid
  face-up sequence.  Empty columns accept Kings (or a sequence beginning with
  a King).
* Foundations build Ace through King by suit.
* Stock draws one card.  When empty, the waste is recycled in reverse order;
  unlimited redeals are an explicit digital rule and are recorded in the
  metadata rather than being confused with a draw-three variant.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, Enum
import random
from typing import Any, Optional

from .common import ActionResult


class Suit(str, Enum):
    CLUBS = "clubs"
    DIAMONDS = "diamonds"
    HEARTS = "hearts"
    SPADES = "spades"

    @property
    def red(self) -> bool:
        return self in (Suit.DIAMONDS, Suit.HEARTS)


class Rank(IntEnum):
    ACE = 1
    TWO = 2
    THREE = 3
    FOUR = 4
    FIVE = 5
    SIX = 6
    SEVEN = 7
    EIGHT = 8
    NINE = 9
    TEN = 10
    JACK = 11
    QUEEN = 12
    KING = 13


@dataclass(frozen=True)
class Card:
    rank: int
    suit: Suit | str
    face_up: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "rank", int(self.rank))
        object.__setattr__(self, "suit", Suit(self.suit))
        if self.rank < 1 or self.rank > 13:
            raise ValueError("card rank must be 1..13")

    @property
    def red(self) -> bool:
        return self.suit.red

    def with_face(self, face_up: bool) -> "Card":
        return Card(self.rank, self.suit, bool(face_up))

    def to_dict(self) -> dict[str, Any]:
        return {"rank": self.rank, "suit": self.suit.value, "face_up": self.face_up}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Card":
        return cls(int(data["rank"]), data["suit"], bool(data.get("face_up", True)))


class KlondikeGame:
    game_id = "klondike"
    ruleset_id = "klondike.standard_draw1.v1"
    save_schema_version = 1

    def __init__(self, seed: int = 0, draw_count: int = 1) -> None:
        if draw_count != 1:
            raise ValueError("this ruleset implements draw-one; use a distinct ruleset for draw-three")
        self.seed = int(seed)
        self.draw_count = int(draw_count)
        self.restart()

    def initialize(self, context: Any = None) -> "KlondikeGame":
        return self

    def start(self, config: Optional[dict[str, Any]] = None) -> "KlondikeGame":
        if config and "seed" in config:
            self.seed = int(config["seed"])
        if config and int(config.get("draw_count", 1)) != 1:
            raise ValueError("only draw-one is implemented by this ruleset")
        self.restart()
        return self

    @staticmethod
    def _full_deck() -> list[Card]:
        return [Card(rank, suit, False) for suit in Suit for rank in range(1, 14)]

    def restart(self) -> None:
        deck = self._full_deck()
        random.Random(self.seed).shuffle(deck)
        self.tableau: list[list[Card]] = [[] for _ in range(7)]
        cursor = 0
        for column in range(7):
            for row in range(column + 1):
                card = deck[cursor]
                cursor += 1
                self.tableau[column].append(card.with_face(row == column))
        self.stock: list[Card] = deck[cursor:]
        self.waste: list[Card] = []
        self.foundations: dict[Suit, list[Card]] = {suit: [] for suit in Suit}
        self.status = "playing"
        self.move_count = 0
        self.redeals = 0
        self.paused = False
        self.last_error = ""

    def initialize_deal(self) -> None:
        self.restart()

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def _top(self, pile: list[Card]) -> Optional[Card]:
        return pile[-1] if pile else None

    @staticmethod
    def _tableau_build_valid(cards: list[Card]) -> bool:
        if not cards or any(not c.face_up for c in cards):
            return False
        return all(cards[i].rank == cards[i + 1].rank + 1 and cards[i].red != cards[i + 1].red
                   for i in range(len(cards) - 1))

    @staticmethod
    def _can_place_tableau(card: Card, destination: Optional[Card]) -> bool:
        if destination is None:
            return card.rank == Rank.KING
        return destination.face_up and destination.rank == card.rank + 1 and destination.red != card.red

    @staticmethod
    def _can_place_foundation(card: Card, pile: list[Card]) -> bool:
        if not card.face_up:
            return False
        if not pile:
            return card.rank == Rank.ACE
        top = pile[-1]
        return card.suit == top.suit and card.rank == top.rank + 1

    def draw_stock(self) -> ActionResult:
        if self.paused:
            return ActionResult(False, "game_paused")
        if self.status != "playing":
            return ActionResult(False, "game_finished", self.status)
        if self.stock:
            card = self.stock.pop().with_face(True)
            self.waste.append(card)
            self.move_count += 1
            return ActionResult(True, outcome="continue", payload={"card": card.to_dict()})
        if not self.waste:
            return ActionResult(False, "stock_and_waste_empty")
        # Waste's last item is the visible top; reversing restores the old
        # stock order so the oldest discarded card is drawn first.
        self.stock = [card.with_face(False) for card in reversed(self.waste)]
        self.waste.clear()
        self.redeals += 1
        self.move_count += 1
        return ActionResult(True, outcome="recycle", payload={"redeals": self.redeals})

    def _flip_exposed(self, column: int) -> Optional[Card]:
        if self.tableau[column] and not self.tableau[column][-1].face_up:
            card = self.tableau[column][-1].with_face(True)
            self.tableau[column][-1] = card
            return card
        return None

    def move_waste_to_foundation(self) -> ActionResult:
        if not self.waste:
            return ActionResult(False, "waste_empty")
        card = self.waste[-1]
        if not self._can_place_foundation(card, self.foundations[card.suit]):
            return ActionResult(False, "illegal_foundation_move")
        self.waste.pop()
        self.foundations[card.suit].append(card)
        self.move_count += 1
        self._check_win()
        return ActionResult(True, outcome=self.status, payload={"card": card.to_dict()})

    def move_waste_to_tableau(self, destination: int) -> ActionResult:
        if not 0 <= int(destination) < 7:
            return ActionResult(False, "out_of_bounds")
        destination = int(destination)
        if not self.waste:
            return ActionResult(False, "waste_empty")
        card = self.waste[-1]
        if not self._can_place_tableau(card, self._top(self.tableau[destination])):
            return ActionResult(False, "illegal_tableau_move")
        self.waste.pop()
        self.tableau[destination].append(card)
        self.move_count += 1
        return ActionResult(True, outcome="continue", payload={"card": card.to_dict(), "destination": destination})

    def move_tableau_to_foundation(self, source: int) -> ActionResult:
        if not 0 <= int(source) < 7:
            return ActionResult(False, "out_of_bounds")
        source = int(source)
        card = self._top(self.tableau[source])
        if card is None or not card.face_up:
            return ActionResult(False, "no_face_up_card")
        if not self._can_place_foundation(card, self.foundations[card.suit]):
            return ActionResult(False, "illegal_foundation_move")
        self.tableau[source].pop()
        self.foundations[card.suit].append(card)
        self._flip_exposed(source)
        self.move_count += 1
        self._check_win()
        return ActionResult(True, outcome=self.status, payload={"card": card.to_dict()})

    def move_tableau_sequence(self, source: int, start: int, destination: int) -> ActionResult:
        try:
            source, start, destination = int(source), int(start), int(destination)
        except (TypeError, ValueError):
            return ActionResult(False, "invalid_column")
        if not (0 <= source < 7 and 0 <= destination < 7):
            return ActionResult(False, "out_of_bounds")
        if source == destination:
            return ActionResult(False, "same_column")
        pile = self.tableau[source]
        if not (0 <= start < len(pile)):
            return ActionResult(False, "out_of_bounds")
        moving = pile[start:]
        if not self._tableau_build_valid(moving):
            return ActionResult(False, "invalid_sequence")
        if not self._can_place_tableau(moving[0], self._top(self.tableau[destination])):
            return ActionResult(False, "illegal_tableau_move")
        del pile[start:]
        self.tableau[destination].extend(moving)
        flipped = self._flip_exposed(source)
        self.move_count += 1
        return ActionResult(True, outcome="continue", payload={"cards": [c.to_dict() for c in moving],
                                                                  "flipped": flipped.to_dict() if flipped else None})

    def move_foundation_to_tableau(self, suit: Suit | str, destination: int) -> ActionResult:
        try:
            suit, destination = Suit(suit), int(destination)
        except (ValueError, TypeError):
            return ActionResult(False, "invalid_destination")
        if not 0 <= destination < 7:
            return ActionResult(False, "out_of_bounds")
        pile = self.foundations[suit]
        if not pile:
            return ActionResult(False, "foundation_empty")
        card = pile[-1]
        if not self._can_place_tableau(card, self._top(self.tableau[destination])):
            return ActionResult(False, "illegal_tableau_move")
        pile.pop()
        self.tableau[destination].append(card)
        self.move_count += 1
        return ActionResult(True, outcome="continue", payload={"card": card.to_dict()})

    def auto_move_card(self, source: str, index: int = 0, destination: Optional[int] = None) -> ActionResult:
        """Apply a serialisable action dictionary's common forms.

        ``source`` is ``waste``, ``tableau``, or ``foundation``.  This helper
        is intentionally explicit instead of evaluating arbitrary strings.
        """
        if source == "waste":
            if destination is None:
                return self.move_waste_to_foundation()
            return self.move_waste_to_tableau(destination)
        if source == "tableau":
            if destination is None:
                return self.move_tableau_to_foundation(index)
            return self.move_tableau_sequence(index, 0, destination)
        return ActionResult(False, "unsupported_action")

    def apply_action(self, action: dict[str, Any]) -> ActionResult:
        kind = action.get("type")
        if kind == "draw_stock":
            return self.draw_stock()
        if kind == "waste_to_foundation":
            return self.move_waste_to_foundation()
        if kind == "waste_to_tableau":
            return self.move_waste_to_tableau(int(action["destination"]))
        if kind == "tableau_to_foundation":
            return self.move_tableau_to_foundation(int(action["source"]))
        if kind == "tableau_sequence":
            return self.move_tableau_sequence(int(action["source"]), int(action["start"]), int(action["destination"]))
        if kind == "foundation_to_tableau":
            return self.move_foundation_to_tableau(action["suit"], int(action["destination"]))
        return ActionResult(False, "unknown_action")

    def _check_win(self) -> None:
        if sum(len(pile) for pile in self.foundations.values()) == 52:
            self.status = "won"

    def is_finished(self) -> bool:
        return self.status != "playing"

    def get_legal_actions(self, player_id: Optional[int] = None) -> list[dict[str, Any]]:
        if self.status != "playing" or self.paused:
            return []
        actions: list[dict[str, Any]] = []
        if self.stock or self.waste:
            actions.append({"type": "draw_stock"})
        if self.waste:
            card = self.waste[-1]
            if self._can_place_foundation(card, self.foundations[card.suit]):
                actions.append({"type": "waste_to_foundation"})
            for dest in range(7):
                if self._can_place_tableau(card, self._top(self.tableau[dest])):
                    actions.append({"type": "waste_to_tableau", "destination": dest})
        for source, pile in enumerate(self.tableau):
            top = self._top(pile)
            if top and top.face_up and self._can_place_foundation(top, self.foundations[top.suit]):
                actions.append({"type": "tableau_to_foundation", "source": source})
            for start in range(len(pile)):
                moving = pile[start:]
                if not self._tableau_build_valid(moving):
                    continue
                for dest in range(7):
                    if dest != source and self._can_place_tableau(moving[0], self._top(self.tableau[dest])):
                        actions.append({"type": "tableau_sequence", "source": source,
                                        "start": start, "destination": dest})
        return actions

    @staticmethod
    def _visible_card(card: Card) -> dict[str, Any]:
        return card.to_dict() if card.face_up else {"face_up": False}

    def get_observation(self, player_id: Optional[int] = None) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "ruleset_id": self.ruleset_id,
            "tableau": [[self._visible_card(c) for c in pile] for pile in self.tableau],
            "stock_count": len(self.stock),
            "waste_top": self._visible_card(self.waste[-1]) if self.waste else None,
            "foundations": {suit.value: (pile[-1].to_dict() if pile else None)
                            for suit, pile in self.foundations.items()},
            "status": self.status, "move_count": self.move_count, "redeals": self.redeals,
        }

    def get_result(self) -> dict[str, Any]:
        return {"status": self.status, "foundations": sum(len(p) for p in self.foundations.values()),
                "moves": self.move_count, "redeals": self.redeals}

    def _all_cards(self) -> list[Card]:
        cards: list[Card] = []
        cards.extend(c for pile in self.tableau for c in pile)
        cards.extend(self.stock)
        cards.extend(self.waste)
        cards.extend(c for pile in self.foundations.values() for c in pile)
        return cards

    def save_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id, "game_version": 1,
            "ruleset_id": self.ruleset_id, "ruleset_version": 1,
            "save_schema_version": self.save_schema_version,
            "seed": self.seed, "draw_count": self.draw_count,
            "tableau": [[c.to_dict() for c in pile] for pile in self.tableau],
            "stock": [c.to_dict() for c in self.stock], "waste": [c.to_dict() for c in self.waste],
            "foundations": {suit.value: [c.to_dict() for c in pile]
                            for suit, pile in self.foundations.items()},
            "status": self.status, "move_count": self.move_count,
            "redeals": self.redeals, "paused": self.paused,
        }

    def load_state(self, data: dict[str, Any]) -> None:
        if data.get("game_id") not in (None, self.game_id):
            raise ValueError("state belongs to another game")
        self.seed = int(data.get("seed", 0))
        self.draw_count = int(data.get("draw_count", 1))
        if self.draw_count != 1:
            raise ValueError("unsupported draw count")
        self.tableau = [[Card.from_dict(c) for c in pile] for pile in data["tableau"]]
        self.stock = [Card.from_dict(c) for c in data.get("stock", [])]
        self.waste = [Card.from_dict(c) for c in data.get("waste", [])]
        raw_foundations = data.get("foundations", {})
        self.foundations = {suit: [Card.from_dict(c) for c in raw_foundations.get(suit.value, [])]
                            for suit in Suit}
        if len(self.tableau) != 7:
            raise ValueError("invalid tableau")
        cards = self._all_cards()
        identities = [(c.rank, c.suit.value) for c in cards]
        if len(cards) != 52 or len(set(identities)) != 52:
            raise ValueError("Klondike state must contain exactly one complete deck")
        self.status = str(data.get("status", "playing"))
        if self.status not in ("playing", "won"):
            raise ValueError("invalid Klondike status")
        self.move_count = int(data.get("move_count", 0))
        self.redeals = int(data.get("redeals", 0))
        self.paused = bool(data.get("paused", False))

    @classmethod
    def from_state(cls, data: dict[str, Any]) -> "KlondikeGame":
        game = cls(int(data.get("seed", 0)), int(data.get("draw_count", 1)))
        game.load_state(data)
        return game

    def dispose(self) -> None:
        self.paused = True

