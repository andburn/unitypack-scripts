#!/usr/bin/env python
import os
import pickle
import sys
import glob
import unitypack
from unitypack.export import OBJMesh
import json_mesh
from argparse import ArgumentParser
from PIL import ImageOps
import utils.file as FileUtils


EXCLUDES = ["sounds0"]


def handle_asset(asset, handle_formats, dir, flip, objMesh, quiet):
	for id, obj in asset.objects.items():
		try:
			otype = obj.type
		except Exception as e:
			print("[Error] %s" % (e))
			continue

		if otype not in handle_formats:
			continue

		d = obj.read()
		save_path = os.path.join(dir, obj.type, d.name)
		FileUtils.make_dirs(save_path)

		if otype == "Mesh":
			try:
				mesh_data = None
				
				if not objMesh:
					mesh_data = json_mesh.JSONMesh(d).export()
					FileUtils.write_to_file(save_path + ".js", mesh_data, mode="w")
					
				mesh_data = OBJMesh(d).export()
				FileUtils.write_to_file(save_path + ".obj", mesh_data, mode="w")
			except (NotImplementedError, RuntimeError) as e:
				print("WARNING: Could not extract %r (%s)" % (d, e))
				mesh_data = pickle.dumps(d._obj)
				FileUtils.write_to_file(save_path + ".Mesh.pickle", mesh_data, mode="wb")

		elif otype == "TextAsset":
			if isinstance(d.script, bytes):
				FileUtils.write_to_file(save_path + ".bin", d.script, mode="wb")
			else:
				FileUtils.write_to_file(save_path + ".txt", d.script)

		elif otype == "Texture2D":
			filename = d.name + ".png"
			try:
				image = d.image
				if image is None:
					print("WARNING: %s is an empty image" % (filename))
					FileUtils.write_to_file(save_path + ".empty", "")
				else:
					if not quiet:
						print("Decoding %r" % (d))
					img = image
					if flip:
						img = ImageOps.flip(image)
					img.save(save_path + ".png")
			except Exception as e:
				print("Failed to extract texture %s (%s)" % (d.name, e))



def main():
	p = ArgumentParser()
	p.add_argument("files", nargs="+")
	p.add_argument("--output", "-o", required=True)
	p.add_argument("--all", action="store_true")
	p.add_argument("--images", action="store_true")
	p.add_argument("--models", action="store_true")
	p.add_argument("--text", action="store_true")
	p.add_argument("--quiet", action="store_true")
	# flip images the "right" way up
	p.add_argument("--flip", action="store_true")
	# option for obj meshes (instead of js)
	p.add_argument("--obj", action="store_true")
	args = p.parse_args(sys.argv[1:])

	format_args = {
		"images": "Texture2D",
		"models": "Mesh",
		"text": "TextAsset",
	}
	handle_formats = []
	for a, classname in format_args.items():
		if args.all or getattr(args, a):
			handle_formats.append(classname)

	files = args.files
	if len(args.files) == 1:
		if not args.files[0].endswith("unity3d"):
			files = glob.glob(args.files[0] + "/*.unity3d")

	for file in files:
		bundle_name = FileUtils.filename_no_ext(file)
		if bundle_name in EXCLUDES:
			print("Skipping %s..." % (bundle_name))
			continue
		print("Extracting %s..." % (bundle_name))
		save_path = os.path.join(args.output, bundle_name)

		with open(file, "rb") as f:
			bundle = unitypack.load(f)

		for asset in bundle.assets:
			handle_asset(asset, handle_formats, save_path,
						 args.flip, args.obj, args.quiet)


if __name__ == "__main__":
	main()
