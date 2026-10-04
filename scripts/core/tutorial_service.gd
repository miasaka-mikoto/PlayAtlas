extends Node

signal tutorial_progress_changed(game_id: String, step: int, completed: bool)

const PROGRESS_PATH := "user://tutorial_progress.json"
var progress: Dictionary = {}

func _ready() -> void:
	_load()

func get_progress(game_id: String) -> Dictionary:
	return progress.get(game_id, {"step": 0, "completed": false}).duplicate(true)

func set_step(game_id: String, step: int, total_steps: int) -> void:
	var completed := step >= total_steps
	progress[game_id] = {"step": step, "completed": completed}
	_save()
	tutorial_progress_changed.emit(game_id, step, completed)

func reset(game_id: String) -> void:
	progress.erase(game_id)
	_save()
	tutorial_progress_changed.emit(game_id, 0, false)

func _load() -> void:
	if not FileAccess.file_exists(PROGRESS_PATH):
		return
	var file := FileAccess.open(PROGRESS_PATH, FileAccess.READ)
	if file == null:
		return
	var parsed = JSON.parse_string(file.get_as_text())
	if typeof(parsed) == TYPE_DICTIONARY:
		progress = parsed

func _save() -> void:
	var file := FileAccess.open(PROGRESS_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(progress, "\t"))
		file.flush()
		file.close()
