import os
import sys

import unitypack
import argparse

from utils import vec_from_dict


quiet_print = False

def qprint(string):
	global quiet_print
	if not quiet_print:
		print(string)


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


class Texture:
	def __init__(self, name, obj):
		self.name = name
		self.pointer = obj["m_Texture"]
		self.scale = vec_from_dict(obj["m_Scale"])
		self.offset = vec_from_dict(obj["m_Offset"])

	def __str__(self):
		return f"{self.name} {self.scale} {self.offset}"



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


	def __str__(self):
		return f"<Material> ({self.name}, {self.shader})"


class Mesh:
	def __init__(self, pointer):
		self.pointer = pointer
		self.object = pointer.resolve()
		self.name = self.object.name

	def __str__(self):
		return f"<Mesh> {self.name}"


class GameObject(Node):
	def __init__(self, game_object, transform):
		super().__init__(game_object.name)
		self.transform = Transform(transform)
		self.mesh = None
		self.materials = []
		self.scripts = []
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
					qprint("Unknown component")
			except AttributeError:
				if "m_Script" in comp:
					self.scripts.append(
						comp["m_Script"].resolve()["m_ClassName"])
				else:
					qprint("Component error")



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


def main():
	arg_parser = argparse.ArgumentParser()
	arg_parser.add_argument("dir",
		help="the directory containing the unity3d files")
	arg_parser.add_argument("bundle",
		help="the unity3d file containing the asset")
	arg_parser.add_argument("id",
		help="the id of the base asset")
	arg_parser.add_argument("--quiet", action="store_true")
	args = arg_parser.parse_args(sys.argv[1:])

	global quiet_print
	quiet_print = args.quiet

	base_id = int(args.id)

	with open(os.path.join(args.dir, args.bundle + ".unity3d"), "rb") as f:
		bundle = unitypack.load(f)
	for asset in bundle.assets:
		print(asset.asset_refs)
		game_object = get_by_id(base_id, asset)
		if not game_object:
			print(f"{base_id} not found in {asset.name}")
			break

		root_object = get_root_object(game_object)
		root_transform = get_transform(root_object)

		tree = Tree()
		traverse_transforms(root_transform, tree)
		tree.print()


if __name__ == "__main__":
	main()
