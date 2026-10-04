extends Node

## Application coordinator. UI scenes communicate with this node instead of
## reaching into individual game modules or persistence files.

signal game_opened(game_id: String)
signal game_closed(game_id: String)
signal application_ready

var active_module: GameModule
var active_game_id := ""
var _initialized := false

func _ready() -> void:
	# Autoload order is not guaranteed by scene construction. Defer one frame so
	# the registry and persistence services can finish their own _ready methods.
	call_deferred("_initialize")

func _initialize() -> void:
	if _initialized:
		return
	_initialized = true
	application_ready.emit()

func open_game(game_id: String, mode := "solo", options: Dictionary = {}) -> bool:
	close_game()
	var context := GameContext.new(game_id, int(options.get("seed", Time.get_unix_time_from_system())))
	context.mode = mode
	context.player_count = int(options.get("player_count", 1))
	context.options = options.duplicate(true)
	context.services = {
		"save": SaveService,
		"settings": SettingsService,
		"statistics": StatisticsService,
		"input": InputService,
		"audio": AudioService,
		"tutorial": TutorialService,
	}
	active_module = GameRegistry.instantiate(game_id, context)
	if active_module == null:
		return false
	active_game_id = game_id
	active_module.start(options)
	StatisticsService.record_started(game_id)
	game_opened.emit(game_id)
	return true

func close_game() -> void:
	if active_module == null:
		return
	var closed_id := active_game_id
	active_module.dispose()
	active_module = null
	active_game_id = ""
	game_closed.emit(closed_id)

func pause_game() -> void:
	if active_module != null:
		active_module.pause()

func resume_game() -> void:
	if active_module != null:
		active_module.resume()

func save_active_game() -> bool:
	if active_module == null or active_game_id.is_empty():
		return false
	var state := active_module.save_state()
	return SaveService.save_game(active_game_id, state)

func load_saved_game(game_id: String) -> bool:
	var document := SaveService.load_game(game_id)
	if document.is_empty():
		return false
	if not open_game(game_id, "resume", document.get("state", {})):
		return false
	return active_module.load_state(document.get("state", {}))
