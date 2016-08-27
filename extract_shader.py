#!/usr/bin/env python
import os
import pickle
import sys
import glob
import unitypack
import utils.file as FileUtils
from unitypack.export import OBJMesh
from argparse import ArgumentParser
from unitypack import utils
from io import BytesIO


def handle_shader(shader, out_path):
	fname = os.path.join(out_path, shader.name)
	FileUtils.make_dirs(fname)

	if "m_SubProgramBlob" in shader._obj:
		compressed = utils.BinaryReader(BytesIO(shader._obj["m_SubProgramBlob"]))
		# decompress lz4 frame
		lz4 = utils.lz4_decompress(
			shader._obj["m_SubProgramBlob"],
			shader._obj["decompressedSize"]
		)
		uncompressed = utils.BinaryReader(BytesIO(lz4))
		progs = uncompressed.read_int()

		subshaders = []
		for p in range(progs):
			off = uncompressed.read_int()
			length = uncompressed.read_int()
			subshaders.append((off, length))

		for i, (o, l) in enumerate(subshaders):
			uncompressed.seek(o)
			data = uncompressed.read(l)
			FileUtils.write_to_file(fname + str(i) + ".sub", data, "wb")

		FileUtils.write_to_file(fname + ".bin", lz4, "wb")
		FileUtils.write_to_file(fname + ".shaderlab", shader.script, "w")


def main():
	p = ArgumentParser()
	p.add_argument("input")
	p.add_argument("output")
	args = p.parse_args(sys.argv[1:])

	files = [args.input]
	if not args.input.endswith("unity3d"):
		files = glob.glob(args.input + "/*.unity3d")

	for file in files:
		print("Processing %s" % (file))

		with open(file, "rb") as f:
			bundle = unitypack.load(f)

		for asset in bundle.assets:
			for id, obj in asset.objects.items():
				try:
					save_path = os.path.join(
						args.output,
						FileUtils.filename_no_ext(file),
						obj.type
					)
					d = obj.read()
					if obj.type == "Shader":
						print("Extracting %s (%d)" % (d.name, id))
						handle_shader(d, save_path)
				except Exception as e:
					print("[Error] %s" % (e))


if __name__ == "__main__":
	main()
