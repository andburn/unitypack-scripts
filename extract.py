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
from fsb5 import FSB5
import utils


def write_to_file(path, filename, contents, mode="w"):
	file = utils.get_file_path(path, filename)
	with open(file, mode) as f:
		written = f.write(contents)


def handle_asset(asset, handle_formats, dir, flip, obj):
	for id, obj in asset.objects.items():
		if obj.type not in handle_formats:
			continue

		save_path = os.path.join(dir, obj.type)
		d = obj.read()

		if obj.type == "AudioClip":
			if not d.data:
				# eg. StreamedResource not available
				continue
			af = FSB5(d.data)
			for i, sample in enumerate(af.samples):
				if i > 0:
					filename = "%s-%i.%s" % (d.name, i, af.get_sample_extension())
				else:
					filename = "%s.%s" % (d.name, af.get_sample_extension())
				try:
					sample = af.rebuild_sample(sample)
				except ValueError as e:
					print("WARNING: Could not extract %r (%s)" % (d, e))
					continue
				write_to_file(save_path, filename, sample, mode="wb")

		elif obj.type == "MovieTexture":
			filename = d.name + ".ogv"
			write_to_file(save_path, filename, d.movie_data, mode="wb")

		elif obj.type == "Shader":
			write_to_file(save_path, d.name + ".cg", d.script)

		elif obj.type == "Mesh":
			try:
				mesh_data = None
				ext = ".js"
				if obj:
					mesh_data = OBJMesh(d).export()
					ext = ".obj"
				else:
					mesh_data = json_mesh.JSONMesh(d).export()
				write_to_file(save_path, d.name + ext, mesh_data, mode="w")
			except NotImplementedError as e:
				print("WARNING: Could not extract %r (%s)" % (d, e))
				mesh_data = pickle.dumps(d._obj)
				write_to_file(save_path, d.name + ".Mesh.pickle", mesh_data, mode="wb")

		elif obj.type == "TextAsset":
			if isinstance(d.script, bytes):
				write_to_file(save_path, d.name + ".bin", d.script, mode="wb")
			else:
				write_to_file(save_path, d.name + ".txt", d.script)

		elif obj.type == "Texture2D":
			filename = d.name + ".png"
			image = d.image
			if image is None:
				print("WARNING: %s is an empty image" % (filename))
				write_to_file(save_path, filename, "")
			else:
				print("Decoding %r" % (d))
				img = image
				if flip:
					img = ImageOps.flip(image)
				path = utils.get_file_path(save_path, filename)
				img.save(path)


def main():
	p = ArgumentParser()
	p.add_argument("input")
	p.add_argument("output")
	p.add_argument("--flip", action="store_true")
	p.add_argument("--obj", action="store_true")
	p.add_argument("--all", action="store_true")
	p.add_argument("--audio", action="store_true")
	p.add_argument("--images", action="store_true")
	p.add_argument("--models", action="store_true")
	p.add_argument("--shaders", action="store_true")
	p.add_argument("--text", action="store_true")
	p.add_argument("--video", action="store_true")
	args = p.parse_args(sys.argv[1:])

	format_args = {
		"audio": "AudioClip",
		"images": "Texture2D",
		"models": "Mesh",
		"shaders": "Shader",
		"text": "TextAsset",
		"video": "MovieTexture",
	}
	handle_formats = []
	for a, classname in format_args.items():
		if args.all or getattr(args, a):
			handle_formats.append(classname)

	files = glob.glob(args.input + "/*.unity3d")
	for file in files:
		bundle_name = utils.filename_no_ext(file)
		print("Extracting %s..." % (bundle_name))
		if bundle_name == "cardxml0":
			continue
		save_path = os.path.join(args.output, bundle_name)

		with open(file, "rb") as f:
			bundle = unitypack.load(f)

		for asset in bundle.assets:
			handle_asset(asset, handle_formats, save_path, args.flip, args.obj)


if __name__ == "__main__":
	main()
