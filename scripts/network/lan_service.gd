extends Node

## Godot-side LAN adapter.
##
## The rule engine remains authoritative in the host GameModule.  Clients send
## actions with a monotonically increasing sequence; the host validates them
## and sends player-scoped observations.  Python's newline-JSON adapter in
## `network/lan.py` mirrors this contract for headless QA and a future CLI.

signal room_created(room: Dictionary)
signal room_joined(room: Dictionary)
signal peer_joined(peer_id: int)
signal peer_left(peer_id: int)
signal action_rejected(peer_id: int, code: String)
signal snapshot_received(snapshot: Dictionary)
signal network_error(code: String, message: String)

const PROTOCOL_VERSION := 1
const DEFAULT_PORT := 27800
const MAX_PLAYERS := 4

var peer: ENetMultiplayerPeer
var host_authority := false
var room: Dictionary = {}
var _last_client_sequence: Dictionary = {}
var _next_sequence := 0
var _action_validator: Callable
var _observation_provider: Callable

func _ready() -> void:
	multiplayer.peer_connected.connect(_on_peer_connected)
	multiplayer.peer_disconnected.connect(_on_peer_disconnected)
	multiplayer.connected_to_server.connect(_on_connected)
	multiplayer.connection_failed.connect(_on_connection_failed)
	multiplayer.server_disconnected.connect(_on_server_disconnected)

func set_rule_bridge(validator: Callable, observation_provider: Callable) -> void:
	## The bridge is supplied by the active GameModule, never by arbitrary
	## network input.  It should return {ok, reason, payload}.
	_action_validator = validator
	_observation_provider = observation_provider

func create_room(game_id: String, ruleset_id: String, port: int = DEFAULT_PORT, max_players: int = MAX_PLAYERS) -> bool:
	leave_room()
	peer = ENetMultiplayerPeer.new()
	var error := peer.create_server(port, clampi(max_players - 1, 1, MAX_PLAYERS - 1))
	if error != OK:
		network_error.emit("create_failed", error_string(error))
		return false
	multiplayer.multiplayer_peer = peer
	host_authority = true
	room = {
		"protocol": PROTOCOL_VERSION,
		"game_id": game_id,
		"ruleset_id": ruleset_id,
		"phase": "lobby",
		"max_players": clampi(max_players, 2, MAX_PLAYERS),
		"host_peer_id": multiplayer.get_unique_id(),
	}
	_last_client_sequence.clear()
	room_created.emit(room.duplicate(true))
	return true

func join_room(address: String, port: int = DEFAULT_PORT) -> bool:
	leave_room()
	peer = ENetMultiplayerPeer.new()
	var error := peer.create_client(address, port)
	if error != OK:
		network_error.emit("connect_failed", error_string(error))
		return false
	multiplayer.multiplayer_peer = peer
	host_authority = false
	return true

func start_room() -> bool:
	if not host_authority or room.is_empty():
		return false
	room["phase"] = "playing"
	_broadcast_snapshot()
	return true

func send_ready(ready: bool = true) -> void:
	if host_authority:
		return
	_set_ready.rpc_id(1, ready)

func send_action(action: Dictionary) -> void:
	if host_authority or room.is_empty() or str(room.get("phase", "")) != "playing":
		return
	_next_sequence += 1
	_submit_action.rpc_id(1, action.duplicate(true), _next_sequence)

func leave_room() -> void:
	if multiplayer.multiplayer_peer != null:
		multiplayer.multiplayer_peer = null
	peer = null
	host_authority = false
	room.clear()
	_last_client_sequence.clear()

@rpc("any_peer", "reliable")
func _set_ready(ready: bool) -> void:
	if not host_authority:
		return
	var sender := multiplayer.get_remote_sender_id()
	_set_lobby_state.rpc({"peer_id": sender, "ready": ready})

@rpc("any_peer", "reliable")
func _submit_action(action: Dictionary, client_sequence: int) -> void:
	if not host_authority:
		return
	var sender := multiplayer.get_remote_sender_id()
	var last := int(_last_client_sequence.get(sender, 0))
	if client_sequence <= last:
		action_rejected.emit(sender, "duplicate_action")
		return
	_last_client_sequence[sender] = client_sequence
	if _action_validator.is_valid():
		var result = _action_validator.call(sender, action)
		if typeof(result) == TYPE_DICTIONARY and not bool(result.get("ok", false)):
			action_rejected.emit(sender, str(result.get("reason", "illegal_action")))
			return
	_broadcast_snapshot()

@rpc("authority", "call_local", "reliable")
func _set_lobby_state(state: Dictionary) -> void:
	room["last_lobby_state"] = state.duplicate(true)

func _broadcast_snapshot() -> void:
	if not host_authority:
		return
	for peer_id in multiplayer.get_peers():
		_send_snapshot(peer_id)

func _send_snapshot(peer_id: int) -> void:
	var observation: Dictionary = {}
	if _observation_provider.is_valid():
		var value = _observation_provider.call(str(peer_id))
		if typeof(value) == TYPE_DICTIONARY:
			observation = value
	_next_sequence += 1
	_receive_snapshot.rpc_id(peer_id, {
		"protocol": PROTOCOL_VERSION,
		"server_sequence": _next_sequence,
		"player_id": peer_id,
		"phase": room.get("phase", "lobby"),
		"observation": observation,
	})

@rpc("authority", "reliable")
func _receive_snapshot(snapshot: Dictionary) -> void:
	## Never broadcast the host's full save state here; only this client's
	## observation is accepted by the presentation layer.
	snapshot_received.emit(snapshot.duplicate(true))

func _on_peer_connected(peer_id: int) -> void:
	peer_joined.emit(peer_id)

func _on_peer_disconnected(peer_id: int) -> void:
	_last_client_sequence.erase(peer_id)
	peer_left.emit(peer_id)

func _on_connected() -> void:
	room_joined.emit(room.duplicate(true))

func _on_connection_failed() -> void:
	network_error.emit("connection_failed", "局域网房间连接失败")

func _on_server_disconnected() -> void:
	network_error.emit("server_disconnected", "主机已断开")
