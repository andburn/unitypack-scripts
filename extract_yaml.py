import os
import sys
import glob
import unitypack
import utils
import obj_to_yaml


def main():
	dir_in = sys.argv[1]
	dir_out = sys.argv[2]

	files = glob.glob(dir_in + '/*.unity3d')
	yaml = obj_to_yaml.YamlWriter()

	for file in files:
		save_path = os.path.join(dir_out, utils.filename_no_ext(file))

		with open(file, "rb") as f:
			bundle = unitypack.load(f)

		for asset in bundle.assets:
			for id, obj in asset.objects.items():
				d = obj.read()
				f = utils.get_file_path(save_path, str(id) + ".yaml")
				utils.write_to_file(f, yaml.write(d))


if __name__ == "__main__":
	main()
