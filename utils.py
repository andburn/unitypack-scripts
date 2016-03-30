import os


def write_to_file(path, contents, mode="w", info=False):
	if os.path.isfile(path):
		print("WARNING: %s exists and will be overwritten" % (path))
	with open(path, mode) as f:
		written = f.write(contents)
	if info:
		print("Written %i bytes to %r" % (written, path))


def filename_no_ext(path):
	return os.path.splitext(os.path.basename(path))[0];


def get_file_path(basedir, filename):
	path = os.path.join(basedir, filename)
	dirs = os.path.dirname(path)
	if not os.path.exists(dirs):
		os.makedirs(dirs)
	return path
