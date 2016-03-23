import sys
import pickle
import unitypack
from unitypack.export import OBJMesh
from unitypack.engine import Mesh

def write_to_file(filename, contents, mode="w"):
	path = filename
	with open(path, mode) as f:
		written = f.write(contents)


def unpickle(file):
	path = "data/mesh/" + file
	with open(path, 'rb') as f:
		d = Mesh(pickle.load(f))
		mesh = OBJMesh(d).export()
		write_to_file(path + ".obj", mesh)


def main():
	''' Convert some pickled Mesh objects to OBJ '''
	pickles = [
		"single_mtl_5.pickle",
		"two_streams_5.pickle",
		"two_uvs_5.pickle",
		"color_channel_5.pickle"
	]
	for p in pickles:
		unpickle(p)

if __name__ == "__main__":
	main()
