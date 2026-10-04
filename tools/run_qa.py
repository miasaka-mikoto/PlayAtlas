#!/usr/bin/env python3
"""Run truthful, headless PlayAtlas QA checks.

This runner is deliberately independent of Godot.  It exercises Python rule
engines when they are available, loads the catalogue, and writes machine
readable plus human-readable reports.  A successful headless run means only
that the exercised rule code passed these checks; it is *not* a Windows,
Android, visual, audio, or manual acceptance claim.

Usage (from the project directory)::

    python tools/run_qa.py --out reports/qa

The command always writes a report and returns a non-zero exit code when an
implemented module fails a check.  Missing/in-development catalogue entries
are reported as ``待验证`` rather than silently counted as playable.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import os
import platform
import re
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable


ALLOWED_STATUS = {"已实现", "已自动测试", "已人工测试", "待验证", "失败", "阻塞"}
PLAYABLE_STATES = {"playable", "installed", "implemented", "ready"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def jsonable(value: Any) -> Any:
    """Convert common rule objects to a bounded JSON-safe representation."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in list(value.items())[:100]}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in list(value)[:100]]
    if hasattr(value, "__dict__"):
        return {str(k): jsonable(v) for k, v in vars(value).items() if not str(k).startswith("_")}
    return repr(value)


def jsonable_full(value: Any) -> Any:
    """JSON-safe conversion that never truncates a saved game state."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable_full(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable_full(v) for v in value]
    if hasattr(value, "__dict__"):
        return {str(k): jsonable_full(v) for k, v in vars(value).items() if not str(k).startswith("_")}
    return repr(value)


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def read_catalogue(project_root: Path) -> list[dict[str, Any]]:
    candidates = [
        project_root / "data" / "games" / "GAME_CATALOG.json",
        project_root / "data" / "GAME_CATALOG.json",
    ]
    raw: Any = []
    source = None
    for candidate in candidates:
        if candidate.is_file():
            raw = load_json(candidate, [])
            source = candidate
            break
    if isinstance(raw, dict):
        raw = raw.get("games", raw.get("catalogue", []))
    entries: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and str(item.get("id", "")).strip():
                entries.append(dict(item))
    # Keep the source visible to callers without introducing a fake catalogue
    # entry.  This is useful when the report is generated before data lands.
    if source is None:
        return []
    return entries


def import_game_package(project_root: Path) -> ModuleType | None:
    # Running the script as ``python tools/run_qa.py`` puts tools/ on sys.path,
    # not the project root.  Add both project root and its parent so either
    # ``games`` or ``playatlas_core.games`` layouts work.
    for candidate in (project_root, project_root.parent):
        candidate_s = str(candidate.resolve())
        if candidate_s not in sys.path:
            sys.path.insert(0, candidate_s)
    names = [f"{project_root.name}.games", "games"]
    for name in names:
        try:
            return importlib.import_module(name)
        except (ImportError, ModuleNotFoundError):
            continue
    # During incremental development __init__.py can list a module that has
    # not landed yet.  Keep the QA runner useful by creating a *synthetic*
    # namespace package and importing the modules that do exist.  This does
    # not alter source files and still lets relative imports such as
    # ``from .common import ...`` resolve normally.
    package_dir = project_root / "games"
    if package_dir.is_dir():
        import types

        fallback_name = f"{project_root.name}.games"
        fallback = types.ModuleType(fallback_name)
        fallback.__path__ = [str(package_dir)]  # type: ignore[attr-defined]
        fallback.__package__ = fallback_name
        sys.modules[fallback_name] = fallback
        # Also support a project launched with its root directly on sys.path.
        short_name = "games"
        short = types.ModuleType(short_name)
        short.__path__ = [str(package_dir)]  # type: ignore[attr-defined]
        short.__package__ = short_name
        sys.modules.setdefault(short_name, short)
        return fallback
    return None


def class_game_id(cls: type[Any]) -> str:
    return str(getattr(cls, "game_id", "") or getattr(cls, "GAME_ID", ""))


def discover_game_classes(package: ModuleType | None) -> dict[str, type[Any]]:
    """Discover exported classes without importing UI/Godot modules."""
    if package is None:
        return {}
    result: dict[str, type[Any]] = {}
    for name, value in inspect.getmembers(package, inspect.isclass):
        game_id = class_game_id(value)
        if game_id and value.__module__.startswith(package.__name__):
            result.setdefault(game_id, value)
    # A package may intentionally keep __init__.__all__ small.  Import direct
    # Python modules as a fallback, ignoring optional/unfinished modules.
    package_file = getattr(package, "__file__", None)
    if package_file:
        package_dir = Path(package_file).parent
    else:
        paths = list(getattr(package, "__path__", []))
        package_dir = Path(paths[0]) if paths else Path()
    if package_dir.is_dir():
        for file in sorted(package_dir.glob("*.py")):
            if file.name.startswith("_") or file.stem in {"common"}:
                continue
            module_name = f"{package.__name__}.{file.stem}"
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue
            for _, value in inspect.getmembers(module, inspect.isclass):
                game_id = class_game_id(value)
                if game_id and value.__module__ == module.__name__:
                    result.setdefault(game_id, value)
    return result


def instantiate(cls: type[Any]) -> Any:
    attempts = [(), (5,), (8,), (10, 10)]
    last: Exception | None = None
    for args in attempts:
        try:
            return cls(*args)
        except (TypeError, ValueError, KeyError) as exc:
            last = exc
    if last:
        raise last
    raise TypeError(f"unable to instantiate {cls.__name__}")


def invoke_optional(obj: Any, name: str, *args: Any) -> Any:
    method = getattr(obj, name, None)
    if not callable(method):
        return None
    return method(*args)


def result_ok(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, dict) and "ok" in value:
        return bool(value["ok"])
    if hasattr(value, "ok"):
        return bool(value.ok)
    # A None return is common for start/restart and is not an error.
    return value is None or bool(value)


def action_for(value: Any) -> Any:
    # ``get_legal_actions`` returns a list, while one legal action may itself
    # be a tuple (coordinates, a card, or a Shisen-Sho pair).  Unwrapping
    # tuples here would silently turn a two-cell action into its first cell.
    if isinstance(value, list) and value:
        return value[0]
    return value


def invalid_action_for(game: Any, legal: Any) -> Any:
    """Return a conservative invalid action for common action shapes."""
    if isinstance(legal, (list, tuple)) and legal:
        sample = legal[0]
        if isinstance(sample, dict):
            invalid = dict(sample)
            if "index" in invalid:
                invalid["index"] = -999999
            elif "cell" in invalid:
                invalid["cell"] = -999999
            elif "position" in invalid:
                invalid["position"] = -999999
            else:
                invalid.update({"row": -1, "col": -1})
            return invalid
        if isinstance(sample, tuple):
            return tuple(-999 for _ in sample)
        if hasattr(sample, "row") and hasattr(sample, "col"):
            cls = type(sample)
            try:
                return cls(-1, -1)
            except Exception:
                return {"row": -1, "col": -1}
    return {"row": -1, "col": -1}


def apply_game_action(game: Any, action: Any) -> Any:
    """Apply a generic turn action, including small engines with named APIs."""
    apply = getattr(game, "apply_action", None)
    if callable(apply):
        return apply(action)
    if isinstance(action, dict):
        action_type = str(action.get("type", action.get("action", ""))).lower()
        argument = action.get("index", action.get("cell", action.get("position", action)))
        named = {
            "reveal": "reveal",
            "flag": "toggle_flag",
            "toggle_flag": "toggle_flag",
            "chord": "chord",
            "place_striker": "place_striker",
            "move": "move",
            "place": "place",
            "pass": "pass_turn",
        }.get(action_type)
        if named and callable(getattr(game, named, None)):
            if named == "place_striker":
                return getattr(game, named)(0.5)
            return getattr(game, named)(argument)
        if action_type == "strike" and callable(getattr(game, "strike", None)):
            return game.strike(0.0, 0.25)
    return None


def _first_card_action(game: Any) -> Any:
    hands = getattr(game, "hands", [])
    current = int(getattr(game, "current_player", 0))
    hand = hands[current] if isinstance(hands, list) and 0 <= current < len(hands) else []
    top = getattr(game, "discard", [])
    top_card = top[-1] if top else None
    # Crazy Eights: prefer a card that is legal against the current discard.
    if hand and top_card is not None:
        for card in hand:
            if card[1] == 8 or card[0] == top_card[0] or card[1] == top_card[1]:
                return card
    return hand[0] if hand else None


def invoke_first_available_action(game: Any, game_id: str, legal: Any = None) -> tuple[Any, str]:
    """Invoke one conservative real action for engines with named methods."""
    if legal is not None:
        action = action_for(legal)
        if action is not None:
            return apply_game_action(game, action), "legal_actions"
    apply = getattr(game, "apply_action", None)
    if callable(apply):
        if game_id == "sungka":
            pits = getattr(game, "pits", [])
            player = int(getattr(game, "current_player", 0))
            indices = range(0, 7) if player == 0 else range(7, 14)
            action = next((i for i in indices if i < len(pits) and pits[i] > 0), None)
            if action is not None:
                return apply(action), "apply_action"
        # A few compact modules use a scalar action and accept zero as a
        # valid initial action.  If this is rejected, the result is still a
        # useful rule-level finding in the report.
        return apply(0), "apply_action"
    # Table-physics modules generally expose a two-step placement/strike API.
    # Exercise both parts so the QA result is not just a render-loop check.
    place_striker = getattr(game, "place_striker", None)
    strike = getattr(game, "strike", None)
    if callable(place_striker) and callable(strike):
        placed = place_striker(0.5)
        if result_ok(placed):
            return strike(0.0, 0.25), "strike"
        return placed, "place_striker"
    move = getattr(game, "move", None)
    if callable(move):
        try:
            params = list(inspect.signature(move).parameters.values())
        except (TypeError, ValueError):
            params = []
        if len(params) <= 1:
            if game_id == "2048":
                return move("left"), "move"
            if game_id == "fifteen_puzzle":
                blank = int(getattr(game, "blank", 0))
                neighbors = getattr(game, "_neighbors", lambda _x: [])(blank)
                return move(neighbors[0] if neighbors else 0), "move"
            return move(0), "move"
        return move(0, 1), "move"
    play = getattr(game, "play", None)
    if callable(play):
        card = _first_card_action(game)
        if card is not None:
            return play(card), "play"
    ask = getattr(game, "ask", None)
    if callable(ask):
        hands = getattr(game, "hands", [[]])
        current = int(getattr(game, "current_player", 0))
        hand = hands[current] if 0 <= current < len(hands) else []
        rank = int(hand[0][1]) if hand else 1
        target = 1 if current == 0 and len(hands) > 1 else 0
        return ask(target, rank), "ask"
    roll = getattr(game, "roll", None)
    if callable(roll):
        return roll(0), "roll"
    finish_hole = getattr(game, "finish_hole", None)
    if callable(finish_hole):
        return finish_hole(1), "finish_hole"
    draw = getattr(game, "draw", None)
    if callable(draw):
        return draw(), "draw"
    reveal = getattr(game, "reveal", None)
    if callable(reveal):
        return reveal(0), "reveal"
    return None, "none"


def invoke_invalid_action(game: Any, game_id: str, method_name: str) -> Any:
    """Exercise an invalid input for the named-action subset when obvious."""
    if method_name == "apply_action" and callable(getattr(game, "apply_action", None)):
        return game.apply_action(-999999)
    if method_name == "move" and callable(getattr(game, "move", None)):
        return game.move("invalid") if game_id == "2048" else game.move(-999999) if game_id == "fifteen_puzzle" else game.move(-999999, -999999)
    if method_name == "play" and callable(getattr(game, "play", None)):
        return game.play(("?", -1))
    if method_name == "ask" and callable(getattr(game, "ask", None)):
        return game.ask(-1, -1)
    if method_name == "roll" and callable(getattr(game, "roll", None)):
        return game.roll(11)
    if method_name == "finish_hole" and callable(getattr(game, "finish_hole", None)):
        return game.finish_hole(0)
    if method_name == "strike" and callable(getattr(game, "strike", None)):
        return game.strike(0.0, 0.0)
    if method_name == "place_striker" and callable(getattr(game, "place_striker", None)):
        return game.place_striker(-1.0)
    return None


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""
    duration_ms: float = 0.0


@dataclass
class GameReport:
    game_id: str
    title: str = ""
    catalogue_status: str = "unknown"
    implementation_status: str = "待验证"
    automatic_status: str = "待验证"
    checks: list[Check] = field(default_factory=list)
    error: str = ""
    source: str = "headless_python"

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(check.passed for check in self.checks)


def run_check(report: GameReport, name: str, fn) -> None:
    start = time.perf_counter()
    try:
        result = fn()
        passed = bool(result) if result is not None else True
        detail = "" if passed else "returned false"
    except Exception as exc:  # noqa: BLE001 - report the exact QA failure
        passed = False
        detail = f"{type(exc).__name__}: {exc}"
    report.checks.append(Check(name, passed, detail, round((time.perf_counter() - start) * 1000, 3)))


def exercise_game(game_id: str, cls: type[Any], catalogue_entry: dict[str, Any]) -> GameReport:
    report = GameReport(
        game_id=game_id,
        title=str(catalogue_entry.get("title_zh", catalogue_entry.get("title", game_id))),
        catalogue_status=str(catalogue_entry.get("status", "unknown")),
    )
    holder: dict[str, Any] = {}

    def make() -> Any:
        game = instantiate(cls)
        holder["game"] = game
        return game

    run_check(report, "instantiate", lambda: make() is not None)

    def initialize_and_start() -> bool:
        game = holder.get("game") or make()
        initialize = getattr(game, "initialize", None)
        if callable(initialize):
            initialize(None)
        start = getattr(game, "start", None)
        if callable(start):
            result = start({})
            return result_ok(result)
        restart = getattr(game, "restart", None)
        return result_ok(restart()) if callable(restart) else True

    run_check(report, "initialize_start", initialize_and_start)

    def observation() -> bool:
        game = holder["game"]
        getter = getattr(game, "get_observation", None)
        if not callable(getter):
            getter = getattr(game, "get_snapshot", None)
        if not callable(getter):
            return True
        value = getter()
        jsonable(value)
        return value is not None

    run_check(report, "observation_serializable", observation)

    def legal_action() -> bool:
        game = holder["game"]
        legal_getter = getattr(game, "get_legal_actions", None)
        legal = legal_getter() if callable(legal_getter) else None
        holder["legal"] = legal
        if callable(legal_getter) and legal == []:
            # A valid initial state can have no legal move (for example a
            # finished puzzle).  Still allow named APIs to explain why.
            return True
        result, method_name = invoke_first_available_action(game, str(getattr(game, "game_id", "")), legal)
        holder["action_method"] = method_name
        if method_name == "none":
            # Real-time modules expose frame input rather than turn actions.
            return callable(getattr(game, "fixed_update", None)) or callable(getattr(game, "handle_input", None))
        holder["action_result"] = result
        return result is not None and result_ok(result)

    run_check(report, "legal_action", legal_action)

    def illegal_action() -> bool:
        game = holder["game"]
        method_name = str(holder.get("action_method", "none"))
        if method_name == "none":
            return True
        result = invoke_invalid_action(game, str(getattr(game, "game_id", "")), method_name)
        if result is None:
            return True  # named API has no conservative invalid form
        # A rejected invalid move is ideal; a finished game may return a
        # finished error too.  The important property is no exception/state
        # corruption, which this runner cannot infer from every custom engine.
        return result is not None

    run_check(report, "illegal_action_does_not_crash", illegal_action)

    def save_round_trip() -> bool:
        game = holder["game"]
        save = getattr(game, "save_state", None)
        load = getattr(game, "load_state", None)
        if not callable(save) or not callable(load):
            return False if catalogue_entry.get("save_required") else True
        state = save()
        if not isinstance(state, dict):
            return False
        # Do not use the bounded observation serializer here: truncating a
        # 15x15 board would manufacture a false save failure.
        payload = json.loads(json.dumps(jsonable_full(state), ensure_ascii=False))
        load(payload)
        return True

    run_check(report, "save_round_trip", save_round_trip)

    def pause_resume() -> bool:
        game = holder["game"]
        pause, resume = getattr(game, "pause", None), getattr(game, "resume", None)
        if callable(pause):
            pause()
        if callable(resume):
            resume()
        return True

    run_check(report, "pause_resume", pause_resume)

    game = holder.get("game")
    if game is not None and callable(getattr(game, "dispose", None)):
        run_check(report, "dispose", lambda: (game.dispose() is None or True))

    if report.passed:
        report.implementation_status = "已实现"
        report.automatic_status = "已自动测试"
    else:
        report.implementation_status = "失败" if report.catalogue_status in PLAYABLE_STATES else "待验证"
        report.automatic_status = "失败"
        report.error = "; ".join(f"{c.name}: {c.detail}" for c in report.checks if not c.passed)
    return report


def make_missing_report(entry: dict[str, Any]) -> GameReport:
    game_id = str(entry.get("id", "unknown"))
    status = str(entry.get("status", "unknown"))
    implemented = "失败" if status in PLAYABLE_STATES else "待验证"
    return GameReport(
        game_id=game_id,
        title=str(entry.get("title_zh", entry.get("title", game_id))),
        catalogue_status=status,
        implementation_status=implemented,
        automatic_status="失败" if implemented == "失败" else "待验证",
        checks=[Check("module_discovery", False, "No headless Python rule module discovered")],
        error="No headless Python rule module discovered",
    )


def run_unittest_discovery(project_root: Path) -> dict[str, Any]:
    """Run repository unittest files when present, without requiring pytest."""
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return {"status": "待验证", "returncode": None, "output": "tests directory missing"}
    command = [sys.executable, "-m", "unittest", "discover", "-s", str(tests_dir), "-p", "test_*.py"]
    # The project directory is itself the ``playatlas_core`` package.  When
    # this runner is invoked from inside that directory, unittest imports
    # ``tests`` as a top-level package and test modules cannot resolve
    # ``playatlas_core.games``.  Put both the project parent and project root
    # on PYTHONPATH and run from the parent so the package identity is stable.
    env = os.environ.copy()
    python_path = [str(project_root.parent), str(project_root)]
    if env.get("PYTHONPATH"):
        python_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    try:
        completed = subprocess.run(command, cwd=project_root.parent, env=env, text=True, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"status": "失败", "returncode": None, "output": "unittest discovery timed out after 120 seconds"}
    output = (completed.stdout + "\n" + completed.stderr).strip()
    if completed.returncode == 0:
        status = "已自动测试"
    elif completed.returncode == 5 and "NO TESTS RAN" in output:
        status = "待验证"
    else:
        status = "失败"
    return {"status": status, "returncode": completed.returncode, "output": output[-12000:]}


def run_pytest_discovery(project_root: Path) -> dict[str, Any]:
    """Run pytest when available so function-style rule tests are included.

    The project remains runnable without pytest; in that case the result is
    explicitly ``待验证`` instead of being reported as a pass.
    """
    tests_dir = project_root / "tests"
    if not tests_dir.is_dir():
        return {"status": "待验证", "returncode": None, "output": "tests directory missing"}
    try:
        import pytest  # type: ignore
    except ImportError:
        return {"status": "待验证", "returncode": None, "output": "pytest is not installed"}
    env = os.environ.copy()
    python_path = [str(project_root.parent), str(project_root)]
    if env.get("PYTHONPATH"):
        python_path.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    command = [sys.executable, "-m", "pytest", "-q", str(tests_dir)]
    try:
        completed = subprocess.run(command, cwd=project_root.parent, env=env, text=True, capture_output=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"status": "失败", "returncode": None, "output": "pytest timed out after 120 seconds"}
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return {"status": "已自动测试" if completed.returncode == 0 else "失败", "returncode": completed.returncode, "output": output[-12000:]}


def inspect_visual_evidence(project_root: Path) -> dict[str, Any]:
    """Inventory screenshot-like files without treating them as acceptance."""
    roots = [
        project_root / "screenshots",
        project_root / "reports" / "screenshots",
        project_root / "artifacts" / "screenshots",
        project_root / "reports" / "visual",
    ]
    found: list[str] = []
    for root in roots:
        if root.is_dir():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}:
                    found.append(str(path.relative_to(project_root)))
    return {
        "status": "待验证",
        "files_found": found,
        "count": len(found),
        "notes": [
            "File presence alone is not evidence of a real interactive run.",
            "Automated preview artwork is inventoried separately and is not a runtime/manual screenshot.",
            "No visual/manual acceptance is marked by the headless runner.",
        ],
    }


def build_report(project_root: Path) -> dict[str, Any]:
    catalogue = read_catalogue(project_root)
    package = import_game_package(project_root)
    classes = discover_game_classes(package)
    reports: list[GameReport] = []
    if catalogue:
        for entry in catalogue:
            game_id = str(entry.get("id"))
            cls = classes.get(game_id)
            reports.append(exercise_game(game_id, cls, entry) if cls else make_missing_report(entry))
    else:
        for game_id, cls in sorted(classes.items()):
            reports.append(exercise_game(game_id, cls, {"id": game_id, "status": "unknown"}))
    unittest_report = run_unittest_discovery(project_root)
    pytest_report = run_pytest_discovery(project_root)
    visual_evidence = inspect_visual_evidence(project_root)
    counts: dict[str, int] = {status: 0 for status in sorted(ALLOWED_STATUS)}
    for report in reports:
        counts[report.implementation_status] = counts.get(report.implementation_status, 0) + 1
    return {
        "schema_version": 1,
        "generated_at": utc_now(),
        "project": "PlayAtlas",
        "project_root": str(project_root.resolve()),
        "execution": {
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "godot_detected": bool(__import__("shutil").which("godot") or __import__("shutil").which("godot4")),
            "scope": "headless_rule_layer_only",
            "limitations": [
                "No Windows desktop interaction was performed in this environment.",
                "No Android APK build or device/touch verification was performed in this environment.",
                "No visual, audio, performance, controller, or LAN acceptance is implied by this report.",
            ],
        },
        "catalogue_count": len(catalogue),
        "discovered_rule_modules": sorted(classes),
        "counts_by_implementation_status": counts,
        "games": [
            {
                **asdict(report),
                "checks": [asdict(check) for check in report.checks],
            }
            for report in reports
        ],
        "unittest": unittest_report,
        "pytest": pytest_report,
        "visual_evidence": visual_evidence,
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# PlayAtlas 自动化 QA 报告",
        "",
        f"生成时间（UTC）：{report['generated_at']}",
        "",
        "> 范围：无图形界面的 Python 规则层检查。该报告不等同于 Windows、安卓、触屏、音频、视觉或人工验收。",
        "",
        f"目录条目：{report['catalogue_count']}；发现规则模块：{len(report['discovered_rule_modules'])}",
        "",
        "## 状态统计",
        "",
        "| 状态 | 数量 |",
        "|---|---:|",
    ]
    for status, count in report["counts_by_implementation_status"].items():
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## 游戏检查", "", "| 游戏 | 目录状态 | 实现状态 | 自动化状态 | 失败项 |", "|---|---|---|---|---|"])
    for game in report["games"]:
        failures = ", ".join(check["name"] for check in game["checks"] if not check["passed"]) or "—"
        lines.append(f"| {game['title']} ({game['game_id']}) | {game['catalogue_status']} | {game['implementation_status']} | {game['automatic_status']} | {failures} |")
    lines.extend([
        "",
        "## Unittest",
        "",
        f"状态：{report['unittest']['status']}；返回码：{report['unittest']['returncode']}",
        "",
        "```text",
        report["unittest"].get("output", ""),
        "```",
        "",
        "## Pytest",
        "",
        f"状态：{report['pytest']['status']}；返回码：{report['pytest']['returncode']}",
        "",
        "```text",
        report["pytest"].get("output", ""),
        "```",
        "",
        "## 视觉/真实运行证据",
        "",
        f"状态：{report['visual_evidence']['status']}；发现文件：{report['visual_evidence']['count']}",
        "",
    ])
    lines.extend(f"- {note}" for note in report["visual_evidence"]["notes"])
    if report["visual_evidence"]["files_found"]:
        lines.append("")
        lines.extend(f"- `{path}`" for path in report["visual_evidence"]["files_found"])
    lines.extend([
        "",
        "## 环境限制",
        "",
    ])
    lines.extend(f"- {item}" for item in report["execution"]["limitations"])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--out", type=Path, default=None, help="report directory (default: project/reports/qa)")
    args = parser.parse_args(argv)
    project_root = args.project_root.resolve()
    out_dir = (args.out or project_root / "reports" / "qa").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(project_root)
    (out_dir / "qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "qa_report.md").write_text(markdown_report(report), encoding="utf-8")
    # A short environment record makes later Windows/Android verification
    # additive and auditable rather than replacing the original evidence.
    environment = {
        "generated_at": report["generated_at"],
        "host_os": platform.platform(),
        "python": sys.version,
        "godot_detected": report["execution"]["godot_detected"],
        "windows_started": False,
        "windows_interaction_tested": False,
        "android_exported": False,
        "android_device_tested": False,
        "visual_evidence": report["visual_evidence"],
        "notes": report["execution"]["limitations"],
    }
    (out_dir / "environment.json").write_text(json.dumps(environment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"QA report: {out_dir / 'qa_report.md'}")
    print(f"JSON report: {out_dir / 'qa_report.json'}")
    return 1 if any(game["automatic_status"] == "失败" for game in report["games"]) or report["unittest"]["status"] == "失败" or report["pytest"]["status"] == "失败" else 0


if __name__ == "__main__":
    raise SystemExit(main())
