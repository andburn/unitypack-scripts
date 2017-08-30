class Vec2:
	def __init__(self, x=0, y=0):
		self.x = x
		self.y = y

	def __str__(self):
		return "({0:.5f}, {1:.5f})".format(self.x, self.y)

	def to_json(self):
		return { "x": self.x, "y": self.y}


class Vec3(Vec2):
	def __init__(self, x=0, y=0, z=0):
		super().__init__(x, y)
		self.z = z

	def __str__(self):
		return "({0:.5f}, {1:.5f}, {2:.5f})".format(self.x, self.y, self.z)

	def to_json(self):
		return { "x": float("{0:.5f}".format(self.x)), "y": float("{0:.5f}".format(self.y)), "z": float("{0:.5f}".format(self.z)) }


class Vec4(Vec3):
	def __init__(self, x=0, y=0, z=0, w=0):
		super().__init__(x, y, z)
		self.w = w

	def __str__(self):
		return "({0:.5f}, {1:.5f}, {2:.5f}, {3:.5f})".format(self.x, self.y, self.z, self.w)

	def to_json(self):
		return { "x": float("{0:.5f}".format(self.x)), "y": float("{0:.5f}".format(self.y)), "z": float("{0:.5f}".format(self.z)), "w": float("{0:.5f}".format(self.w)) }


class Color(Vec4):
	def __init__(self, x=0, y=0, z=0, w=0):
		super().__init__(x, y, z, w)
		self.r = x
		self.g = y
		self.b = z
		self.a = w

	def __str__(self):
		return super().__str__()

	def to_json(self):
		return { "r": self.r, "g": self.g, "b": self.b, "a": self.a }


'''
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
'''
class JSONMesh:
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
