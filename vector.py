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


def vec_from_dict(d, precision=None):
	dim = len(d)
	if dim == 2:
		return Vec2(d["x"], d["y"])
	elif dim == 3:
		return Vec3(d["x"], d["y"], d["z"])
	elif dim == 4:
		if "x" in d:
			return Vec4(d["x"], d["y"], d["z"], d["w"])
		elif "r" in d:
			return Color(d["r"], d["g"], d["b"], d["a"])
