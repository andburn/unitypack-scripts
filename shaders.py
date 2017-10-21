#!/usr/bin/env python

import os
from enum import Enum, auto
from io import BytesIO
import unitypack
from unitypack.engine.object import field
import mojoparser
import utils


(debug, info, error) = utils.Echo.echo()


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

	15: ShaderType(Program.VERTEX, API.D3D11, 4.0),
	16: ShaderType(Program.VERTEX, API.D3D11, 5.0),
	17: ShaderType(Program.FRAGMENT, API.D3D11, 4.0),
	18: ShaderType(Program.FRAGMENT, API.D3D11, 5.0),
}


class ParsedForm(unitypack.engine.object.Object):
	"""Define the basic properties of the parsed Shaderlab file in 5.6"""
	name = field("m_Name")
	ed_name = field("m_CustomEditorName")
	fallback_name = field("m_FallbackName")
	prop_info = field("m_PropInfo")
	dependencies = field("m_Dependencies")


def redefine_shader():
	"""Redefine the UnityPack Shader object for 5.6"""
	from unitypack.engine import Shader

	Shader.script = None
	Shader.dependencies = field("m_Dependencies")
	Shader.decompressed_sizes = field("decompressedLengths")
	Shader.compressed_sizes = field("compressedLengths")
	Shader.compressed_offsets = field("offsets")
	Shader.platforms = field("platforms")
	Shader.is_baked = field("m_ShaderIsBaked", bool)
	Shader.blob = field("compressedBlob")
	Shader.parsed_form = field("m_ParsedForm", ParsedForm)


def shader_has_compatible_props(obj):
	"""Check if object has the properties we expect from a shader"""
	try:
		obj.parsed_form
		obj.compressed_sizes
		obj.compressed_offsets
		obj.blob
		return True
	except KeyError:
		return False


def extract_shader(shader, dir, raw=False):
	if not shader_has_compatible_props(shader):
		error("The shader asset has an unsupported format")
		return

	# create output path for each shader
	name = os.path.basename(shader.parsed_form.name)
	path = os.path.normpath(os.path.join(dir, shader.parsed_form.name))
	os.makedirs(path, exist_ok=True)

	info(f"Extracting '{shader.parsed_form.name}'")
	compressed = unitypack.utils.BinaryReader(BytesIO(shader.blob))
	# check blob sizes and offsets match up
	assert compressed.buf.getbuffer().nbytes == sum(shader.compressed_sizes)
	assert len(shader.compressed_sizes) == len(shader.decompressed_sizes)
	assert len(shader.compressed_sizes) == len(shader.compressed_offsets)

	# create shader bytecode parser object
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
		count = 0
		for offset, length in index:
			data.seek(offset)
			# read the subshader bytes
			sub_bytes = data.read(length)
			b = unitypack.utils.BinaryReader(BytesIO(sub_bytes))
			# unity date-stamp, version?
			date_stamp = b.read_int()
			# use the map to retrieve the shader type
			stype_id = b.read_int()
			if stype_id in shader_type_map:
				stype = shader_type_map[stype_id]
			if stype == None:
				info(f"Skipping unsupported type ({stype}) @ {offset}")
				continue
			# XXX unknown series of bytes (12)
			u1, u2, u3 = (b.read_int(), b.read_int(), b.read_int())
			# XXX another four bytes in 5.6 ?
			u4 = b.read_int()
			# the number of associated shader keywords
			keyword_count = b.read_int()
			# get the keyword strings
			keywords = []
			for t in range(keyword_count):
				size = b.read_int()
				keywords.append(b.read_string(size))
				b.align()
			debug(f"subprogram ({stype}) @ {offset} [{' '.join(keywords)}]")
			# read the bytecode data
			raw_data = b.read(b.read_int())

			# NOTE after the shader bytecode there is a section that looks to be
			#	the shader properties or constants, unable to figure out the
			#	format. Don't think its necesssary as the bytecode has an
			#	embeded constant table 'CTAB'

			# TODO match up verts and frags, and name better
			# disassemble DX9 bytecode
			if stype.api == API.D3D9:
				try:
					parsed_data = bytecode_parser.parse(raw_data, mojoparser.Profile.GLSL110)
				except mojoparser.ParseFailureError as err:
					error(f"'{name}': {err}")
					debug("\n".join(err.errors))
					continue
			# set the filename
			filename = os.path.join(path, f"{name}.{stype.api}.{offset}")
			ext = ".vert" if stype.program == Program.VERTEX else ".frag"
			# write DX9 shaders to file
			if stype.api == API.D3D9:
				utils.write_to_file(filename + ext, str(parsed_data))
			# write keywords to file
			if keywords:
				utils.write_to_file(filename + ".tags", "\n".join(keywords))
			# write full subshader blob
			if raw:
				utils.write_to_file(filename + ".bin", sub_bytes, "wb")
				utils.write_to_file(filename + ".co", raw_data, "wb")
