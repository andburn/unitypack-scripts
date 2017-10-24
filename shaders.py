#!/usr/bin/env python

import os
from enum import Enum, auto
from io import BytesIO
import unitypack
from unitypack.engine.object import field
import mojoparser
import utils


class Program(Enum):
	FRAGMENT = auto()
	VERTEX = auto()


class API(Enum):
	D3D9 = auto()
	D3D11 = auto()
	OPENGL = auto()


class ShaderType:
	def __init__(self, prog, api, version):
		self.program = prog
		self.api = api
		self.version = version

	def __str__(self):
		return f"{self.api.name} {self.program.name}"


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
	# TODO more robust replacement of chars
	name = shader.parsed_form.name.replace("/", "_")
	print(f"Extracting '{name}'")
	# create output path for each shader
	out_dir = os.path.join(dir, name) + os.sep
	utils.make_dirs(out_dir)

	compressed = unitypack.utils.BinaryReader(BytesIO(shader.blob))
	# check blob sizes and offsets match up
	assert compressed.buf.getbuffer().nbytes == sum(shader.compressed_sizes)
	assert len(shader.compressed_sizes) == len(shader.decompressed_sizes)
	assert len(shader.compressed_sizes) == len(shader.compressed_offsets)

	# crate object to parse shader bytecode
	bytecode_parser = mojoparser.Parser()
	# decompress each shader format and extract the subprograms
	for i, s in enumerate(shader.compressed_sizes):
		# decompress lz4 frame
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
			# read the subshader bytes
			b = unitypack.utils.BinaryReader(BytesIO(data.read(length)))
			# unity date-stamp, version?
			date_stamp = b.read_int()
			# use the map to retrieve the shader type
			stype_id = b.read_int()
			if stype_id in shader_type_map:
				stype = shader_type_map[stype_id]
			if stype == None or stype.api != API.D3D9:
				print("Skipping unsupported shader type (%s)" % (stype))
				continue
			# XXX unknown series of bytes (12)
			u1, u2, u3 = (b.read_int(), b.read_int(), b.read_int())
			# XXX another four bytes in 5.6
			u4 = b.read_int()
			# the number of associated shader keywords
			keyword_count = b.read_int()
			# get the keyword strings
			keywords = []
			for t in range(keyword_count):
				size = b.read_int()
				keywords.append(b.read_string(size))
				b.align()
			# TODO do something more with keywords?
			# the length of the shader bytecode
			code_len = b.read_int()
			data_out = b.read(code_len)
			# disassemble bytecode to glsl
			try:
				parsed_data = bytecode_parser.parse(data_out)
			except Exception as e:
				print(e)
				continue
			# write glsl code
			file_ext = ".vert" if stype.program == Program.VERTEX else ".frag"
			file_keywords = "_".join(keywords)
			file_name = f"{name}-{file_keywords}{file_ext}"
			utils.write_to_file(os.path.join(out_dir, file_name), str(parsed_data))
			# TODO some other stuff at the end, not sure what it is
			# TODO it is the embedded CTAB (constant table), deal with it
