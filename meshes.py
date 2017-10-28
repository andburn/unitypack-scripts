
class BabylonMesh:
	"""JSON Mesh format defined by Babylon.js"""

	def __init__(self, mesh):
		from unitypack.export import MeshData

		if mesh.mesh_compression:
			# TODO handle compressed meshes
			raise NotImplementedError("(%s) compressed meshes are not supported" % (mesh.name))
		self.mesh_data = MeshData(mesh)
		self.mesh = mesh
		self.name = mesh.name

	@staticmethod
	def vec2_list(vec):
		return [vec.x, 1 - vec.y]

	@staticmethod
	def vec3_list(vec):
		return [-vec.x, vec.y, vec.z]

	@staticmethod
	def vec4_list(vec):
		return [vec.x, vec.y, vec.z, vec.w]

	@staticmethod
	def add_uv(uvs, uv):
		out = []
		for u in uv:
			out.extend(JSONMesh.vec2_list(u))
		if out:
			uvs.append(out)

	@staticmethod
	def uv_list(uv):
		out = []
		for u in uv:
			out.extend(JSONMesh.vec2_list(u))
		return out

	@staticmethod
	def face_list(indices, type, id):
		ret = [type]
		triple = []
		for i in indices[::-1]:
			triple.append(i)
		ret.extend(triple)
		ret.append(id)
		ret.extend(triple)
		ret.extend(triple)
		return ret

	def export(self):
		import json

		# check all elements exists
		# TODO empty arrays won't match here
		# if not self.mesh_data.vertices or not self.mesh_data.normals or \
		# 		not self.mesh_data.uv1 or not self.mesh_data.indices:
		# 	raise RuntimeError("%s is missing some required elements" % self.mesh.name)
		vertices = []
		uvs = []
		faces = []
		normals = []
		colors = []
		indices = []
		for v in self.mesh_data.vertices:
			vertices.extend(self.vec3_list(v))
		for n in self.mesh_data.normals:
			normals.extend(self.vec3_list(n))
		for c in self.mesh_data.colors:
			colors.extend(self.vec4_list(c))
		for x in self.mesh_data.indices:
			indices.extend(x)

		# verts_per_face = 3
		# face_type = 42
		# sub_count = len(self.mesh.submeshes)
		# for i in range(0, sub_count):
		# 	face_tri = []
		# 	for t in self.mesh_data.triangles[i]:
		# 		face_tri.append(t)
		# 		if len(face_tri) == verts_per_face:
		# 			faces.extend(self.face_list(face_tri, face_type, i))
		# 			face_tri = []

		mesh = {
			"name": self.name,
			"id": self.name,
			"tags": "",
			"parentId": None,
			"materialId": None,
			"position": [0, 0, 0],
			"rotation": [0, 0, 0],
			"scaling": [1, 1, 1],
			"isVisible": True,
			"isEnabled": True,
			"billboardMode": 0,
			"receiveShadows": False,
			"positions": vertices,
			"normals": normals,
			"uvs": self.uv_list(self.mesh_data.uv1),
			"indices": indices,
			"subMeshes": [{
					"materialIndex": 0,
					"verticesStart": 0,
					"verticesCount": int(len(vertices) / 3),
					"indexStart": 0,
					"indexCount": len(indices)
				}
			],
			"instances": []
		};
		if self.mesh_data.uv2:
			mesh["uvs2"] = self.uv_list(self.mesh_data.uv2)
		if colors:
			mesh["colors"] = colors

		babylon = {
			"autoClear": True,
			"clearColor": [0.5, 0.5, 0.7],
			"ambientColor": [0, 0, 0],
			"gravity": [0,-9,0],
			"cameras": [],
			"lights": [],
			"materials": [],
			"multiMaterials": [],
			"meshes": [mesh],
			"shadowGenerators": [],
			"skeletons": []
		}

		print(f"v {len(mesh['positions'])/3} n {len(mesh['normals'])/3} i {len(mesh['indices'])/3} uv {len(mesh['uvs'])/2}")

		return json.dumps(babylon)



class JSONMesh:
	"""JSON Mesh format defined by Three.js

	{
		"metadata": {
			"version": 4,
			"type": "Geometry",
			"generator": "GeometryExporter"
		},
		"data": {
			"indices": [0,1,2,...],
			"vertices": [50,50,50,...],
			"normals": [1,0,0,...],
			"uvs": [0,1,...]
		}
	}
	"""
	def __init__(self, mesh):
		from unitypack.export import MeshData

		if mesh.mesh_compression:
			# TODO handle compressed meshes
			raise NotImplementedError("(%s) compressed meshes are not supported" % (mesh.name))
		self.mesh_data = MeshData(mesh)
		self.mesh = mesh

	@staticmethod
	def vec2_list(vec):
		# TODO check Three.js uv fix thingy
		return [vec.x, 1 - vec.y]

	@staticmethod
	def vec3_list(vec):
		return [-vec.x, vec.y, vec.z]

	@staticmethod
	def vec4_list(vec):
		return [vec.x, vec.y, vec.z, vec.w]

	@staticmethod
	def add_uv(uvs, uv):
		out = []
		for u in uv:
			out.extend(JSONMesh.vec2_list(u))
		if out:
			uvs.append(out)

	@staticmethod
	def face_list(indices, type, id):
		ret = [type]
		triple = []
		for i in indices[::-1]:
			triple.append(i)
		ret.extend(triple)
		ret.append(id)
		ret.extend(triple)
		ret.extend(triple)
		return ret

	def export(self):
		import json

		# check all elements exists
		if not self.mesh_data.vertices or not self.mesh_data.normals or \
				not self.mesh_data.uv1 or not self.mesh_data.indices:
			raise RuntimeError("%s is missing some required elements" % self.mesh.name)
		vertices = []
		uvs = []
		faces = []
		normals = []
		colors = []
		for v in self.mesh_data.vertices:
			vertices.extend(self.vec3_list(v))
		for n in self.mesh_data.normals:
			normals.extend(self.vec3_list(n))
		for c in self.mesh_data.colors:
			colors.extend(self.vec4_list(c))

		self.add_uv(uvs, self.mesh_data.uv1)
		self.add_uv(uvs, self.mesh_data.uv2)
		self.add_uv(uvs, self.mesh_data.uv3)
		self.add_uv(uvs, self.mesh_data.uv4)

		verts_per_face = 3
		face_type = 42
		sub_count = len(self.mesh.submeshes)
		for i in range(0, sub_count):
			face_tri = []
			for t in self.mesh_data.triangles[i]:
				face_tri.append(t)
				if len(face_tri) == verts_per_face:
					faces.extend(self.face_list(face_tri, face_type, i))
					face_tri = []

		mesh = {
			"metadata": { "version": 4, "type": "Geometry" },
			"indices": self.mesh_data.indices,
			"vertices": vertices,
			"uvs": uvs,
			"faces": faces,
			"normals": normals,
			"colors": colors
		}
		return json.dumps(mesh)
