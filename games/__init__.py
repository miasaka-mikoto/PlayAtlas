"""Headless, serialisable rule engines for PlayAtlas sample games."""

from .gomoku import GomokuGame, GomokuAction
from .minesweeper import MinesweeperGame, MinesweeperResult
from .snake import SnakeGame, Direction, SnakeResult

# Optional imports keep the package usable while a staged checkout is being
# assembled.  The final source tree contains all six Stage-1 modules.
try:
    from .oware import OwareGame, OwareResult
except ImportError:  # pragma: no cover
    OwareGame = OwareResult = None
try:
    from .klondike import KlondikeGame, Card, Rank, Suit
except ImportError:  # pragma: no cover
    KlondikeGame = Card = Rank = Suit = None
try:
    from .carrom import CarromGame, CarromResult
except ImportError:  # pragma: no cover
    CarromGame = CarromResult = None
try:
    from .extended import (
        ConnectFourGame, ReversiGame, Puzzle2048Game, SokobanGame,
        FifteenPuzzleGame, SungkaGame, BowlingGame, MiniGolfGame,
        CrazyEightsGame, GoFishGame, PlaceholderRuleGame,
    )
except ImportError:  # pragma: no cover - keeps partial checkouts importable
    ConnectFourGame = ReversiGame = Puzzle2048Game = SokobanGame = None
    FifteenPuzzleGame = SungkaGame = BowlingGame = MiniGolfGame = None
    CrazyEightsGame = GoFishGame = PlaceholderRuleGame = None
try:
    from .expansion import (
        BreakoutGame, SudokuGame, MatchingTilesGame, ShisenShoGame, MahjongConnectGame,
        DotsAndBoxesGame, sudoku_count_solutions, sudoku_solve,
        count_solutions, solve_sudoku,
    )
except ImportError:  # pragma: no cover - keeps partial checkouts importable
    BreakoutGame = SudokuGame = MatchingTilesGame = ShisenShoGame = MahjongConnectGame = None
    DotsAndBoxesGame = None
    sudoku_count_solutions = sudoku_solve = count_solutions = solve_sudoku = None

try:
    from .party import (
        TankBattleGame, UnoGame, UpgradePokerGame, BlackjackGame,
        PrizeReelsGame, PrizeWheelGame,
    )
except ImportError:  # pragma: no cover - keeps staged checkouts importable
    TankBattleGame = UnoGame = UpgradePokerGame = BlackjackGame = None
    PrizeReelsGame = PrizeWheelGame = None
__all__ = [
    "GomokuGame", "GomokuAction", "MinesweeperGame", "MinesweeperResult",
    "SnakeGame", "Direction", "SnakeResult", "OwareGame", "OwareResult",
    "KlondikeGame", "Card", "Rank", "Suit", "CarromGame", "CarromResult",
    "ConnectFourGame", "ReversiGame", "Puzzle2048Game", "SokobanGame",
    "FifteenPuzzleGame", "SungkaGame", "BowlingGame", "MiniGolfGame",
    "CrazyEightsGame", "GoFishGame", "PlaceholderRuleGame",
    "BreakoutGame", "SudokuGame", "MatchingTilesGame", "ShisenShoGame",
    "MahjongConnectGame", "DotsAndBoxesGame", "sudoku_count_solutions", "sudoku_solve",
    "count_solutions", "solve_sudoku",
    "TankBattleGame", "UnoGame", "UpgradePokerGame", "BlackjackGame",
    "PrizeReelsGame", "PrizeWheelGame",
]
