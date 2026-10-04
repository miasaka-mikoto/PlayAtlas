extends Node

## Central catalogue. It stores metadata and module factories, but never owns
## game scene nodes. This keeps loading cheap and lets the hall lazy-load only
## the selected game.

signal catalogue_changed

const CATALOG_PATH := "res://data/games/GAME_CATALOG.json"
const PARTY_CATALOG_PATH := "res://data/games/PARTY_CATALOG.json"
var _games: Dictionary = {}
var _factories: Dictionary = {}
var _loaded := false

func _ready() -> void:
	load_catalogue()

func load_catalogue(path: String = CATALOG_PATH) -> bool:
	_games.clear()
	_loaded = false
	if not FileAccess.file_exists(path):
		return false
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return false
	var parsed = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	var entries = parsed.get("games", [])
	if typeof(entries) != TYPE_ARRAY:
		return false
	for entry in entries:
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var game_id := str(entry.get("id", "")).strip_edges()
		if game_id.is_empty():
			continue
		_games[game_id] = entry.duplicate(true)
	_loaded = true
	catalogue_changed.emit()
	return true

func load_expansion_catalogue(path: String = PARTY_CATALOG_PATH) -> bool:
	## Expansion packs are opt-in so the hall does not claim the launch-36
	## count has changed.  PackageManager should call this only after validating
	## a trusted local manifest/checksum.
	if not FileAccess.file_exists(path):
		return false
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return false
	var parsed = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY or typeof(parsed.get("games", [])) != TYPE_ARRAY:
		return false
	for entry in parsed.get("games", []):
		if typeof(entry) != TYPE_DICTIONARY:
			continue
		var game_id := str(entry.get("id", "")).strip_edges()
		if game_id.is_empty():
			continue
		var copy := entry.duplicate(true)
		copy["catalogue_scope"] = str(parsed.get("catalogue_version", "expansion"))
		copy["installed_from"] = path
		_games[game_id] = copy
	_loaded = true
	catalogue_changed.emit()
	return true

func is_loaded() -> bool:
	return _loaded

func register_module(game_id: String, factory: Callable) -> void:
	if game_id.strip_edges().is_empty() or not factory.is_valid():
		return
	_factories[game_id] = factory

func unregister_module(game_id: String) -> void:
	_factories.erase(game_id)

func get_all_games() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for value in _games.values():
		result.append(value.duplicate(true))
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a.get("title", a.get("title_zh", ""))) < str(b.get("title", b.get("title_zh", "")))
	)
	return result

func get_game(game_id: String) -> Dictionary:
	return _games.get(game_id, {}).duplicate(true)

func has_game(game_id: String) -> bool:
	return _games.has(game_id)

func instantiate(game_id: String, context: GameContext = null) -> GameModule:
	if not _factories.has(game_id):
		return null
	var factory: Callable = _factories[game_id]
	var module = factory.call()
	if module is not GameModule:
		return null
	if context == null:
		context = GameContext.new(game_id)
	module.initialize(context, get_game(game_id))
	return module

func get_featured_games(limit: int = 8) -> Array[Dictionary]:
	var featured: Array[Dictionary] = []
	for game in get_all_games():
		if bool(game.get("featured", false)) or str(game.get("status", "")) == "playable":
			featured.append(game)
			if featured.size() >= limit:
				break
	return featured

func search(query: String = "", filters: Dictionary = {}) -> Array[Dictionary]:
	var normalized := query.strip_edges().to_lower()
	var result: Array[Dictionary] = []
	for game in _games.values():
		if not _matches_query(game, normalized):
			continue
		if not _matches_filters(game, filters):
			continue
		result.append(game.duplicate(true))
	return result

func get_status_summary() -> Dictionary:
	var summary := {"playable": 0, "installed": 0, "in_development": 0, "unavailable": 0, "total": _games.size()}
	for game in _games.values():
		var status := str(game.get("status", "unavailable"))
		if summary.has(status):
			summary[status] += 1
		else:
			summary["unavailable"] += 1
	return summary

func recommend_game(filters: Dictionary = {}, player_count: int = 1, input_device: String = "") -> Dictionary:
	"""Return one deterministic eligible entry for the hall's「给我一局」按钮.

	The registry never recommends a multiplayer-only entry to a solo user and
	never treats an unimplemented card as playable.  A preview entry may be
	returned only when its metadata explicitly opts into `preview_playable`.
	"""
	var candidates := search(str(filters.get("query", "")), filters.get("search_filters", {}))
	var eligible: Array[Dictionary] = []
	for game in candidates:
		var players: Dictionary = game.get("players", {})
		if int(players.get("min", 1)) > player_count or int(players.get("max", player_count)) < player_count:
			continue
		if not input_device.is_empty() and input_device not in game.get("supported_inputs", []):
			continue
		var status := str(game.get("status", "unavailable"))
		if status not in ["playable", "installed"] and not bool(game.get("preview_playable", false)):
			continue
		eligible.append(game)
	if eligible.is_empty():
		return {}
	eligible.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return str(a.get("id", "")) < str(b.get("id", ""))
	)
	return eligible[0].duplicate(true)

func _matches_query(game: Dictionary, normalized: String) -> bool:
	if normalized.is_empty():
		return true
	for key in ["title", "title_zh", "english_name", "local_name", "id"]:
		if normalized in str(game.get(key, "")).to_lower():
			return true
	for alias in game.get("aliases", []):
		if normalized in str(alias).to_lower():
			return true
	return false

func _matches_filters(game: Dictionary, filters: Dictionary) -> bool:
	for key in filters.keys():
		var expected = filters[key]
		if expected == null or str(expected).is_empty():
			continue
		var actual = game.get(key)
		if typeof(actual) == TYPE_ARRAY:
			if expected is Array:
				var found := false
				for candidate in expected:
					if candidate in actual:
						found = true
						break
				if not found:
					return false
			elif expected not in actual:
				return false
		elif actual != expected:
			return false
	return true
