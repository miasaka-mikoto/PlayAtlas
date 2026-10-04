class_name GameContext
extends RefCounted

## Services intentionally passed to a game module so its rule layer stays
## independent from scene nodes and can be tested without rendering.

var game_id: String = ""
var seed: int = 0
var player_count: int = 1
var mode: String = "solo"
var services: Dictionary = {}
var options: Dictionary = {}

func _init(context_game_id: String = "", context_seed: int = 0) -> void:
	game_id = context_game_id
	seed = context_seed

func service(name: String) -> Variant:
	return services.get(name)

func duplicate_context() -> GameContext:
	var copy := GameContext.new(game_id, seed)
	copy.player_count = player_count
	copy.mode = mode
	copy.services = services.duplicate()
	copy.options = options.duplicate(true)
	return copy
