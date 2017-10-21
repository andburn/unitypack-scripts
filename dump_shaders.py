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


(debug, info, error) = utils.Echo.echo()


def main():
	p = ArgumentParser()
	p.add_argument("input")
	p.add_argument("output")
	p.add_argument("--raw", action="store_true")
	p.add_argument("-qq", action="store_true")
	p.add_argument("-q", action="store_true")
	args = p.parse_args(sys.argv[1:])

	utils.Echo.quiet = args.q
	utils.Echo.very_quiet = args.qq

	files = [args.input]
	if os.path.isdir(args.input):
		files = glob.glob(args.input + "/*")

	redefine_shader()

	for file in files:
		info("Processing %s" % (file))

		with open(file, "rb") as f:
			bundle = unitypack.load(f)

		for asset in bundle.assets:
			for id, obj in asset.objects.items():
				bundle_name = utils.filename_no_ext(file)
				try:
					if obj.type == "Shader":
						d = obj.read()
						save_path = os.path.join(
							args.output,
							bundle_name,
							obj.type
						)
						extract_shader(d, save_path, args.raw)
				except Exception as e:
					error("{0} ({1})".format(e, bundle_name))

if __name__ == "__main__":
	main()
