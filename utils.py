import os


class Echo:
	quiet = False
	very_quiet = False
	hide_errors = False

	@classmethod
	def echo(cls):
		return (cls.debug, cls.info, cls.error)

	@classmethod
	def debug(cls, message):
		if not cls.quiet and not cls.very_quiet:
			print(message)

	@classmethod
	def info(cls, message):
		if not cls.very_quiet:
			print(message)

	@classmethod
	def error(cls, message):
		if not cls.hide_errors:
			print(message)


def write_to_file(path, contents, mode="w"):
	if os.path.isfile(path):
		Echo.info("WARNING: %s exists and will be overwritten" % (path))
	encoding = None if "b" in mode else "utf-8"
	with open(path, mode, encoding=encoding) as f:
		written = f.write(contents)
	Echo.debug("Written %i bytes to %r" % (written, path))


def filename_no_ext(path):
	return os.path.splitext(os.path.basename(path))[0];


def make_dirs(path):
	dirs = os.path.dirname(path)
	if not os.path.exists(dirs):
		os.makedirs(dirs)
		return True
	return False


def vec_from_dict(d, precision=None):
	from objects import Vec2, Vec3, Vec4, Color

	dim = len(d)
	if dim == 2:
		return Vec2(d["x"], d["y"])
	elif dim == 3:
		return Vec3(d["x"], d["y"], d["z"])
	elif dim == 4:
		if "x" in d:
			return Vec4(d["x"], d["y"], d["z"], d["w"])
		elif "r" in d:
			return Color(d["r"], d["g"], d["b"], d["a"])
