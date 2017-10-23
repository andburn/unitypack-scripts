#!/usr/bin/env python

import os
from enum import Enum, auto
from collections import namedtuple
from io import BytesIO
import unitypack
from unitypack.engine.object import field
import utils


class Program(Enum):
	FRAGMENT = auto()
	VERTEX = auto()


class API(Enum):
	D3D9 = auto()
	D3D11 = auto()
	OPENGL = auto()


ShaderType = namedtuple("ShaderType", "program api version")


shader_type_map = {
	9: ShaderType(Program.VERTEX, API.D3D9, 2.0),
	10: ShaderType(Program.VERTEX, API.D3D9, 3.0),
	11: ShaderType(Program.FRAGMENT, API.D3D9, 2.0),
	12: ShaderType(Program.FRAGMENT, API.D3D9, 3.0),

	15: ShaderType(Program.VERTEX, API.D3D11, 2.0),
	16: ShaderType(Program.VERTEX, API.D3D11, 3.0),
	17: ShaderType(Program.FRAGMENT, API.D3D11, 2.0),
	18: ShaderType(Program.FRAGMENT, API.D3D11, 3.0),
}


class ParsedForm(unitypack.engine.object.Object):
	"""Define the basic properties of the parsed Shaderlab file in 5.6+"""
	name = field("m_Name")
	ed_name = field("m_CustomEditorName")
	fallback_name = field("m_FallbackName")
	prop_info = field("m_PropInfo")
	dependencies = field("m_Dependencies")


def redefine_shader():
	"""Redefine the UnityPack Shader object for 5.6+"""
	from unitypack.engine import Shader

	Shader.script = None
	Shader.path_name = None
	Shader.dependencies = field("m_Dependencies")
	Shader.decompressed_sizes = field("decompressedLengths")
	Shader.compressed_sizes = field("compressedLengths")
	Shader.compressed_offsets = field("offsets")
	Shader.platforms = field("platforms")
	Shader.is_baked = field("m_ShaderIsBaked", bool)
	Shader.blob = field("compressedBlob")
	Shader.parsed_form = field("m_ParsedForm", ParsedForm)


# TODO better!
def supported_shader_asset(obj):
	try:
		obj.parsed_form
		obj.compressed_sizes
		obj.compressed_offsets
		obj.blob
		return True
	except KeyError:
		return False


def extract_shader(shader, dir):
	if not supported_shader_asset(shader):
		print("The shader asset has an unsupported format")
		return
	name = shader.parsed_form.name.replace("/", "_")
	print(f"Extracting '{name}'")
	# create output path for each shader
	out_dir = os.path.join(dir, name) + os.sep
	utils.make_dirs(out_dir)

	compressed = unitypack.utils.BinaryReader(BytesIO(shader.blob))
	assert compressed.buf.getbuffer().nbytes == sum(shader.compressed_sizes)
	assert len(shader.compressed_sizes) == len(shader.decompressed_sizes)
	assert len(shader.compressed_sizes) == len(shader.compressed_offsets)

	for i, s in enumerate(shader.compressed_sizes):
		# decompress lz4 frames
		compressed.seek(shader.compressed_offsets[i])
		uncompressed = unitypack.utils.lz4_decompress(
			compressed.read(s), shader.decompressed_sizes[i]
		)

		data = unitypack.utils.BinaryReader(BytesIO(uncompressed))

		# read header for subshader offsets and lengths
		index = []
		num_subprograms = data.read_int()
		for i in range(num_subprograms):
			index.append((data.read_int(), data.read_int()))

		# extract each subshader
		for offset, length in index:
			data.seek(offset)
			sdata = data.read(length)
			b = unitypack.utils.BinaryReader(BytesIO(sdata))
			# unknown, seems to be same for all shaders, version date/time-stamp
			sid = b.read_int()
			# use the map to retrieve the shader type
			stype_id = b.read_int()
			if stype_id in shader_type_map:
				stype = shader_type_map[stype_id]
			if stype == None or stype.api != API.D3D9:
				print("Skipping unsupported shader type (%d)" % (stype_id))
				continue
			# XXX unknown series of bytes (12)
			u2, u3, u4 = (b.read_int(), b.read_int(), b.read_int())
			# the number of associated shader keywords
			num_tags = b.read_int()
			# get the tag strings
			# TODO do something better with tags
			tags = []
			for t in range(num_tags):
				size = b.read_int()
				tags.append(b.read_string(size))
				b.align()
			# the length of the shader bytecode
			length = b.read_int()
			# read bytecode
			file_ext = ".vert" if stype.program == Program.VERTEX else ".frag"
			file_tags = "_".join(tags)
			file_name = f"{name}-{file_tags}{file_ext}"
			data_out = b.read(length)
			utils.write_to_file(os.path.join(out_dir, file_name), data_out, "wb", False, True)
			# TODO some other stuff at the end, not sure what it is
			# TODO it is the embedded CTAB (constant table), deal with it
