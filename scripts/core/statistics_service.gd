extends Node

signal statistics_changed(game_id: String, statistics: Dictionary)

const STATS_PATH := "user://statistics.json"
var values: Dictionary = {}

func _ready() -> void:
	load_statistics()

func record_started(game_id: String) -> void:
	var stats := _get_or_create(game_id)
	stats["plays"] = int(stats.get("plays", 0)) + 1
	stats["last_played_at"] = Time.get_datetime_string_from_system(true)
	_commit(game_id, stats)

func record_finished(game_id: String, result: Dictionary) -> void:
	var stats := _get_or_create(game_id)
	stats["completed"] = int(stats.get("completed", 0)) + 1
	var outcome := str(result.get("outcome", "unknown"))
	if outcome == "win":
		stats["wins"] = int(stats.get("wins", 0)) + 1
	elif outcome == "loss":
		stats["losses"] = int(stats.get("losses", 0)) + 1
	elif outcome == "draw":
		stats["draws"] = int(stats.get("draws", 0)) + 1
	if result.has("score"):
		stats["best_score"] = max(int(stats.get("best_score", 0)), int(result["score"]))
	_commit(game_id, stats)

func add_play_time(game_id: String, seconds: float) -> void:
	var stats := _get_or_create(game_id)
	stats["play_time_seconds"] = float(stats.get("play_time_seconds", 0.0)) + maxf(seconds, 0.0)
	_commit(game_id, stats)

func get_game_statistics(game_id: String) -> Dictionary:
	return _get_or_create(game_id).duplicate(true)

func all_statistics() -> Dictionary:
	return values.duplicate(true)

func load_statistics() -> bool:
	if not FileAccess.file_exists(STATS_PATH):
		return false
	var file := FileAccess.open(STATS_PATH, FileAccess.READ)
	if file == null:
		return false
	var parsed = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	values = parsed
	return true

func _get_or_create(game_id: String) -> Dictionary:
	if not values.has(game_id):
		values[game_id] = {
			"plays": 0,
			"completed": 0,
			"wins": 0,
			"losses": 0,
			"draws": 0,
			"play_time_seconds": 0.0,
			"best_score": 0,
		}
	return values[game_id]

func _commit(game_id: String, stats: Dictionary) -> void:
	values[game_id] = stats
	var file := FileAccess.open(STATS_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(values, "\t"))
		file.flush()
		file.close()
	statistics_changed.emit(game_id, stats.duplicate(true))
