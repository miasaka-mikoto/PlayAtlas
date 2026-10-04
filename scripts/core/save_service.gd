extends Node

## Versioned local save service. Game modules provide the `state` dictionary;
## this service adds integrity metadata and keeps a backup before replacement.

signal save_succeeded(game_id: String, path: String)
signal save_failed(game_id: String, message: String)

const SAVE_ROOT := "user://saves"
const SAVE_SCHEMA_VERSION := 1

func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(SAVE_ROOT))

func save_game(game_id: String, payload: Dictionary) -> bool:
	if game_id.strip_edges().is_empty():
		save_failed.emit(game_id, "Missing game id")
		return false
	var now := Time.get_datetime_string_from_system(true)
	var document := {
		"game_id": game_id,
		"game_version": str(payload.get("game_version", "0.0.0")),
		"ruleset_id": str(payload.get("ruleset_id", "default")),
		"ruleset_version": str(payload.get("ruleset_version", "1.0")),
		"save_schema_version": int(payload.get("save_schema_version", SAVE_SCHEMA_VERSION)),
		"state": payload.get("state", payload.duplicate(true)),
		"created_at": str(payload.get("created_at", now)),
		"updated_at": now,
	}
	var path := _path_for(game_id)
	var backup := path + ".bak"
	if FileAccess.file_exists(path):
		DirAccess.copy_absolute(ProjectSettings.globalize_path(path), ProjectSettings.globalize_path(backup))
	var temp := path + ".tmp"
	var file := FileAccess.open(temp, FileAccess.WRITE)
	if file == null:
		save_failed.emit(game_id, "Unable to open temporary save")
		return false
	file.store_string(JSON.stringify(document, "\t"))
	file.flush()
	file.close()
	var error := DirAccess.rename_absolute(ProjectSettings.globalize_path(temp), ProjectSettings.globalize_path(path))
	if error != OK:
		save_failed.emit(game_id, "Unable to replace save file: %s" % error)
		return false
	save_succeeded.emit(game_id, path)
	return true

func load_game(game_id: String) -> Dictionary:
	var path := _path_for(game_id)
	var document := _read_json(path)
	if document.is_empty() and FileAccess.file_exists(path + ".bak"):
		document = _read_json(path + ".bak")
	return document

func has_save(game_id: String) -> bool:
	return not load_game(game_id).is_empty()

func delete_save(game_id: String) -> bool:
	var path := _path_for(game_id)
	if not FileAccess.file_exists(path):
		return true
	return DirAccess.remove_absolute(ProjectSettings.globalize_path(path)) == OK

func list_saves() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var directory := DirAccess.open(SAVE_ROOT)
	if directory == null:
		return result
	directory.list_dir_begin()
	var name := directory.get_next()
	while not name.is_empty():
		if not directory.current_is_dir() and name.ends_with(".json"):
			var document := _read_json(SAVE_ROOT + "/" + name)
			if not document.is_empty():
				result.append(document)
		name = directory.get_next()
	directory.list_dir_end()
	return result

func _path_for(game_id: String) -> String:
	var safe_id := game_id.to_lower().replace("/", "_").replace("\\", "_").replace("..", "_")
	return SAVE_ROOT + "/" + safe_id + ".json"

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}
