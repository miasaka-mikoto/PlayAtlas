"""Small host-authoritative LAN protocol for PlayAtlas party games.

The transport is deliberately boring: newline-delimited UTF-8 JSON over TCP.
The host owns the rule engine and sends each client only that client's
``get_observation(player_id)``.  This makes hidden hands a protocol property,
not a UI convention.  A future Godot presentation can use the same message
shapes over ENet; the Python adapter is useful for deterministic CI and for a
LAN smoke host on machines without Godot installed.

Protocol highlights
-------------------
* protocol version 1, maximum message 256 KiB;
* hello → welcome → lobby/ready → started → snapshot/action_result;
* client sequence numbers are monotonic and duplicate request ids are
  replayed, so retries cannot apply an action twice;
* only the host calls the rule engine and broadcasts canonical snapshots;
* reconnecting with the same ``client_id`` restores the same player slot when
  it is still available;
* no discovery server, internet account, or fake online population exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import json
import queue
import socket
import threading
import time
import uuid
from typing import Any, Callable, Optional


PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 256 * 1024
DEFAULT_HOST = "0.0.0.0"


class LanProtocolError(ValueError):
    """Raised for malformed or unsafe protocol messages."""


def _encode(message: dict[str, Any]) -> bytes:
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise LanProtocolError("message must contain a string type")
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
    if len(payload) > MAX_MESSAGE_BYTES:
        raise LanProtocolError("message_too_large")
    return payload


def _decode(line: bytes) -> dict[str, Any]:
    if len(line) > MAX_MESSAGE_BYTES:
        raise LanProtocolError("message_too_large")
    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LanProtocolError("invalid_json") from exc
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise LanProtocolError("invalid_message")
    protocol = message.get("protocol", PROTOCOL_VERSION)
    if protocol != PROTOCOL_VERSION:
        raise LanProtocolError("unsupported_protocol")
    return message


def _result_dict(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return {"ok": bool(result.get("ok", True)), **result}
    return {
        "ok": bool(getattr(result, "ok", result is None)),
        "reason": str(getattr(result, "reason", "")),
        "outcome": getattr(result, "outcome", None),
        "payload": getattr(result, "payload", None),
    }


def create_lan_game(game_id: str, players: int = 2, seed: int = 0) -> Any:
    """Create a supported game without importing presentation code."""

    mapping = {
        "gomoku": ("PlayAtlas.games", "GomokuGame"),
        "reversi": ("PlayAtlas.games", "ReversiGame"),
        "crazy_eights": ("PlayAtlas.games", "CrazyEightsGame"),
        "tank_battle": ("PlayAtlas.games", "TankBattleGame"),
        "uno": ("PlayAtlas.games", "UnoGame"),
        "upgrade_poker": ("PlayAtlas.games", "UpgradePokerGame"),
        "blackjack": ("PlayAtlas.games", "BlackjackGame"),
    }
    if game_id not in mapping:
        raise ValueError(f"LAN game is not configured: {game_id}")
    module_name, class_name = mapping[game_id]
    try:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise ValueError(f"LAN game module unavailable: {game_id}") from exc
    if game_id == "gomoku":
        return cls()
    if game_id == "reversi":
        return cls()
    if game_id == "crazy_eights":
        return cls(players=players, seed=seed)
    return cls(players=players, seed=seed)


@dataclass
class _Session:
    sock: socket.socket
    address: tuple[Any, ...]
    client_id: str = ""
    player_id: Optional[int] = None
    name: str = "玩家"
    ready: bool = False
    connected: bool = True
    last_client_seq: int = 0
    requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    send_lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, message: dict[str, Any]) -> None:
        payload = _encode(message)
        with self.send_lock:
            self.sock.sendall(payload)


class LanHost:
    """Host a single authoritative room on a local TCP port."""

    def __init__(
        self,
        game: Any | None = None,
        *,
        game_id: str | None = None,
        players: int = 2,
        seed: int = 0,
        bind_host: str = DEFAULT_HOST,
        port: int = 0,
        room_name: str = "PlayAtlas 聚会房间",
        max_message_bytes: int = MAX_MESSAGE_BYTES,
    ) -> None:
        self.game = game if game is not None else create_lan_game(str(game_id), players=players, seed=seed)
        self.game_id = str(game_id or getattr(self.game, "game_id", "unknown"))
        if not bool(getattr(self.game, "supports_lan", True)):
            raise ValueError(f"game does not support LAN: {self.game_id}")
        self.max_players = int(getattr(self.game, "max_players", players))
        self.min_players = int(getattr(self.game, "min_players", 2))
        self.room_name = str(room_name)
        self.bind_host, self.requested_port = bind_host, int(port)
        self.max_message_bytes = int(max_message_bytes)
        self.host_id = "host"
        self.phase = "lobby"
        self._listener: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._client_threads: set[threading.Thread] = set()
        self._sessions: dict[socket.socket, _Session] = {}
        self._by_client: dict[str, _Session] = {}
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._server_seq = 0
        self._next_player = 1  # player 0 is reserved for the host authority
        self._started_at: Optional[float] = None

    @property
    def address(self) -> tuple[str, int]:
        if self._listener is None:
            return (self.bind_host, self.requested_port)
        host, port = self._listener.getsockname()[:2]
        return (str(host), int(port))

    @property
    def port(self) -> int:
        return self.address[1]

    @property
    def players(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"player_id": int(s.player_id), "name": s.name, "ready": s.ready, "connected": s.connected}
                    for s in sorted(self._sessions.values(), key=lambda item: item.player_id or 999)
                    if s.player_id is not None]

    def start(self) -> tuple[str, int]:
        if self._listener is not None:
            return self.address
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((self.bind_host, self.requested_port)); listener.listen(self.max_players + 4); listener.settimeout(0.25)
        self._listener = listener
        self._accept_thread = threading.Thread(target=self._accept_loop, name="PlayAtlas-LAN-host", daemon=True)
        self._accept_thread.start()
        return self.address

    def _accept_loop(self) -> None:
        assert self._listener is not None
        while not self._stop.is_set():
            try:
                sock, address = self._listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            sock.settimeout(0.5)
            session = _Session(sock=sock, address=address)
            with self._lock:
                self._sessions[sock] = session
            thread = threading.Thread(target=self._client_loop, args=(session,), name="PlayAtlas-LAN-client", daemon=True)
            self._client_threads.add(thread); thread.start()

    def _client_loop(self, session: _Session) -> None:
        buffer = b""
        try:
            while not self._stop.is_set() and session.connected:
                try:
                    chunk = session.sock.recv(8192)
                except socket.timeout:
                    continue
                if not chunk:
                    break
                buffer += chunk
                if len(buffer) > self.max_message_bytes * 2:
                    raise LanProtocolError("buffer_too_large")
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    if not raw:
                        continue
                    try:
                        message = _decode(raw)
                        self._handle(session, message)
                    except LanProtocolError as exc:
                        self._send_error(session, "protocol_error", str(exc))
        except (OSError, ConnectionError):
            pass
        finally:
            self._disconnect(session)

    def _disconnect(self, session: _Session) -> None:
        with self._lock:
            session.connected = False
            self._sessions.pop(session.sock, None)
            if session.client_id and self._by_client.get(session.client_id) is session:
                # Keep the identity for a short-lived reconnect.  The session
                # remains in _by_client but is marked disconnected.
                self._by_client[session.client_id] = session
        try:
            session.sock.close()
        except OSError:
            pass
        if session.client_id:
            self._broadcast_lobby()

    def _send(self, session: _Session, message: dict[str, Any]) -> bool:
        if not session.connected:
            return False
        try:
            session.send({"protocol": PROTOCOL_VERSION, "server_seq": self._next_seq(), **message})
            return True
        except (OSError, ConnectionError, LanProtocolError):
            self._disconnect(session)
            return False

    def _next_seq(self) -> int:
        with self._lock:
            self._server_seq += 1
            return self._server_seq

    def _send_error(self, session: _Session, code: str, message: str, request_id: str | None = None) -> None:
        response = {"type": "error", "code": code, "message": message}
        if request_id:
            response["request_id"] = request_id
        self._send(session, response)

    def _handle(self, session: _Session, message: dict[str, Any]) -> None:
        kind = message["type"]
        if not session.client_id and kind != "hello":
            self._send_error(session, "hello_required", "先发送 hello")
            return
        if kind == "hello":
            self._hello(session, message); return
        if kind == "ready":
            self._ready(session, bool(message.get("ready", True))); return
        if kind == "action":
            self._action(session, message); return
        if kind == "ping":
            self._send(session, {"type": "pong", "client_time": message.get("client_time")}); return
        if kind == "leave":
            self._disconnect(session); return
        if kind == "start":
            self._send_error(session, "host_only", "只有主机可以开始房间")
            return
        self._send_error(session, "unknown_message", kind)

    def _hello(self, session: _Session, message: dict[str, Any]) -> None:
        client_id = str(message.get("client_id") or uuid.uuid4().hex)
        name = str(message.get("player_name") or "玩家")[:32]
        with self._lock:
            previous = self._by_client.get(client_id)
            if previous is not None and previous is not session and not previous.connected:
                session.player_id, session.ready = previous.player_id, previous.ready
            else:
                occupied = {s.player_id for s in self._sessions.values() if s.player_id is not None}
                free = next((pid for pid in range(1, self.max_players) if pid not in occupied), None)
                if free is None:
                    self._send_error(session, "room_full", "房间已满")
                    return
                session.player_id = free; session.ready = False
            session.client_id, session.name, session.connected = client_id, name, True
            self._by_client[client_id] = session
        self._send(session, {"type": "welcome", "client_id": client_id, "player_id": session.player_id,
                             "host_id": self.host_id, "game_id": self.game_id,
                             "ruleset_id": getattr(self.game, "ruleset_id", ""),
                             "phase": self.phase, "room_name": self.room_name, "players": self.players})
        self._broadcast_lobby()
        if self.phase == "playing":
            self._send_snapshot(session)

    def _ready(self, session: _Session, ready: bool) -> None:
        session.ready = bool(ready)
        self._broadcast_lobby()

    def _broadcast_lobby(self) -> None:
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.connected and s.client_id]
            payload = {"type": "lobby", "phase": self.phase, "room_name": self.room_name,
                       "game_id": self.game_id, "players": self.players}
        for session in sessions:
            self._send(session, payload)

    def can_start(self) -> bool:
        with self._lock:
            connected = [s for s in self._sessions.values() if s.connected and s.client_id]
            # The host is the authority and is considered ready.  All joined
            # clients must explicitly be ready before a start.
            return self.min_players <= len(connected) + 1 <= self.max_players and all(s.ready for s in connected)

    def start_game(self) -> dict[str, Any]:
        if self.phase != "lobby":
            raise RuntimeError("room_already_started")
        if not self.can_start():
            raise RuntimeError("players_not_ready")
        starter = getattr(self.game, "start", None)
        if callable(starter):
            starter({"players": len(self.players) + 1})
        self.phase = "playing"; self._started_at = time.time()
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.connected and s.client_id]
        for session in sessions:
            self._send(session, {"type": "started", "game_id": self.game_id, "phase": self.phase})
            self._send_snapshot(session)
        return {"phase": self.phase, "players": len(sessions) + 1}

    def _invoke_game(self, action: Any, player_id: int) -> Any:
        method = getattr(self.game, "apply_action", None)
        if not callable(method):
            method = getattr(self.game, "handle_input", None)
        if callable(method):
            try:
                return method(action, player_id=player_id)
            except TypeError:
                # Older two-player engines do not accept player_id; only use
                # this fallback for public-information games.
                return method(action)
        # Crazy Eights is one of the older compact modules and exposes named
        # `play`/`draw` methods rather than the common apply_action contract.
        if isinstance(action, dict) and str(action.get("type", "")) == "play" and callable(getattr(self.game, "play", None)):
            card = action.get("card")
            return self.game.play(tuple(card) if isinstance(card, list) else card)
        if isinstance(action, dict) and str(action.get("type", "")) == "draw" and callable(getattr(self.game, "draw", None)):
            return self.game.draw()
        raise RuntimeError("game_has_no_action_api")

    def _action(self, session: _Session, message: dict[str, Any]) -> None:
        request_id = str(message.get("request_id") or uuid.uuid4().hex)
        client_seq = message.get("client_seq")
        try:
            client_seq = int(client_seq)
        except (TypeError, ValueError):
            self._send_error(session, "invalid_client_seq", "client_seq 必须是整数", request_id); return
        # A retry with the same request id is idempotent even if its transport
        # wrapper accidentally assigned a new client sequence.
        cached_request = session.requests.get(request_id)
        if cached_request is not None:
            self._send(session, cached_request)
            return
        if client_seq <= session.last_client_seq:
            self._send_error(session, "duplicate_action", "已处理过的 client_seq", request_id)
            return
        if self.phase != "playing":
            self._send_error(session, "not_started", "房间尚未开始", request_id); return
        if session.player_id is None:
            self._send_error(session, "not_joined", "尚未加入房间", request_id); return
        action = message.get("action")
        if isinstance(action, dict) and "player_id" in action and int(action["player_id"]) != session.player_id:
            self._send_error(session, "player_spoofing", "动作中的 player_id 与房间身份不一致", request_id); return
        session.last_client_seq = client_seq
        try:
            result = _result_dict(self._invoke_game(action, int(session.player_id)))
        except (TypeError, ValueError, RuntimeError, IndexError) as exc:
            result = {"ok": False, "reason": "invalid_action", "message": str(exc)}
        response = {"type": "action_result", "request_id": request_id, "player_id": session.player_id, **result}
        session.requests[request_id] = response
        # Bound the retry cache to avoid unbounded memory growth.
        if len(session.requests) > 128:
            del session.requests[next(iter(session.requests))]
        self._send(session, response)
        if result.get("ok"):
            self._broadcast_snapshots(result)

    def _observation(self, player_id: int) -> dict[str, Any]:
        method = getattr(self.game, "get_observation", None)
        if callable(method):
            observation = method(player_id)
        else:
            method = getattr(self.game, "observation", None)
            if callable(method):
                observation = method(player_id)
            else:
                method = getattr(self.game, "get_snapshot", None)
                observation = method() if callable(method) else {"game_id": self.game_id}
        if not isinstance(observation, dict):
            raise RuntimeError("observation_must_be_object")
        return observation

    def _send_snapshot(self, session: _Session, result: Optional[dict[str, Any]] = None) -> None:
        if session.player_id is None:
            return
        payload = {"type": "snapshot", "game_id": self.game_id, "phase": self.phase,
                   "player_id": session.player_id, "observation": self._observation(session.player_id)}
        if result is not None:
            payload["last_action"] = result
        self._send(session, payload)

    def _broadcast_snapshots(self, result: dict[str, Any]) -> None:
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.connected and s.client_id]
        for session in sessions:
            self._send_snapshot(session, result)

    def submit_local_action(self, player_id: int, action: Any) -> dict[str, Any]:
        """Apply a host/local-player action and broadcast it to clients."""
        if self.phase != "playing":
            return {"ok": False, "reason": "not_started"}
        try:
            result = _result_dict(self._invoke_game(action, int(player_id)))
        except (TypeError, ValueError, RuntimeError, IndexError) as exc:
            result = {"ok": False, "reason": "invalid_action", "message": str(exc)}
        if result.get("ok"):
            self._broadcast_snapshots(result)
        return result

    def stop(self) -> None:
        self._stop.set()
        listener, self._listener = self._listener, None
        if listener is not None:
            try: listener.close()
            except OSError: pass
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.connected = False
            try: session.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: session.sock.close()
            except OSError: pass
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1.0)
        self._accept_thread = None

    close = stop


class LanClient:
    """Tiny client used by Godot bridges, test harnesses, or a LAN CLI."""

    def __init__(self, client_id: Optional[str] = None, player_name: str = "玩家") -> None:
        self.client_id = client_id or uuid.uuid4().hex
        self.player_name = str(player_name)[:32]
        self.sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self._send_lock = threading.Lock()
        self._client_seq = 0
        self._connected = False
        self.player_id: Optional[int] = None
        self.last_server_seq = 0

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int, timeout: float = 3.0) -> None:
        self.close()
        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.settimeout(0.5); self.sock = sock; self._stop.clear(); self._connected = True
        self._thread = threading.Thread(target=self._receive_loop, name="PlayAtlas-LAN-recv", daemon=True)
        self._thread.start()
        self._send({"type": "hello", "protocol": PROTOCOL_VERSION, "client_id": self.client_id, "player_name": self.player_name})

    def _send(self, message: dict[str, Any]) -> None:
        if self.sock is None or not self._connected:
            raise ConnectionError("LAN client is not connected")
        payload = _encode({"protocol": PROTOCOL_VERSION, **message})
        with self._send_lock:
            self.sock.sendall(payload)

    def _receive_loop(self) -> None:
        assert self.sock is not None
        buffer = b""
        try:
            while not self._stop.is_set():
                try:
                    chunk = self.sock.recv(8192)
                except socket.timeout:
                    continue
                if not chunk: break
                buffer += chunk
                if len(buffer) > MAX_MESSAGE_BYTES * 2: raise LanProtocolError("buffer_too_large")
                while b"\n" in buffer:
                    raw, buffer = buffer.split(b"\n", 1)
                    if not raw: continue
                    message = _decode(raw)
                    if isinstance(message.get("server_seq"), int):
                        self.last_server_seq = max(self.last_server_seq, int(message["server_seq"]))
                    if message.get("type") == "welcome": self.player_id = message.get("player_id")
                    self._messages.put(message)
        except (OSError, ConnectionError, LanProtocolError):
            pass
        finally:
            self._connected = False

    def send_ready(self, ready: bool = True) -> None:
        self._send({"type": "ready", "ready": bool(ready)})

    def send_action(self, action: Any, request_id: Optional[str] = None) -> str:
        self._client_seq += 1
        request_id = request_id or uuid.uuid4().hex
        self._send({"type": "action", "client_seq": self._client_seq,
                    "request_id": request_id, "action": action})
        return request_id

    def send_ping(self) -> None:
        self._send({"type": "ping", "client_time": time.time()})

    def poll(self, timeout: float = 0.0) -> Optional[dict[str, Any]]:
        try:
            return self._messages.get(timeout=max(0.0, float(timeout)))
        except queue.Empty:
            return None

    def wait_for(self, message_type: str, timeout: float = 3.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.01, deadline - time.monotonic())
            message = self.poll(min(0.1, remaining))
            if message is not None and message.get("type") == message_type:
                return message
        raise TimeoutError(f"timed out waiting for {message_type}")

    def close(self) -> None:
        self._stop.set(); self._connected = False
        sock, self.sock = self.sock, None
        if sock is not None:
            try: sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: sock.close()
            except OSError: pass
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None

    disconnect = close


__all__ = ["LanClient", "LanHost", "LanProtocolError", "create_lan_game", "PROTOCOL_VERSION"]
