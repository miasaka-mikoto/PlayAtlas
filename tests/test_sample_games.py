"""Headless smoke and rule-invariant tests for the six Stage-1 games.

These tests deliberately exercise the public rule APIs rather than any UI;
they are suitable for CI without Godot or a display server.
"""

from __future__ import annotations

import math

try:
    from playatlas_core.games import (
        Card, CarromGame, GomokuGame, KlondikeGame, MinesweeperGame,
        OwareGame, SnakeGame, Suit,
    )
except ModuleNotFoundError:
    try:
        from PlayAtlas.games import (
            Card, CarromGame, GomokuGame, KlondikeGame, MinesweeperGame,
            OwareGame, SnakeGame, Suit,
        )
    except ModuleNotFoundError:
        from games import (
            Card, CarromGame, GomokuGame, KlondikeGame, MinesweeperGame,
            OwareGame, SnakeGame, Suit,
        )


def test_gomoku_win_illegal_move_and_round_trip() -> None:
    game = GomokuGame(size=9, win_length=5)
    moves = [(0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2), (0, 3), (1, 3)]
    for move in moves:
        assert game.apply_action(move).ok
    before = list(game.board)
    assert not game.apply_action((0, 0)).ok
    assert game.board == before
    assert game.apply_action((0, 4)).outcome == "win"
    assert game.winner == 1
    restored = GomokuGame.from_state(game.save_state())
    assert restored.save_state() == game.save_state()


def test_minesweeper_first_click_safe_flood_loss_and_save() -> None:
    game = MinesweeperGame(width=7, height=7, mines=8, seed=77)
    assert game.reveal((3, 3)).ok
    assert game.generated
    first = game._index(3, 3)
    assert first not in game.mines
    # The selected ruleset excludes the 8-neighbourhood on a normal board.
    assert not (game.mines & set(game._neighbors(first)))
    # Flags are markers and do not reveal a cell.
    hidden = next(i for i in range(49) if i not in game.revealed)
    assert game.toggle_flag(hidden).ok
    assert hidden in game.flags
    assert not game.reveal(hidden).ok
    # Reveal a known mine to check the loss path and complete mine exposure.
    mine = next(iter(game.mines))
    game.flags.discard(mine)
    assert game.reveal(mine).outcome == "lost"
    assert game.status == "lost"
    clone = MinesweeperGame.from_state(game.save_state())
    assert clone.save_state() == game.save_state()


def test_snake_determinism_reverse_and_wall_collision() -> None:
    a, b = SnakeGame(width=10, height=8, seed=123), SnakeGame(width=10, height=8, seed=123)
    assert a.food == b.food
    assert not a.handle_input("left").ok  # immediate reverse is illegal
    assert a.step().ok
    assert b.step().ok
    assert a.save_state() == b.save_state()
    # Build a legal near-wall state without bypassing the rules on the step.
    state = a.save_state()
    state.update({"snake": [[8, 3], [7, 3]], "direction": "right",
                  "pending_direction": None, "food": [1, 1], "status": "playing"})
    a.load_state(state)
    assert a.step().ok
    assert a.step().outcome == "lost"
    clone = SnakeGame.from_state(a.save_state())
    assert clone.save_state() == a.save_state()


def test_oware_sowing_capture_starvation_and_save() -> None:
    game = OwareGame()
    assert game.get_legal_actions() == [0, 1, 2, 3, 4, 5]
    assert game.apply_action(0).ok
    assert sum(game.pits) + sum(game.scores) == 48
    # Only pit 5 can feed an empty opponent row.
    game.load_state({"game_id": "oware", "seeds_per_pit": 4,
                     "pits": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
                     "scores": [0, 0], "current_player": 0, "status": "playing"})
    assert game.get_legal_actions() == [5]
    # A two-seed capture that leaves one opponent seed is legal.
    game.load_state({"game_id": "oware", "seeds_per_pit": 4,
                     "pits": [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
                     "scores": [0, 0], "current_player": 0, "status": "playing"})
    result = game.apply_action(5)
    assert result.ok and result.payload["captured"] == 2
    assert game.scores[0] == 2 and game.pits[6] == 0 and game.pits[7] == 1
    assert OwareGame.from_state(game.save_state()).save_state() == game.save_state()


def _klondike_state_with_ace() -> dict:
    cards = [Card(rank, suit, False) for suit in Suit for rank in range(1, 14)]
    ace = Card(1, Suit.CLUBS, True)
    tableau = [[ace]] + [[] for _ in range(6)]
    remaining = [c.to_dict() for c in cards if not (c.rank == 1 and c.suit == Suit.CLUBS)]
    return {
        "game_id": "klondike", "seed": 0, "draw_count": 1,
        "tableau": [[c.to_dict() for c in pile] for pile in tableau],
        "stock": remaining, "waste": [],
        "foundations": {suit.value: [] for suit in Suit},
        "status": "playing", "move_count": 0, "redeals": 0,
    }


def test_klondike_deck_conservation_draw_recycle_and_foundation() -> None:
    game = KlondikeGame(seed=5)
    assert len(game._all_cards()) == 52
    assert len({(c.rank, c.suit) for c in game._all_cards()}) == 52
    for _ in range(len(game.stock)):
        assert game.draw_stock().ok
    assert game.stock == [] and len(game.waste) == 24
    assert game.draw_stock().outcome == "recycle"
    assert len(game._all_cards()) == 52
    custom = KlondikeGame.from_state(_klondike_state_with_ace())
    assert custom.move_tableau_to_foundation(0).ok
    assert len(custom.foundations[Suit.CLUBS]) == 1
    assert custom.save_state() == KlondikeGame.from_state(custom.save_state()).save_state()


def test_carrom_input_physics_settle_and_snapshot() -> None:
    game = CarromGame()
    assert len(game.pieces) == 19
    assert not game.place_striker(0.01).ok
    assert game.place_striker(0.5).ok
    assert not game.strike(0.0, 0.0).ok
    assert game.strike(math.pi / 2, 0.18).ok
    # Advance real physics until the turn resolves; the bound catches a
    # tunnelling/stuck-piece regression without assuming a particular pocket.
    for _ in range(2500):
        if game.phase == "aiming":
            break
        game.fixed_update(1 / 120)
    assert game.phase == "aiming"
    assert game.move_count == 1
    clone = CarromGame.from_state(game.save_state())
    assert clone.save_state() == game.save_state()
