class_name GameModule
extends RefCounted

## Contract shared by every PlayAtlas game.
## Rule code should live in a module, not in a UI scene. Modules are safe to
## create in a headless test and can be hosted by either the desktop or mobile
## presentation layer.

signal state_changed(snapshot: Dictionary)
signal result_ready(result: Dictionary)
signal error_raised(code: String, message: String)

var context: GameContext
var manifest: Dictionary = {}
var _started := false
var _paused := false
var _disposed := false

func initialize(module_context: GameContext, game_manifest: Dictionary = {}) -> void:
	context = module_context
	manifest = game_manifest.duplicate(true)
	_disposed = false
	_started = false
	_paused = false

func start(config: Dictionary = {}) -> void:
	if _disposed:
		error_raised.emit("disposed", "Cannot start a disposed game module.")
		return
	_started = true
	_paused = false

func pause() -> void:
	if _started and not _disposed:
		_paused = true

func resume() -> void:
	if _started and not _disposed:
		_paused = false

func restart(config: Dictionary = {}) -> void:
	if _disposed:
		return
	_started = false
	_paused = false
	start(config)

func save_state() -> Dictionary:
	return {
		"game_id": str(manifest.get("id", "unknown")),
		"game_version": str(manifest.get("version", "0.0.0")),
		"ruleset_id": str(manifest.get("ruleset_id", "default")),
		"ruleset_version": str(manifest.get("ruleset_version", "1.0")),
		"save_schema_version": 1,
		"started": _started,
		"paused": _paused,
	}

func load_state(data: Dictionary) -> bool:
	if _disposed:
		return false
	_started = bool(data.get("started", false))
	_paused = bool(data.get("paused", false))
	return true

func get_result() -> Dictionary:
	return {"status": "in_progress" if _started else "not_started"}

func get_metadata() -> Dictionary:
	return manifest.duplicate(true)

func dispose() -> void:
	if _disposed:
		return
	_disposed = true
	_started = false
	_paused = false
	context = null

## Turn-based modules override these methods.
func get_current_player() -> String:
	return ""

func get_observation(_player_id: String = "") -> Dictionary:
	return {}

func get_legal_actions(_player_id: String = "") -> Array[Dictionary]:
	return []

func apply_action(_action: Dictionary) -> Dictionary:
	error_raised.emit("not_implemented", "This module does not expose turn-based actions.")
	return {"ok": false, "error": "not_implemented"}

## Real-time modules override these methods.
func handle_input(_input_frame: Dictionary) -> void:
	pass

func fixed_update(_delta: float) -> void:
	pass

func get_snapshot() -> Dictionary:
	return save_state()

func restore_snapshot(snapshot: Dictionary) -> bool:
	return load_state(snapshot)

func emit_state() -> void:
	state_changed.emit(get_snapshot())

func finish(result: Dictionary) -> void:
	_started = false
	result_ready.emit(result.duplicate(true))
