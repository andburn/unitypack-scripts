#!/usr/bin/env python

"""Dump all contents of all unity3d files in dir as yaml

Based on UnityPack's unity2yaml script
"""

import os
import sys
import glob
import yaml
import unitypack
import unitypack
import unitypack.engine as engine
from unitypack.object import ObjectPointer
from unitypack.asset import Asset
from utils import *


FILE_EXT = ".unity3d"
EXCLUDES = ["sounds0", "dbf", "fonts0", "fontsjajp0", "fontsruru0"]


def unityobj_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:%s" % (data.__class__.__name__), data._obj)


def asset_representer(dumper, data):
	return dumper.represent_scalar("!asset", data.name)


def asset_constructor(loader, node):
	return loader.construct_scalar(node)


def objectpointer_representer(dumper, data):
	return dumper.represent_sequence("!PPtr", [data.file_id, data.path_id])


def objectpointer_constructor(loader, node):
	return loader.construct_sequence(node)


def shader_representer(dumper, data):
	obj = data._obj.copy()
	if "compressedBlob" in obj:
		obj["compressedBlob"] = "<stripped>"
	return dumper.represent_mapping("!unitypack:stripped:Shader", obj)


def textasset_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:stripped:TextAsset", {data.name: None})


def texture2d_representer(dumper, data):
	return dumper.represent_mapping("!unitypack:stripped:Texture2D", {data.name: None})


def mesh_representer(dumper, data):
	obj = data._obj.copy()
	obj["m_IndexBuffer"] = "<stripped>"
	obj["m_VertexData"] = "<stripped>"
	return dumper.represent_mapping("!unitypack:stripped:Mesh", obj)


def movietexture_representer(dumper, data):
	obj = data._obj.copy()
	obj["m_MovieData"] = "<stripped>"
	return dumper.represent_mapping("!unitypack:stripped:MovieTexture", obj)


def serialize(obj):
	return yaml.dump(obj)


def deserialize(obj):
	return yaml.load(obj)


def mapping_constructor(loader, node):
	return loader.construct_mapping(node)


def main():
	if len(sys.argv) != 3:
		print("Usage: extract_yaml.py <dir_in> <dir_out>")
		sys.exit(2)

	dir_in = sys.argv[1]
	dir_out = sys.argv[2]

	if dir_in.endswith(FILE_EXT):
		files = [dir_in]
	else:
		files = glob.glob(dir_in + "/*" + FILE_EXT)

	# define default representers and constructors for unity engine objects
	for k, v in engine.__dict__.items():
		if isinstance(v, type) and issubclass(v, engine.object.Object):
			yaml.add_representer(v, unityobj_representer)
			yaml.add_constructor("!unitypack:%s" % (k), mapping_constructor)
	# define for non engine objects
	yaml.add_representer(Asset, asset_representer)
	yaml.add_representer(ObjectPointer, objectpointer_representer)
	# override set representer with stripped versions, for these objects
	yaml.add_representer(engine.text.TextAsset, textasset_representer)
	yaml.add_representer(engine.mesh.Mesh, mesh_representer)
	yaml.add_representer(engine.movie.MovieTexture, movietexture_representer)
	yaml.add_representer(engine.text.Shader, shader_representer)
	yaml.add_representer(engine.texture.Texture2D, texture2d_representer)
	# constructors
	yaml.add_constructor("!asset", asset_constructor)
	yaml.add_constructor("!PPtr", objectpointer_constructor)
	# stripped versions
	yaml.add_constructor("!unitypack:stripped:TextAsset", mapping_constructor)
	yaml.add_constructor("!unitypack:stripped:Mesh", mapping_constructor)
	yaml.add_constructor("!unitypack:stripped:MovieTexture", mapping_constructor)
	yaml.add_constructor("!unitypack:stripped:Shader", mapping_constructor)
	yaml.add_constructor("!unitypack:stripped:Texture2D", mapping_constructor)

	for f in files:
		bundle_name = filename_no_ext(f)
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
					make_dirs(file_out)
					write_to_file(file_out, serialize(d), warn=False)
				except Exception as e:
					print("[Error] %s" % (e))


if __name__ == "__main__":
	main()
