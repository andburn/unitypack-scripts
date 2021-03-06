#!/usr/bin/env python

import os
from enum import Enum, auto
from io import BytesIO
from operator import attrgetter
import unitypack
from unitypack.engine.object import field
import mojoparser
import utils
import glsl_parser
from glsl_objects import Define, Declare, Assignment


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


def convert_register_set(register_set):
	set_text = ""
	if register_set == mojoparser.SymbolRegisterSet.BOOL:
		set_text = "bool"
	elif register_set == mojoparser.SymbolRegisterSet.INT4:
		set_text = "ivec4"
	elif register_set == mojoparser.SymbolRegisterSet.FLOAT4:
		set_text = "vec4"
	elif register_set == mojoparser.SymbolRegisterSet.SAMPLER:
		set_text = "sampler2D"
	return set_text


class SymbolMap:
	def __init__(self, id, name, expr):
		self.id = id
		self.name = name
		self.expr = expr

	def __repr__(self):
		return "SymbolMap(id={}, name={}, expr={})".format(
			self.id, self.name, self.expr
		)


def create_attribute_map(parsed):
	"""Create a map of generated symbol names to actual symbol names"""

	symbol_map = {}
	uniform_mat_ids = []

	is_frag = False
	if parsed.shader_type == mojoparser.ShaderType.PIXEL:
		is_frag = True

	for i in range(parsed.symbol_count):
		is_sampler = parsed.symbols[i].register_set == mojoparser.SymbolRegisterSet.SAMPLER
		index = parsed.symbols[i].register_index
		id = "{}_{}{}".format(
			"ps" if is_frag else "vs",
			"s" if is_sampler else "c",
			index,
		)
		name = parsed.symbols[i].name.decode("utf-8")
		type = convert_register_set(parsed.symbols[i].register_set)
		# XXX yuck!
		# the unity uniforms are matrices, but are used as 4 column vectors
		if name[:6] == "unity_":
			type = "mat4"
			# store the uniforms that are part of this matrix
			for r in range(index, index + 4):
				uniform_mat_ids.append("vs_c{}".format(r))
		exp = "uniform {} {};".format(type, name,)
		symbol_map[id] = SymbolMap(id, name, exp)

	for i in range(parsed.output_count):
		id = parsed.outputs[i].name.decode("utf-8")
		usage = mojoparser.Usage(parsed.outputs[i].usage)
		if usage == mojoparser.Usage.POSITION:
			name = "gl_Position"
			exp = None
		elif usage == mojoparser.Usage.TEXCOORD:
			name = "_TexCoord{}".format(parsed.outputs[i].index)
			exp = "varying vec2 {};".format(name)
		else:
			# XXX probably!
			name = "gl_FragColor"
			exp = None
		symbol_map[id] = SymbolMap(id, name, exp)

	for i in range(parsed.attribute_count):
		id = parsed.attributes[i].name.decode("utf-8")
		usage = mojoparser.Usage(parsed.attributes[i].usage)
		if usage == mojoparser.Usage.POSITION:
			name = "position"
			exp = "attribute vec2 position;"
		elif usage == mojoparser.Usage.TEXCOORD:
			idx = parsed.attributes[i].index
			name = "uv{}".format(idx + 1 if idx > 0 else "")
			exp = "attribute vec2 {};".format(name)
		else:
			raise AttributeError("Unable to handle " + id)
		symbol_map[id] = SymbolMap(id, name, exp)

	# sanity check on uniforms
	for i in range(parsed.uniform_count):
		name = parsed.uniforms[i].name.decode("utf-8")
		if not name in symbol_map and not name in uniform_mat_ids:
			id = parsed.uniforms[i].index
			new_name = "_Unkown{}".format(id)
			print("symbol for uniform '{}' [{}] not found".format(name, index))
			# TODO only 'vs_c255' falls in here, where is it coming from?
			# this looks to be some sort of error in mojoparser
			# set is to identity vector for now
			symbol_map[name] = SymbolMap(name, new_name, "uniform vec4 {};".format(new_name))

	return symbol_map


def clean_up(parsed_data, tags):
	# get shader attribute data, from the parsed data
	symbol_map = create_attribute_map(parsed_data)
	# pass through a text parser, for fine tuning
	parsed_glsl, idents = glsl_parser.parse(str(parsed_data))
	# replace declarations
	declarations = []
	for d in parsed_glsl.declarations:
		if isinstance(d, Define):
			if "ps_v" in d.dest.name and not d.dest.name in symbol_map:
				id = d.dest.name[4:]
				name = "_TexCoord" + id
				symbol_map[d.dest.name] = SymbolMap(
					d.dest.name, name,
					"varying vec2 {};".format(name)
				)
			continue
		elif isinstance(d, Declare) and (d.qualifier == "uniform" or d.qualifier == "attribute"):
			continue
		else:
			declarations.append("{!s}".format(d))
	# fix symbols/uniforms/attributes
	for id, sym in symbol_map.items():
		if id in idents:
			for i in idents[id]:
				i.name = sym.name
		if sym.expr:
			declarations.append(sym.expr)

	return glsl_parser.build(parsed_glsl, version="300", keywords=tags, declarations=declarations)


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
			# process DX9 shaders only
			if stype.api == API.D3D9:
				# final clean up to prepare glsl for webgl
				prog_text = clean_up(parsed_data, keywords)
				# write to file
				utils.write_to_file(filename + ext, prog_text)
			# write keywords to file
			if keywords:
				utils.write_to_file(filename + ".tags", "\n".join(keywords))
			# write full subshader blob
			if raw:
				utils.write_to_file(filename + ".bin", sub_bytes, "wb")
				utils.write_to_file(filename + ".co", raw_data, "wb")
