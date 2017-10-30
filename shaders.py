#!/usr/bin/env python

import os
from enum import Enum, auto
from io import BytesIO
from operator import attrgetter
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


class UniformSymbol:
	def __init__(self, name, type, index):
		self.name = name.decode("ascii")
		self.type = type
		self.index = index

	def __str__(self):
		return "%s %d [%d]" % (self.name, self.type, self.index)

	def str_assign(self):
		return "uniform vec4 %s;" % (self.name)

	def str_define(self, is_pixel_shader=False):
		prefix = "ps" if is_pixel_shader else "vs"
		return "#define %s_c%d %s" % (prefix, self.index, self.name)

def extract_shader_attributes(parsed):
	defs = []
	symbols = []
	tex_symbols = []

	is_pixel = True if parsed.shader_type == mojoparser.ShaderType.PIXEL else False

	defs.append("//-- %d Uniforms" % (parsed.uniform_count))
	defs.append("//-- %d Constants" % (parsed.constant_count))
	defs.append("//-- %d Samplers" % (parsed.sampler_count))
	defs.append("//-- %d Attributes" % (parsed.attribute_count))
	defs.append("//-- %d Outputs" % (parsed.output_count))
	defs.append("//-- %d Swizzles" % (parsed.swizzle_count))
	defs.append("//-- %d Symbols\n" % (parsed.symbol_count))

	defs.append("//-- %d Symbols" % (parsed.symbol_count))
	for j in range(parsed.symbol_count):
		sym = UniformSymbol(
			parsed.symbols[j].name,
			parsed.symbols[j].register_set,
			parsed.symbols[j].register_index)
		defs.append("// %s" % (str(sym)))
		if parsed.symbols[j].register_set == mojoparser.SymbolRegisterSet.SAMPLER:
			tex_symbols.append(sym)
		else:
			symbols.append(sym)
	symbols.sort(key=attrgetter("index"))
	tex_symbols.sort(key=attrgetter("index"))
	defs = defs + [s.str_assign() for s in symbols] \
		+ [s.str_define(is_pixel) for s in symbols] \
		+ ["//-- Samplers"] + [str(s) for s in tex_symbols]

	defs.append("//-- %d Attributes" % (parsed.attribute_count))
	for j in range(parsed.attribute_count):
		defs.append("// %s %s %d" % (
			parsed.attributes[j].name,
			mojoparser.Usage(parsed.attributes[j].usage),
			parsed.attributes[j].index))

	defs.append("//-- %d Uniforms" % (parsed.uniform_count))
	for j in range(parsed.uniform_count):
		defs.append("// %s %s %d %d %d" % (
			parsed.uniforms[j].name,
			mojoparser.UniformType(parsed.uniforms[j].type),
			parsed.uniforms[j].array_count, parsed.uniforms[j].index,
			parsed.uniforms[j].constant))

	defs.append("//-- %d Constants" % (parsed.constant_count))
	for j in range(parsed.constant_count):
		defs.append("// %s %d" % (
			mojoparser.UniformType(parsed.constants[j].type),
			parsed.constants[j].index))
		print(*parsed.constants[j].value.f)
		print(*parsed.constants[j].value.i)
		print(parsed.constants[j].value.b)

	defs.append("//-- %d Outputs" % (parsed.output_count))
	for j in range(parsed.output_count):
		defs.append("// %s %s %d" % (
			parsed.outputs[j].name,
			mojoparser.Usage(parsed.outputs[j].usage),
			parsed.outputs[j].index))


	return "\n".join(defs) + "\n\n" + str(parsed).replace("\n", "")


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
			# debug shader attribute data, from parsed bytecode
			debug(extract_shader_attributes(parsed_data))
			# write full subshader blob
			if raw:
				utils.write_to_file(filename + ".bin", sub_bytes, "wb")
				utils.write_to_file(filename + ".co", raw_data, "wb")
