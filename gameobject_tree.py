import os
import sys
from collections import namedtuple

import unitypack
import argparse


GameObject = namedtuple("GameObject", "id name bundle")


def get_by_id(sid, asset):
	print(f"Loading {asset.name}")
	for id, obj in asset.objects.items():
		if sid != id:
			continue

		try:
			d = obj.read()
		except Exception as e:
			print(f"ERROR {e}")
			continue

		return d


def get_transform(game_object):
	components = game_object.component
	for comp in components:
		obj = comp["component"].resolve()
		try:
			obj.parent
			return obj
		except AttributeError:
			continue


def get_root_object(game_object):
	transform = get_transform(game_object)
	while transform.parent:
		transform = transform.parent.resolve()
	return transform.game_object.resolve()


# 7714193434438982024 shared7 > none
# 8149677989356223801 spells3 > parent
# shared5 -7771824907442899968
def main():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument("dir",
		help="the directory containing the unity3d files")
	arg_parser.add_argument("bundle",
		help="the unity3d file containing the asset")
	arg_parser.add_argument("id",
		help="the id of the base asset")
	args = arg_parser.parse_args(sys.argv[1:])

	base_id = int(args.id)

	with open(os.path.join(args.dir, args.bundle + ".unity3d"), "rb") as f:
		bundle = unitypack.load(f)
	for asset in bundle.assets:
		game_object = get_by_id(base_id, asset)
		if not game_object:
			print(f"{base_id} not found in {asset.name}")
			break

		root_object = get_root_object(game_object)


if __name__ == "__main__":
	main()
