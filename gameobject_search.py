import os
import sys
import glob
import pickle
from collections import namedtuple

import unitypack
import argparse

from utils import filename_no_ext


GameObject = namedtuple("GameObject", "id name bundle")


def get_bundle_cache(dir, name):
	file_path = os.path.join(dir, "".join([name, ".pickle"]))
	if os.path.isfile(file_path):
		with open(file_path, "rb") as f:
			print(f"cache loaded from: {file_path}")
			return pickle.load(f)


def save_bundle_cache(dir, name, data):
	file_path = os.path.join(dir, "".join([name, ".pickle"]))
	with open(file_path, "wb") as f:
		print(f"cache saved as: {file_path}")
		return pickle.dump(data, f)


def build_cache(dir, bundle_name, asset, quiet):
	print(f"Building cache: {bundle_name}")
	gameobjects = {}
	for id, obj in asset.objects.items():
		try:
			d = obj.read()
		except Exception as e:
			if not quiet:
				print(f"[Read Error] {id} '{e}'")
			continue

		name = ""
		try:
			name = d.name
		except Exception:
			pass

		type = ""
		try:
			type = obj.type
		except Exception:
			pass

		if type == "GameObject" and name:
			go = GameObject(id, name, bundle_name)
			if name in gameobjects:
				gameobjects[name].append(go)
			else:
				gameobjects[name] = [go]

	if len(gameobjects) > 0:
		save_bundle_cache(dir, bundle_name, gameobjects)

	return gameobjects


def print_cache(cache):
	# debug print cache
	for k, v in cache.items():
		print(k)
		for i in v:
			print(f"\t{i.id}\t{i.name}")


def main():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument("input")
	arg_parser.add_argument("cache")
	arg_parser.add_argument("search")
	arg_parser.add_argument("--quiet", action="store_true")
	args = arg_parser.parse_args(sys.argv[1:])

	# if os.path.isdir(args.input):
	#     files = glob.glob(args.input + "/*.unity3d")
	files = [args.input]

	print(f"Reading {len(files)} files in {args.input}")

	for file in files:
		with open(file, "rb") as f:
			bundle = unitypack.load(f)
			file_name = filename_no_ext(file)

		for asset in bundle.assets:
			asset_bundle_name = f"{file_name}_{asset.name}"
			print(asset_bundle_name)

			cache = get_bundle_cache(args.cache, asset_bundle_name)

			if not cache:
				cache = build_cache(args.cache, asset_bundle_name, asset, args.quiet)

			# look for exact search term as key
			if args.search in cache:
				print(cache[args.search])
			else:
				print(f"No Results for '{args.search}'")


if __name__ == "__main__":
    main()
