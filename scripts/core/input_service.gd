extends Node

## Input facade shared by desktop, touch and future gamepad adapters. Modules
## should consume semantic actions rather than inspect raw key codes.

signal action_triggered(action: String, event: InputEvent)

const ACTIONS := ["confirm", "cancel", "pause_game", "move_up", "move_down", "move_left", "move_right", "primary", "secondary"]

func _ready() -> void:
	_ensure_actions()

func _unhandled_input(event: InputEvent) -> void:
	for action in ACTIONS:
		if InputMap.has_action(action) and event.is_action_pressed(action):
			action_triggered.emit(action, event)

func is_pressed(action: String) -> bool:
	return Input.is_action_pressed(action)

func add_action(action: String, input_event: InputEvent) -> void:
	if not InputMap.has_action(action):
		InputMap.add_action(action)
	InputMap.action_add_event(action, input_event)

func _ensure_actions() -> void:
	for action in ACTIONS:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
	# Keep the project usable immediately after a clean import.  These are
	# conservative semantic defaults; a game may add touch/gamepad bindings
	# through its manifest without replacing the user's profile.
	_add_default_key("confirm", KEY_ENTER)
	_add_default_key("confirm", KEY_SPACE)
	_add_default_key("cancel", KEY_ESCAPE)
	_add_default_key("pause_game", KEY_P)
	_add_default_key("move_up", KEY_UP)
	_add_default_key("move_down", KEY_DOWN)
	_add_default_key("move_left", KEY_LEFT)
	_add_default_key("move_right", KEY_RIGHT)

func _add_default_key(action: String, keycode: int) -> void:
	if not InputMap.has_action(action):
		return
	for existing in InputMap.action_get_events(action):
		if existing is InputEventKey and int(existing.physical_keycode) == keycode:
			return
	var event := InputEventKey.new()
	event.physical_keycode = keycode
	InputMap.action_add_event(action, event)
