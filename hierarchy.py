import sys
import os
import shutil
import sqlite3
import json
import unitypack
import utils.serializer as serializer
import utils.file as utils
import vector
import argparse


class Row:
	def __init__(self, r):
		if len(r) == 5:
			self.fid = r[0]
			self.name = r[1]
			if not self.name or self.name == "unknown":
				self.name = None
			self.bundle = r[2]
			self.type = r[3]
			self.obj = serializer.deserialize(r[4])

	def __str__(self):
		return "{2} {0} ({1}, {3})".format(self.type, self.fid, self.name, self.bundle)

	def to_json(self):
		return { "name": self.name, "bundle": self.bundle, "id": self.fid }


class GameObject:
	def __init__(self, row=None):
		self.__set_defaults()
		if row:
			self.name = row.name
			self.id = row.fid
			self.bundle = row.bundle

	def __set_defaults(self):
		self.name = None
		self.id = None
		self.bundle = None
		self.mesh = None
		self.transform = None
		self.materials = []
		self.children = []

	def __str__(self):
		return "GameObject: {0} ({1})".format(self.name, self.id)

	def to_json(self):
		return { "name": self.name , "transform": self.transform, "mesh": self.mesh,
			"materials": self.materials, "children": self.children }


class Transform:
	def __init__(self, obj):
		self.position = vector.vec_from_dict(obj["m_LocalPosition"])
		self.rotation = vector.vec_from_dict(obj["m_LocalRotation"])
		self.scale = vector.vec_from_dict(obj["m_LocalScale"])

	def __str__(self):
		return "Transform: P{0}".format(self.position)

	def to_json(self):
		return { "position": self.position, "rotation": self.rotation, "scale": self.scale }


class Texture:
	def __init__(self, obj):
		self.name = obj[0]["name"]
		s = obj[1]
		self.scale = vector.vec_from_dict(s["m_Scale"])
		self.offset = vector.vec_from_dict(s["m_Offset"])
		self.obj = resolve_ptr(s, "m_Texture")

	def __str__(self):
		return "Texture: {0} ({1}, {2})".format(self.name, self.obj.bundle, self.obj.name)

	def to_json(self):
		return { "name": self.name, "file": self.obj, "scale": self.scale, "offset": self.offset }


# TODO textures should be dict too
class Material:
	def __init__(self, obj):
		self.name = obj["m_Name"]
		self.shader = resolve_ptr(obj, "m_Shader")
		self.shader_tags = obj["m_ShaderKeywords"]
		self.textures = []
		self.uniforms = {}
		tenv = obj["m_SavedProperties"]["m_TexEnvs"]
		for t in tenv:
			self.textures.append(Texture(t))
		vecs = obj["m_SavedProperties"]["m_Colors"]
		for v in vecs:
			name = v[0]["name"]
			self.uniforms[name] = vector.vec_from_dict(v[1])
		flts = obj["m_SavedProperties"]["m_Floats"]
		for f in flts:
			name = f[0]["name"]
			# TODO round floats
			self.uniforms[name] = f[1]

	def __str__(self):
		return "Material: {0} ({1})".format(self.name, self.shader.name)

	def to_json(self):
		return { "name": self.name, "textures": self.textures, "uniforms": self.uniforms,
			"shader": self.shader, "tags": self.shader_tags}


class GameObjectEncoder(json.JSONEncoder):
	def default(self, obj):
		if hasattr(obj, "to_json"):
			return obj.to_json()
		else:
			print("%r does not implement to_json()" % (obj))
			return json.JSONEncoder.default(self, obj)


def get_by_id(id):
	''' Query the db for matching id, should be only a single row '''
	fid = '"%s"' % (id)
	cursor.execute("SELECT * FROM assets WHERE fid MATCH ?", [fid])
	rows = cursor.fetchall()

	count = len(rows)
	if count > 1:
		print("WARNING: multiple records found for %s" % fid)
	elif count <= 0:
		return None

	return Row(rows[0])


#TODO tidy this
def resolve_ptr(obj, field):
	if not obj or not field:
		return None
	o = obj
	if isinstance(obj, Row):
		o = obj.obj
	if o[field]:
		return get_by_id(o[field][1])
	return None


def resolve_material(ref):
	if not ref:
		return
	mat = get_by_id(ref[1])
	if mat:
		return mat.obj


# ??? what was this for
def resolve_material_debug(mat):
	print(mat)
	m = get_by_id(mat[1])
	print("\t\tMT", m)
	sh = resolve_ptr(m, "m_Shader")
	print("\t\tMT", sh)
	mt = Material(m.obj)
	for t in mt.textures:
		print("\t\tMTt", get_by_id(t)) # if not None


def add_component(comp, go):
	if comp.type == "MeshFilter":
		go.mesh = resolve_ptr(comp, "m_Mesh")
	elif comp.type == "MeshRenderer":
		materials = comp.obj["m_Materials"]
		for m in materials:
			mat = resolve_material(m)
			if mat:
				go.materials.append(Material(mat))
	elif comp.type == "Transform":
		go.transform = Transform(comp.obj)
	# TODO deal with other components



def traverse_components(go, node):
	if go.type != "GameObject":
		print("Need a GameObject to traverse")
		return
	current = GameObject(go)
	node.children.append(current)

	transform = None
	# run through all components, save transform until after
	for item in go.obj["m_Component"]:
		comp = resolve_ptr(item, 1)
		add_component(comp, current)
		if comp.type == "Transform":
			transform = comp

	# process children after components
	if transform:
		for child in transform.obj["m_Children"]:
			child_tr = get_by_id(child[1])
			child_go = resolve_ptr(child_tr, "m_GameObject")
			traverse_components(child_go, current)


def find_root(id):
	''' Given a GameObject id find the root GameObject object '''
	start = get_by_id(id)
	if not start:
		print("find_root: not found", id)
		return

	root = [None]
	if start.type == "GameObject":
		comps = start.obj["m_Component"]
		for c in comps:
			if c[0] == 4:
				traverse_transform(c[1][1], root)

	if not root[0]:
		print("find_root: traversal failed for", id)
		return

	go = resolve_ptr(root[0], "m_GameObject")
	print("Root:", go, "[ Transform:", root[0].fid, "]\n")

	return go


def traverse_transform(id, holder):
	''' Traverse up towards root along Transform hierarchy '''
	d = get_by_id(id)

	if not d:
		print("traverse_transform: not found", id)
		return

	if d.type == "Transform":
		parent = d.obj["m_Father"]
		children = d.obj["m_Children"]
		if not parent:
			# no parent => top, set root
			holder[0] = d
		else:
			# recursive call on parent
			traverse_transform(parent[1], holder)


def traverse(root):
	print(root)
	for comp in root.components:
		print(comp)
	for child in root.children:
		traverse(child)


def gather_assets(node, assets):
	if node.mesh:
		assets.append("%s/Mesh/%s.js" % (node.mesh.bundle, node.mesh.name))
		assets.append("%s/Mesh/%s.obj" % (node.mesh.bundle, node.mesh.name))
	if len(node.materials) > 0:
		for m in node.materials:
			if m.shader:
				assets.append("%s/Shader/%s.shaderlab" % (m.shader.bundle, m.shader.name))
				assets.append("%s/Shader/%s.bin" % (m.shader.bundle, m.shader.name))
			for t in m.textures:
				if not t.obj:
					print("WARNING texture missing obj attribute (%s)" % (t.name))
				else:
					assets.append("%s/Texture2D/%s.png" % (t.obj.bundle, t.obj.name))

	for child in node.children:
		gather_assets(child, assets)


def main():
	p = argparse.ArgumentParser()
	p.add_argument("database")
	p.add_argument("assets")
	p.add_argument("id")
	p.add_argument("output")
	args = p.parse_args(sys.argv[1:])

	db = args.database
	assets_dir = args.assets
	go_id = args.id
	out_dir = args.output

	if not os.path.exists(out_dir):
		os.makedirs(out_dir)

	conn = sqlite3.connect(db)

	global cursor
	cursor = conn.cursor()

	# find root object of go_id (should be id of a GameObject)
	go = find_root(go_id)

	# descend from root, GameObject
	root = GameObject()
	root.name = "Root"
	traverse_components(go, root)

	# print tree out
	#traverse(root)
	# dump json
	json_str = json.dumps(root.children[0], cls=GameObjectEncoder, sort_keys=True, indent=4)
	json_path = os.path.join(out_dir, "data.js")
	utils.write_to_file(json_path, json_str)

	# gather assests
	asset_list = []
	gather_assets(root, asset_list)
	for asset in asset_list:
		src = os.path.join(assets_dir, asset)
		shutil.copy(src, out_dir)


	conn.close()


if __name__ == "__main__":
	main()
