"""Package-local CI checks for the six Stage-1 sample rule engines.

The project QA runner discovers this file with stdlib ``unittest`` so the
checks remain available in a portable source/Windows bundle even when pytest
is not installed.
"""

from __future__ import annotations

import json
import math
import unittest

try:
    from playatlas_core.games import (
        CarromGame, GomokuGame, KlondikeGame, MinesweeperGame, OwareGame,
        SnakeGame, Suit,
    )
except ModuleNotFoundError:
    try:
        from PlayAtlas.games import (
            CarromGame, GomokuGame, KlondikeGame, MinesweeperGame, OwareGame,
            SnakeGame, Suit,
        )
    except ModuleNotFoundError:
        from games import (
            CarromGame, GomokuGame, KlondikeGame, MinesweeperGame, OwareGame,
            SnakeGame, Suit,
        )


class Stage1RuleTests(unittest.TestCase):
    def test_gomoku_horizontal_win_and_round_trip(self):
        game = GomokuGame(size=9, win_length=5)
        for action in ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2), (0, 3), (1, 3)):
            self.assertTrue(game.apply_action(action).ok)
        self.assertEqual(game.apply_action((0, 4)).outcome, "win")
        self.assertEqual(GomokuGame.from_state(game.save_state()).save_state(), game.save_state())

    def test_minesweeper_first_click_safe_and_loss(self):
        game = MinesweeperGame(7, 7, 8, seed=77)
        self.assertTrue(game.reveal((3, 3)).ok)
        first = game._index(3, 3)
        self.assertNotIn(first, game.mines)
        self.assertFalse(game.mines & set(game._neighbors(first)))
        mine = next(iter(game.mines))
        game.flags.discard(mine)
        self.assertEqual(game.reveal(mine).outcome, "lost")
        payload = json.loads(json.dumps(game.save_state()))
        self.assertEqual(MinesweeperGame.from_state(payload).save_state(), game.save_state())

    def test_snake_determinism_and_collision(self):
        left = SnakeGame(10, 8, seed=123)
        right = SnakeGame(10, 8, seed=123)
        self.assertEqual(left.food, right.food)
        self.assertFalse(left.handle_input("left").ok)
        left_state = left.save_state()
        left_state.update({"snake": [[8, 3], [7, 3]], "direction": "right",
                           "pending_direction": None, "food": [1, 1], "status": "playing"})
        left.load_state(left_state)
        left.step()
        self.assertEqual(left.step().outcome, "lost")

    def test_oware_feed_and_capture(self):
        game = OwareGame()
        game.load_state({"game_id": "oware", "pits": [0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0],
                         "scores": [0, 0], "current_player": 0, "status": "playing"})
        result = game.apply_action(5)
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["captured"], 2)
        self.assertEqual(game.scores[0], 2)
        self.assertEqual(OwareGame.from_state(game.save_state()).save_state(), game.save_state())

    def test_klondike_complete_deck_and_draw_recycle(self):
        game = KlondikeGame(seed=5)
        self.assertEqual(len(game._all_cards()), 52)
        for _ in range(len(game.stock)):
            self.assertTrue(game.draw_stock().ok)
        self.assertEqual(game.draw_stock().outcome, "recycle")
        self.assertEqual(len(game._all_cards()), 52)

    def test_carrom_strike_settles_and_round_trips(self):
        game = CarromGame()
        self.assertFalse(game.place_striker(0.01).ok)
        self.assertTrue(game.place_striker(0.5).ok)
        self.assertTrue(game.strike(math.pi / 2, 0.18).ok)
        for _ in range(2500):
            if game.phase == "aiming":
                break
            game.fixed_update(1 / 120)
        self.assertEqual(game.phase, "aiming")
        self.assertEqual(CarromGame.from_state(game.save_state()).save_state(), game.save_state())


if __name__ == "__main__":
    unittest.main()
