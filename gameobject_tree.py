import argparse
import json
import os
import sys
from io import BytesIO

import unitypack
from PIL import ImageOps
from unitypack.environment import UnityEnvironment

from shaders import extract_shader, redefine_shader
from utils import vec_from_dict, write_to_file, Echo


(debug, info, error) = Echo.echo()


class Tree:
	def __init__(self, root=None):
		self.root = root

	def print_node(self, node, level=0):
		indent = "--" * level
		if not node:
			print(indent + "Emtpy Node")
			return
		print(indent + node.name)
		for c in node.children:
			self.print_node(c, level + 1)

	def print(self):
		self.print_node(self.root)


class Node:
	def __init__(self, name, parent=None):
		self.name = name
		self.parent = parent
		self.children = []


class Transform:
	def __init__(self, obj):
		self.position = vec_from_dict(obj.position)
		self.rotation = vec_from_dict(obj.rotation)
		self.scale = vec_from_dict(obj.scale)

	def to_json(self):
		return {
			"position": self.position,
			"rotation": self.rotation,
			"scale": self.scale
		}


class Texture:
	def __init__(self, name, obj):
		self.name = name
		self.pointer = obj["m_Texture"]
		self.scale = vec_from_dict(obj["m_Scale"])
		self.offset = vec_from_dict(obj["m_Offset"])
		self.__load_props(obj)

	def __load_props(self, obj):
		self.object = self.pointer.resolve()
		self.file = self.object.name

	def to_json(self):
		return {
			"name": self.name,
			"file": self.file,
			"scale": self.scale,
			"offset": self.offset
		}


class Material:
	def __init__(self, pointer):
		self.pointer = pointer
		self.object = pointer.resolve()
		self.name = self.object.name
		self.shader = None
		self.shader_keywords = []
		self.textures = {}
		self.uniforms = {}
		self.__load_props(self.object)

	def __load_props(self, obj):
		for k, v in obj.saved_properties["m_TexEnvs"].items():
			self.textures[k] = Texture(k, v)
		for k, v in obj.saved_properties["m_Colors"].items():
			self.uniforms[k] = vec_from_dict(v)
		for k, v in obj.saved_properties["m_Floats"].items():
			self.uniforms[k] = float(v)
		self.shader = self.object.shader.resolve()

	def to_json(self):
		return {
			"name": self.name,
			"shader": self.shader.parsed_form.name,
			"keywords": self.shader_keywords,
			"textures": self.textures,
			"uniforms": self.uniforms
		}


class Mesh:
	def __init__(self, pointer):
		self.pointer = pointer
		self.object = pointer.resolve()
		self.name = self.object.name

	def to_json(self):
		return self.name


class GameObject(Node):
	def __init__(self, game_object, transform):
		super().__init__(game_object.name)
		self.transform = Transform(transform)
		self.mesh = None
		self.materials = []
		self.scripts = []
		self.children = []
		self.__load_components(game_object.component)

	def __load_components(self, components):
		for component in components:
			comp = component["component"].resolve()
			# weak check on component types
			try:
				if "m_Mesh" in comp._obj:
					# MeshFilter
					self.mesh = Mesh(comp._obj["m_Mesh"])
				elif "m_MotionVectors" in comp._obj:
					# MeshRenderer
					for m in comp._obj["m_Materials"]:
						self.materials.append(Material(m))
				elif "m_Father" in comp._obj:
					# Transform (skip, added separately)
					continue
				else:
					debug("Unknown component")
			except AttributeError:
				if "m_Script" in comp:
					self.scripts.append(
						comp["m_Script"].resolve()["m_ClassName"])
				else:
					error("Component error")

	def to_json(self):
		return {
            "name": self.name,
            "transform": self.transform,
            "mesh": self.mesh,
			"materials": self.materials,
			"scripts": self.scripts,
            "children": self.children
        }


class GameObjectEncoder(json.JSONEncoder):
	def default(self, obj):
		if hasattr(obj, "to_json"):
			return obj.to_json()
		else:
			info(f"{obj} does not implement to_json()")
			return json.JSONEncoder.default(self, obj)


def get_by_id(sid, asset):
	info(f"Loading {asset.name}")
	for id, obj in asset.objects.items():
		if sid != id:
			continue
		try:
			d = obj.read()
		except Exception as e:
			error(f"ERROR {e}")
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


def traverse_transforms(transform, tree, parent=None):
	game_object = transform.game_object.resolve()
	new_node = GameObject(game_object, transform)

	if not parent:
		tree.root = new_node
	else:
		new_node.parent = parent
		parent.children.append(new_node)

	for child in transform.children:
		traverse_transforms(child.resolve(), tree, new_node)


def extract_texture(texture, out_dir, flip=True):
	filename = texture.name + ".png"
	try:
		image = texture.image
	except NotImplementedError:
		error(f"WARNING: Texture format not implemented. Skipping {filename}.")
		return

	if image is None:
		error("WARNING: {filename} is an empty image")
		return

	info("Decoding {texture.name}")
	# Texture2D objects are flipped
	if flip:
		img = ImageOps.flip(image)
	# PIL has no method to write to a string :/
	output = BytesIO()
	img.save(output, format="png")
	write_to_file(
		os.path.join(out_dir, filename),
		output.getvalue(),
		mode="wb"
	)


def extract_assets(game_object, out_dir):
	from unitypack.export import OBJMesh

	if game_object.mesh:
		write_to_file(
			os.path.join(out_dir, game_object.mesh.name + ".obj"),
			OBJMesh(game_object.mesh.object).export()
		)
	for material in game_object.materials:
		if material.shader:
			extract_shader(material.shader, out_dir)
		for texture in material.textures.values():
			extract_texture(texture.object, out_dir)

	for child in game_object.children:
		extract_assets(child, out_dir)


def main():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument("files", nargs="+", help="the unity3d files")
	arg_parser.add_argument("id", help="the id of the base asset")
	arg_parser.add_argument("output", help="the output directory")
	arg_parser.add_argument("-q", action="store_true")
	arg_parser.add_argument("-qq", action="store_true")
	args = arg_parser.parse_args(sys.argv[1:])

	Echo.quiet = args.q
	Echo.very_quiet = args.qq

	base_id = int(args.id)

	redefine_shader()
	env = UnityEnvironment()

	for file in args.files:
		info(f"Reading {file}")
		f = open(file, "rb")
		env.load(f)

	for bundle in env.bundles.values():
		for asset in bundle.assets:
			info(f"Parsing {asset.name}")
			game_object = get_by_id(base_id, asset)
			if not game_object:
				info(f"{base_id} not found in {asset.name}")
				break

			root_object = get_root_object(game_object)
			root_transform = get_transform(root_object)

			tree = Tree()
			traverse_transforms(root_transform, tree)

			# create output directory
			out_dir = os.path.join(args.output, tree.root.name)
			if not os.path.exists(out_dir):
				os.mkdir(out_dir)
			# export the tree as json
			json_str = json.dumps(tree.root, cls=GameObjectEncoder, indent=4)
			write_to_file(os.path.join(out_dir, "data.json"), json_str)
			# extract referenced textures, models and shaders
			extract_assets(tree.root, out_dir)


if __name__ == "__main__":
	main()
