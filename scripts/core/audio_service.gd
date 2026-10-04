extends Node

## Central audio policy. Actual streams are supplied by game packages; this
## service keeps mute/volume behavior consistent without requiring any asset.

var music_player: AudioStreamPlayer
var sfx_bus := "SFX"

func _ready() -> void:
	music_player = AudioStreamPlayer.new()
	music_player.name = "MusicPlayer"
	add_child(music_player)
	_ensure_sfx_bus()
	_apply_volume()
	if SettingsService != null:
		SettingsService.settings_changed.connect(_on_settings_changed)

func play_music(stream: AudioStream, loop := true) -> void:
	if stream == null:
		return
	music_player.stream = stream
	music_player.set_meta("loop", loop)
	music_player.play()

func stop_music() -> void:
	if music_player != null:
		music_player.stop()

func play_sfx(stream: AudioStream, volume_db := 0.0) -> void:
	if stream == null or bool(SettingsService.get_value("muted", false)):
		return
	var player := AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = volume_db
	player.bus = sfx_bus
	add_child(player)
	player.finished.connect(player.queue_free)
	player.play()

func _on_settings_changed(_settings: Dictionary) -> void:
	_apply_volume()

func _apply_volume() -> void:
	if music_player == null:
		return
	var muted := bool(SettingsService.get_value("muted", false))
	var volume := float(SettingsService.get_value("music_volume", 0.75))
	music_player.volume_db = -80.0 if muted else linear_to_db(maxf(volume, 0.001))
	_ensure_sfx_bus()
	var sfx_volume := float(SettingsService.get_value("sfx_volume", 0.9))
	var sfx_index := AudioServer.get_bus_index(sfx_bus)
	if sfx_index >= 0:
		AudioServer.set_bus_mute(sfx_index, muted)
		AudioServer.set_bus_volume_db(sfx_index, -80.0 if muted else linear_to_db(maxf(sfx_volume, 0.001)))

func _ensure_sfx_bus() -> void:
	if AudioServer.get_bus_index(sfx_bus) >= 0:
		return
	AudioServer.add_bus()
	AudioServer.set_bus_name(AudioServer.bus_count - 1, sfx_bus)
