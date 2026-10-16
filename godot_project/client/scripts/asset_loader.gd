extends RefCounted

## Package-safe image loading. A Godot export (Android in particular) does not ship the source PNG files: it ships the imported
## `.godot/imported/*.ctex` resources and a `.import` remap next to each name. `Image.load("a res:// image path")` and
## `FileAccess.file_exists("a res:// image path")` therefore fail on a phone while they work from the editor on the PC. Everything that
## picks an image at run time must go through here, so the same code runs in the editor, in headless tests and in an export.
##
## Order: the imported resource (the only thing an export has), then the raw source file (an editor or a headless run that has
## not imported the project yet). Textures are the engine's own CompressedTexture2D, so they are also cheaper than the
## ImageTexture copies the code used to build.


static func exists(path: String) -> bool:
	if path == "":
		return false
	return ResourceLoader.exists(path) or FileAccess.file_exists(path)


static func load_texture(path: String) -> Texture2D:
	if path == "":
		return null
	if ResourceLoader.exists(path):
		var res: Resource = ResourceLoader.load(path)
		if res is Texture2D:
			return res
	if FileAccess.file_exists(path):
		var img := Image.load_from_file(path)
		if img != null and not img.is_empty():
			return ImageTexture.create_from_image(img)
	return null


static func read_text(path: String) -> String:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return ""
	return f.get_as_text()
