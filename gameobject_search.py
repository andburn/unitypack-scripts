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
			pt(f"Cache file found for '{name}'")
			return pickle.load(f)


def save_bundle_cache(dir, name, data):
	file_path = os.path.join(dir, "".join([name, ".pickle"]))
	with open(file_path, "wb") as f:
		pt(f"Cache file created for '{name}'")
		pickle.dump(data, f)


def build_dict(bundle_name, asset):
	pt(f"Building dict for '{bundle_name}'")
	gameobjects = {}
	for id, obj in asset.objects.items():
		try:
			d = obj.read()
		except Exception as e:
			err(f"{id} '{e}'")
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
			go = GameObject(id, name, bundle_name.split("/")[0])
			if name in gameobjects:
				gameobjects[name.lower()].append(go)
			else:
				gameobjects[name.lower()] = [go]

	return gameobjects


pt_quiet=False

def pt(message):
	if not pt_quiet:
		print(message)

show_errors=False

def err(message):
	if show_errors:
		print(f"[ERROR] {message}")


def pt_cache(cache):
	for k, v in cache.items():
		print(f"\"{k}\"")
		for i in v:
			print(f"\t{i.id}\t{i.name}")


def main():
	global pt_quiet
	# setup the command arguments
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument("input",
		help="the directory containing the unity3d files")
	arg_parser.add_argument("cache",
		help="the directory containing the cache files")
	arg_parser.add_argument("search",
		help="the search string, case insensitive")
	arg_parser.add_argument("--cache-only", action="store_true",
		help="only use cached files, do not try to build anything")
	arg_parser.add_argument("--quiet", action="store_true",
		help="hide informational output")
	arg_parser.add_argument("--show-errors", action="store_true",
		help="display any errors encountered reading an asset")
	args = arg_parser.parse_args(sys.argv[1:])

	pt_quiet = args.quiet
	show_errors = args.show_errors

	if os.path.isdir(args.input):
	    files = glob.glob(args.input + "/*.unity3d")
	else:
		files = [args.input]

	results = []
	search_term = args.search.lower()

	for file in files:
		file_name = filename_no_ext(file)
		# try and get the file from the cache
		cache = get_bundle_cache(args.cache, file_name)
		# if its not cached, created it or skip it
		if not cache:
			if args.cache_only:
				# if only interested in cached files, try the next file
				continue
			go_dict = {}
			with open(file, "rb") as f:
				bundle = unitypack.load(f)
			for asset in bundle.assets:
				asset_bundle_name = f"{file_name}/{asset.name}"
				# build the game object dict
				go_dict.update(build_dict(asset_bundle_name, asset))
			# skip this file if dict is empty
			if len(go_dict) <= 0:
				continue
			# save dict as file cache
			cache = go_dict
			save_bundle_cache(args.cache, file_name, cache)
		# search this file
		for name in cache.keys():
			if search_term in name:
				results.extend(cache[name])

	if (len(results) > 0):
		for r in results:
			print(f"{r.id:22} {r.bundle:<16}{r.name}")
	else:
		print(f"No Results for '{search_term}'")


if __name__ == "__main__":
    main()
