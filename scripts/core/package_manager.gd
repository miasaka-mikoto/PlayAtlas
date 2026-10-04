extends Node

## Trusted local package manager. Packages are data-first and are validated
## before installation. Unknown scripts are rejected by default; this is not a
## general-purpose sandbox for arbitrary community code.

signal package_changed(game_id: String)
signal package_error(message: String)

const PACKAGE_ROOT := "user://packages"
const MAX_PACKAGE_FILES := 10000
const MAX_UNCOMPRESSED_BYTES := 512 * 1024 * 1024
const MANIFEST_NAME := "manifest.json"
var installed: Dictionary = {}

func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(PACKAGE_ROOT))
	_scan_installed()

func list_installed() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	for manifest in installed.values():
		result.append(manifest.duplicate(true))
	return result

func is_installed(game_id: String) -> bool:
	return installed.has(game_id)

func inspect_package(package_path: String) -> Dictionary:
	var zip := ZIPReader.new()
	if zip.open(package_path) != OK:
		return {"ok": false, "error": "Unable to open package"}
	var files := zip.get_files()
	if files.size() > MAX_PACKAGE_FILES:
		zip.close()
		return {"ok": false, "error": "Package contains too many files"}
	var total := 0
	for file_name in files:
		if not _is_safe_path(file_name):
			zip.close()
			return {"ok": false, "error": "Unsafe path: %s" % file_name}
		if file_name.ends_with(".gd") or file_name.ends_with(".dll") or file_name.ends_with(".exe"):
			zip.close()
			return {"ok": false, "error": "Executable content is not allowed in data packages"}
		var bytes: PackedByteArray = zip.read_file(file_name)
		total += bytes.size()
		if total > MAX_UNCOMPRESSED_BYTES:
			zip.close()
			return {"ok": false, "error": "Package exceeds uncompressed size limit"}
	if MANIFEST_NAME not in files:
		zip.close()
		return {"ok": false, "error": "Missing manifest.json"}
	var parsed = JSON.parse_string(zip.read_file(MANIFEST_NAME).get_string_from_utf8())
	zip.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return {"ok": false, "error": "Invalid manifest.json"}
	var validation := _validate_manifest(parsed)
	validation["manifest"] = parsed
	validation["file_count"] = files.size()
	validation["uncompressed_bytes"] = total
	return validation

func install_package(package_path: String, keep_save := true) -> bool:
	var inspected := inspect_package(package_path)
	if not bool(inspected.get("ok", false)):
		package_error.emit(str(inspected.get("error", "Package validation failed")))
		return false
	var manifest: Dictionary = inspected["manifest"]
	var game_id := str(manifest["id"])
	var destination := _package_path(game_id)
	var staging := destination + ".staging"
	var backup := destination + ".backup"
	if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(staging)):
		_remove_directory(staging)
	if DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(backup)):
		_remove_directory(backup)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(staging))
	var zip := ZIPReader.new()
	if zip.open(package_path) != OK:
		package_error.emit("Unable to open package during install")
		return false
	for file_name in zip.get_files():
		var target := staging.path_join(file_name)
		if file_name.ends_with("/"):
			DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(target))
			continue
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(target.get_base_dir()))
		var file := FileAccess.open(target, FileAccess.WRITE)
		if file == null:
			zip.close()
			_remove_directory(staging)
			package_error.emit("Unable to write staged package")
			return false
		file.store_buffer(zip.read_file(file_name))
		file.close()
	zip.close()
	var had_previous := DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(destination))
	if had_previous:
		var backed_up := DirAccess.rename_absolute(ProjectSettings.globalize_path(destination), ProjectSettings.globalize_path(backup))
		if backed_up != OK:
			_remove_directory(staging)
			package_error.emit("Unable to back up existing package")
			return false
	var renamed := DirAccess.rename_absolute(ProjectSettings.globalize_path(staging), ProjectSettings.globalize_path(destination))
	if renamed != OK:
		_remove_directory(staging)
		if had_previous:
			DirAccess.rename_absolute(ProjectSettings.globalize_path(backup), ProjectSettings.globalize_path(destination))
		package_error.emit("Unable to activate package")
		return false
	# Keep the previous version until the next successful update so a support
	# tool can recover it.  It is never treated as an active package.
	installed[game_id] = manifest.duplicate(true)
	package_changed.emit(game_id)
	return true

func uninstall_package(game_id: String, delete_save := false) -> bool:
	if not installed.has(game_id):
		return true
	var result := _remove_directory(_package_path(game_id))
	if result:
		installed.erase(game_id)
		if delete_save:
			SaveService.delete_save(game_id)
		package_changed.emit(game_id)
	return result

func _validate_manifest(manifest: Dictionary) -> Dictionary:
	for field in ["id", "title", "version", "game_family", "entry_resource"]:
		if not manifest.has(field) or str(manifest[field]).strip_edges().is_empty():
			return {"ok": false, "error": "Manifest is missing %s" % field}
	if not str(manifest["id"]).is_valid_identifier():
		return {"ok": false, "error": "Manifest id must be a safe identifier"}
	return {"ok": true}

func _scan_installed() -> void:
	var root := DirAccess.open(PACKAGE_ROOT)
	if root == null:
		return
	root.list_dir_begin()
	var name := root.get_next()
	while not name.is_empty():
		if root.current_is_dir() and not name.begins_with(".") and not name.ends_with(".backup") and not name.ends_with(".staging"):
			var manifest_path := PACKAGE_ROOT.path_join(name).path_join(MANIFEST_NAME)
			var file := FileAccess.open(manifest_path, FileAccess.READ)
			if file != null:
				var parsed = JSON.parse_string(file.get_as_text())
				if typeof(parsed) == TYPE_DICTIONARY and bool(_validate_manifest(parsed).get("ok", false)):
					installed[str(parsed["id"])] = parsed
			name = root.get_next()
	root.list_dir_end()

func _package_path(game_id: String) -> String:
	return PACKAGE_ROOT.path_join(game_id)

func _is_safe_path(path: String) -> bool:
	return not path.is_absolute_path() and not path.contains("..") and not path.contains("\\")

func _remove_directory(path: String) -> bool:
	var directory := DirAccess.open(path)
	if directory == null:
		return true
	directory.list_dir_begin()
	var name := directory.get_next()
	while not name.is_empty():
		var child := path.path_join(name)
		if directory.current_is_dir():
			_remove_directory(child)
		else:
			DirAccess.remove_absolute(ProjectSettings.globalize_path(child))
		name = directory.get_next()
	directory.list_dir_end()
	return DirAccess.remove_absolute(ProjectSettings.globalize_path(path)) == OK
