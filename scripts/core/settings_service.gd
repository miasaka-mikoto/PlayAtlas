extends Node

signal settings_changed(settings: Dictionary)

const SETTINGS_PATH := "user://settings.json"
const DEFAULTS := {
	"language": "zh-CN",
	"master_volume": 1.0,
	"music_volume": 0.75,
	"sfx_volume": 0.9,
	"muted": false,
	"font_scale": 1.0,
	"high_contrast": false,
	"reduce_motion": false,
	"screen_shake": true,
	"fast_animations": false,
	"input_profile": "default",
}
var values: Dictionary = DEFAULTS.duplicate(true)

func _ready() -> void:
	load_settings()

func get_value(key: String, fallback: Variant = null) -> Variant:
	return values.get(key, fallback)

func set_value(key: String, value: Variant, persist := true) -> void:
	values[key] = value
	settings_changed.emit(values.duplicate(true))
	if persist:
		save_settings()

func reset() -> void:
	values = DEFAULTS.duplicate(true)
	save_settings()
	settings_changed.emit(values.duplicate(true))

func load_settings() -> bool:
	if not FileAccess.file_exists(SETTINGS_PATH):
		return false
	var file := FileAccess.open(SETTINGS_PATH, FileAccess.READ)
	if file == null:
		return false
	var parsed = JSON.parse_string(file.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		return false
	for key in DEFAULTS:
		if parsed.has(key):
			values[key] = parsed[key]
	return true

func save_settings() -> bool:
	var file := FileAccess.open(SETTINGS_PATH, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(values, "\t"))
	file.flush()
	file.close()
	return true
