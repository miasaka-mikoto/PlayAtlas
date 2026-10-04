try:
    from playatlas_core.games.extended import (
        BowlingGame, ConnectFourGame, CrazyEightsGame, FifteenPuzzleGame,
        GoFishGame, MiniGolfGame, Puzzle2048Game, ReversiGame, SokobanGame,
        SungkaGame,
    )
except ModuleNotFoundError:
    try:
        from PlayAtlas.games.extended import (
            BowlingGame, ConnectFourGame, CrazyEightsGame, FifteenPuzzleGame,
            GoFishGame, MiniGolfGame, Puzzle2048Game, ReversiGame, SokobanGame,
            SungkaGame,
        )
    except ModuleNotFoundError:
        from games.extended import (
            BowlingGame, ConnectFourGame, CrazyEightsGame, FifteenPuzzleGame,
            GoFishGame, MiniGolfGame, Puzzle2048Game, ReversiGame, SokobanGame,
            SungkaGame,
        )


def test_connect_four_win_and_illegal_column():
    g = ConnectFourGame()
    for col in (0, 0, 1, 1, 2, 2, 3):
        assert g.apply_action(col)
    assert g.winner == 1
    assert not g.apply_action(4)


def test_reversi_initial_legal_move_flips():
    g = ReversiGame()
    assert (2, 3) in g.get_legal_actions()
    result = g.apply_action((2, 3))
    assert result and g.board[3][3] == 1
    assert sum(x == 1 for row in g.board for x in row) == 4


def test_2048_single_merge_does_not_double_merge():
    g = Puzzle2048Game(seed=1)
    g.board = [[2, 2, 2, 2], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    assert g.move("left")
    assert g.board[0][:4] == [4, 4, 0, 0]


def test_sokoban_reset_and_undo():
    g = SokobanGame()
    start = g.player
    assert g.move(0, 1)
    assert g.undo()
    assert g.player == start


def test_fifteen_only_adjacent_moves_are_legal():
    g = FifteenPuzzleGame(seed=4, shuffle_moves=4)
    before = g.board[:]
    assert not g.move((g.blank + 2) % 16)
    assert g.board == before


def test_sungka_seeded_sowing_preserves_seed_count_until_end():
    g = SungkaGame()
    assert sum(g.pits) + sum(g.stores) == 98
    assert g.apply_action(0)
    assert sum(g.pits) + sum(g.stores) == 98


def test_bowling_perfect_game_scores_300():
    g = BowlingGame()
    for _ in range(12):
        assert g.roll(10)
    assert g.status == "finished"
    assert g.score() == 300


def test_mini_golf_nine_holes():
    g = MiniGolfGame()
    for _ in range(9):
        assert g.finish_hole(3)
    assert g.status == "finished"


def test_card_counts_and_hidden_hand_observation():
    g = CrazyEightsGame(players=2, seed=2)
    obs = g.observation(0)
    assert obs["deck_count"] + sum(obs["hand_sizes"]) + len(g.discard) == 52
    assert "hands" not in obs
    fish = GoFishGame(players=2, seed=2)
    assert sum(len(h) for h in fish.hands) + len(fish.deck) == 52
