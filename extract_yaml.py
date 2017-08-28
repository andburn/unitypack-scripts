#!/usr/bin/env python
import os
import sys
import glob
import unitypack
import utils.file as FileUtils
import utils.serializer as YamlSerializer


FILE_EXT = ".unity3d"
EXCLUDES = ["sounds0", "dbf", "fonts0", "fontsjajp0", "fontsruru0"]


def main():
	if len(sys.argv) != 3:
		print("Usage: extract_yaml.py <dir_in> <dir_out>")
		sys.exit(2)

	dir_in = sys.argv[1]
	dir_out = sys.argv[2]
	files = glob.glob(dir_in + "/*" + FILE_EXT)

	for f in files:
		bundle_name = FileUtils.filename_no_ext(f)
		if bundle_name in EXCLUDES:
			print("Skipping %s%s" % (bundle_name, FILE_EXT))
			continue
		else:
			out_path = os.path.join(dir_out, bundle_name)
			print("Extracting %s%s" % (bundle_name, FILE_EXT))

		with open(f, "rb") as fin:
			bundle = unitypack.load(fin)

		for asset in bundle.assets:
			for id, obj in asset.objects.items():
				try:
					d = obj.read()
					file_out = os.path.join(out_path, str(id) + ".yaml")
					FileUtils.make_dirs(file_out)
					FileUtils.write_to_file(file_out, YamlSerializer.serialize(d), warn=False)
				except Exception as e:
					print("[Error] %s" % (e))


if __name__ == "__main__":
	main()
