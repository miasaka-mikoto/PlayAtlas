extends Control

## Minimal shell that can host the richer hall scene. It deliberately owns only
## navigation and shared presentation; a game module is mounted below it.

signal navigate(route: String)
signal game_selected(game_id: String)

@onready var title_label: Label = %TitleLabel
@onready var subtitle_label: Label = %SubtitleLabel
@onready var search_box: LineEdit = %SearchBox
@onready var game_list: VBoxContainer = %GameList
@onready var empty_label: Label = %EmptyLabel

func _ready() -> void:
	if GameRegistry != null:
		GameRegistry.catalogue_changed.connect(_refresh_games)
	_refresh_games()
	if search_box != null:
		search_box.text_changed.connect(func(_text: String) -> void: _refresh_games())

func _refresh_games() -> void:
	if game_list == null:
		return
	for child in game_list.get_children():
		child.queue_free()
	var query := search_box.text if search_box != null else ""
	var games: Array[Dictionary] = GameRegistry.search(query)
	if empty_label != null:
		empty_label.visible = games.is_empty()
	for game in games:
		var button := Button.new()
		button.text = "%s  ·  %s" % [str(game.get("title_zh", "")), str(game.get("title", ""))]
		button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		button.custom_minimum_size = Vector2(0, 48)
		button.tooltip_text = _game_tooltip(game)
		button.pressed.connect(func() -> void:
			game_selected.emit(str(game.get("id", "")))
		)
		game_list.add_child(button)

func _game_tooltip(game: Dictionary) -> String:
	var status := str(game.get("status", "in_development"))
	var players: Dictionary = game.get("players", {})
	return "%s | %s-%s players | %s" % [status, players.get("min", 1), players.get("max", 1), game.get("difficulty", "unknown")]
