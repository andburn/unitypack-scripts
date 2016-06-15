import os


def write_to_file(path, contents, mode="w", info=False, warn=True):
	if os.path.isfile(path) and warn:
		print("WARNING: %s exists and will be overwritten" % (path))
	encoding = None if "b" in mode else "utf-8"
	with open(path, mode, encoding=encoding) as f:
		written = f.write(contents)
	if info:
		print("Written %i bytes to %r" % (written, path))


def filename_no_ext(path):
	return os.path.splitext(os.path.basename(path))[0];


def make_dirs(path):
	dirs = os.path.dirname(path)
	if not os.path.exists(dirs):
		os.makedirs(dirs)
		return True
	return False
