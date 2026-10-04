"""Headless invariants for the four next-wave PlayAtlas rule engines."""

from __future__ import annotations

import json

try:
    from playatlas_core.games import (
        BreakoutGame, DotsAndBoxesGame, MatchingTilesGame, SudokuGame,
        sudoku_count_solutions,
    )
except ModuleNotFoundError:
    try:
        from PlayAtlas.games import (
            BreakoutGame, DotsAndBoxesGame, MatchingTilesGame, SudokuGame,
            sudoku_count_solutions,
        )
    except ModuleNotFoundError:
        from games import (
            BreakoutGame, DotsAndBoxesGame, MatchingTilesGame, SudokuGame,
            sudoku_count_solutions,
        )


def test_breakout_fixed_step_clears_brick_and_round_trips() -> None:
    game = BreakoutGame(columns=1, rows=1, seed=3)
    # Put the ball just below the only brick, travelling upward.  This is a
    # legal physics state and avoids relying on a long wall-clock simulation.
    brick = game.bricks[0]
    game.ball_x = brick["x"] + brick["w"] / 2
    game.ball_y = brick["y"] + brick["h"] + game.ball_radius + 0.002
    game.ball_vx, game.ball_vy, game.launched = 0.0, -0.5, True
    assert game.fixed_update(0.02).ok
    assert game.score == 10
    assert game.get_result()["bricks_remaining"] == 0
    assert game.status == "won"
    payload = json.loads(json.dumps(game.save_state()))
    assert BreakoutGame.from_state(payload).save_state() == game.save_state()


def test_breakout_paddle_bounds_and_life_loss() -> None:
    game = BreakoutGame(columns=2, rows=1, seed=0)
    game.move_paddle(-10)
    assert game.paddle_x == game.paddle_width / 2
    game.move_paddle(10)
    assert game.paddle_x == 1 - game.paddle_width / 2
    game.ball_y, game.ball_vy, game.launched = 1.1, 1.0, True
    assert game.fixed_update(1 / 60).ok
    assert game.lives == 2
    assert not game.launched


def test_sudoku_known_puzzle_is_unique_and_solver_returns_valid_solution() -> None:
    puzzle = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9],
    ]
    assert sudoku_count_solutions(puzzle) == 1
    game = SudokuGame(puzzle=puzzle)
    assert game.unique_solution
    assert game.solution[0] == [5, 3, 4, 6, 7, 8, 9, 1, 2]
    assert not game.set_value(0, 0, 4).ok  # given cell cannot be changed
    assert not game.set_value(0, 2, 5).ok  # duplicate in row/column
    assert game.set_value(0, 2, 4).ok
    assert game.hint() is not None


def test_sudoku_generated_puzzle_has_real_unique_solution_and_save_round_trip() -> None:
    game = SudokuGame(seed=44, difficulty="hard")
    assert game.unique_solution
    assert sudoku_count_solutions(game.puzzle) == 1
    assert game.get_result()["clues"] < 81
    # The serialized representation is JSON-safe (including note sets).
    payload = json.loads(json.dumps(game.save_state()))
    clone = SudokuGame.from_state(payload)
    assert clone.save_state() == game.save_state()


def test_matching_tiles_two_turn_path_and_pair_conservation() -> None:
    board = [
        [1, 5, 0, 0, 1],
        [0, 5, 0, 0, 0],
    ]
    game = MatchingTilesGame(rows=2, columns=5, tile_types=5, board=board)
    path = game.find_path((0, 0), (0, 4))
    assert path is not None
    directions = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:])]
    turns = sum(previous != current for previous, current in zip(directions, directions[1:]))
    assert turns <= 2
    assert game.match((0, 0), (0, 4)).ok
    assert game.board[0][0] == game.board[0][4] == 0
    assert sum(tile == 5 for row in game.board for tile in row) == 2
    payload = json.loads(json.dumps(game.save_state()))
    assert MatchingTilesGame.from_state(payload).save_state() == game.save_state()


def test_matching_tiles_blocked_pair_is_illegal_and_shuffle_preserves_counts() -> None:
    board = [
        [0, 0, 0, 0],
        [0, 1, 2, 0],
        [0, 2, 1, 0],
        [0, 0, 0, 0],
    ]
    game = MatchingTilesGame(rows=4, columns=4, tile_types=2, board=board)
    before = {value: sum(tile == value for row in game.board for tile in row)
              for value in (1, 2)}
    assert not game.can_connect((1, 1), (2, 2))
    assert not game.match((1, 1), (2, 2)).ok
    game.shuffle()
    after = {value: sum(tile == value for row in game.board for tile in row)
             for value in (1, 2)}
    assert before == after


def test_matching_tiles_custom_odd_layout_allows_empty_blocker_cell() -> None:
    game = MatchingTilesGame(rows=3, columns=3, tile_types=4,
                             board=[[1, 0, 1], [2, 3, 2], [3, 4, 4]])
    assert game.board[0][1] == 0
    assert game.can_connect((0, 0), (0, 2))


def test_dots_and_boxes_completion_grants_extra_turn_and_finishes() -> None:
    game = DotsAndBoxesGame(width=1, height=1)
    assert game.apply_action(("h", 0, 0)).ok
    assert game.current_player == 1
    assert game.apply_action(("v", 0, 0)).ok
    assert game.current_player == 0
    assert game.apply_action(("h", 1, 0)).ok
    assert game.current_player == 1
    result = game.apply_action(((0, 1), (1, 1)))
    assert result.ok
    assert result.payload["completed"] == [(0, 0)]
    assert game.status == "finished"
    assert game.scores == [0, 1]
    assert game.outcome() == "player_1_win"
    payload = json.loads(json.dumps(game.save_state()))
    assert DotsAndBoxesGame.from_state(payload).save_state() == game.save_state()


def test_dots_and_boxes_rejects_duplicate_and_out_of_bounds_edges() -> None:
    game = DotsAndBoxesGame(width=2, height=2)
    assert game.apply_action((0, 0, "h")).ok
    assert not game.apply_action(("h", 0, 0)).ok
    assert not game.apply_action(("v", 99, 0)).ok
    assert len(game.get_legal_actions()) == game.total_edges - 1
