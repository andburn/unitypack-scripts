#!/usr/bin/env python

"""Dump all shaders including all subprogram blobs"""

import os
import pickle
import sys
import glob
import unitypack
import utils
from unitypack.export import OBJMesh
from argparse import ArgumentParser
from io import BytesIO
from shaders import extract_shader, redefine_shader


def main():
	p = ArgumentParser()
	p.add_argument("input")
	p.add_argument("output")
	p.add_argument("--debug", action="store_true")
	args = p.parse_args(sys.argv[1:])

	files = [args.input]
	if os.path.isdir(args.input):
		files = glob.glob(args.input + "/*")

	redefine_shader()

	for file in files:
		print("Processing %s" % (file))

		with open(file, "rb") as f:
			bundle = unitypack.load(f)

		for asset in bundle.assets:
			for id, obj in asset.objects.items():
				#try:
				save_path = os.path.join(
					args.output,
					utils.filename_no_ext(file),
					obj.type
				)
				if obj.type == "Shader":
					d = obj.read()
					print(d.name)
					extract_shader(d, save_path, args.debug)
				#except Exception as e:
				#	print("[Error] %s" % (e))


if __name__ == "__main__":
	main()
