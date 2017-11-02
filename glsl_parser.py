#!/usr/bin/env python

"""A limited GLSL parser, specifically handles mojoshaders GLSL output"""

import os
import sys
from collections import namedtuple
from pyparsing import (
	Suppress, Word, Literal, OneOrMore, ZeroOrMore, Optional, Combine, SkipTo,
	Group, delimitedList, oneOf, alphas, alphanums, nums, StringEnd, Forward,
	ParseException
)


LBRACE, RBRACE, LBRACK, RBRACK = map(Suppress, "{}[]")
PLUS, DASH, SLASH, ASTERIX, PERCENT, EQ, DOT = map(Literal, "+-/*%=.")
COLON, SEMI, COMMA, HASH, QUESTION = map(Suppress, ":;,#?")
CARET, BAR, AMPERSAND, TILDE = map(Suppress, "^|&~")
LESS, GREAT, LPAR, RPAR, BANG = map(Literal, "<>()!")


class Identifier:
	def __init__(self, name, index, swizzle):
		self.name = name
		self.index = None
		self.swizzle = None
		# index and swizzle stored as list,
		# but should only have one element
		if index and len(index) == 1:
			self.index = index[0]
		if swizzle and len(swizzle) == 1:
			self.swizzle = swizzle[0]

	def __repr__(self):
		r = ["Ident(name=", self.name]
		if self.index:
			r.append(", index={}".format(self.index))
		if self.swizzle:
			r.append(", swizzle={}".format(self.swizzle))
		r.append(")")
		return "".join(r)

	def __str__(self):
		s = [self.name]
		if self.index:
			s.extend(["[", self.index[0], "]"])
		if self.swizzle:
			s.extend([".", self.swizzle[0]])
		return "".join(s)


class Define:
	def __init__(self, dest, src):
		self.src = src
		self.dest = dest

	def __repr__(self):
		return f"Define(dest={self.dest} src={self.src})"

	def __str__(self):
		return f"#define {self.dest} {self.src}"


class Declare:
	def __init__(self, qualifier, dtype, ident, value=None):
		self.qualifier = qualifier
		self.type = dtype
		self.ident = ident
		self.value = value

	def __repr__(self):
		return f"Declare(qual={self.qualifier} type={self.type} ident={self.ident} value={self.value})"

	def __str__(self):
		s = []
		if self.qualifier:
			s.append(self.qualifier)
		s.append(self.type)
		s.append(str(self.ident))
		if self.value:
			s.extend(["=", str(self.value)])
		return " ".join(s) + ";"


class Assignment:
	def __init__(self, dtype, value):
		self.type = dtype
		self.value = value

	def __repr__(self):
		return f"Assign(type={self.type}, value={self.value})"

	def __str__(self):
		values = ", ".join(map(str, self.value))
		return f"{self.type}({values})"


class Function:
	def __init__(self, name, params):
		self.name = name
		self.params = params

	def __repr__(self):
		return "Func(name={}, params={})".format(self.name, self.params)

	def __str__(self):
		return "{}({})".format(self.name, ", ".join(map(str, self.params)))


class Instruction:
	def __init__(self, ident, expr):
		self.ident = ident
		self.expression = expr

	def __repr__(self):
		return "Ins(ident={}, expr={})".format(self.ident, self.expression)

	def __str__(self):
		return "{} = {};".format(self.ident, " ".join(map(str, self.expression)))


class Unary:
	def __init__(self, op, param):
		self.operation = op
		self.param = param

	def __repr__(self):
		return "Unary(op={}, expr={})".format(self.operation, self.param)

	def __str__(self):
		return "{}{}".format(self.operation, self.param)


class Binary:
	def __init__(self, op, paraml, paramr):
		self.operation = op
		self.param_left = paraml
		self.param_right = paramr

	def __repr__(self):
		return "Binary(op={} pl={} pr={}".format(self.operation, self.param_left, self.param_right)

	def __str__(self):
		return "{1} {0} {2}".format(self.operation, self.param_left, self.param_right)


class IfBlock:
	def __init__(self, comp, if_block, else_block):
		self.comparison = comp
		self.if_block = if_block
		self.else_block = else_block

	def __repr__(self):
		return "If(comp={}, if={}, else={})".format(self.comparison, self.if_block, self.else_block)

	def __str__(self):
		return "if ({})".format(self.comparison)


def new_ident(tokens):
	ident = Identifier(None, None, None)
	if "name" in tokens:
		ident.name = tokens["name"]
	if "array_index" in tokens:
		ident.index = tokens["array_index"]
	if "swizzle" in tokens:
		ident.swizzle = tokens["swizzle"]
	return ident


def new_declare(tokens):
	if "qualifier" in tokens:
		return Declare(tokens[0], tokens[1], tokens[2])
	else:
		return Declare(None, tokens[0], tokens[1])


def new_assign(tokens):
	if isinstance(tokens[0], Declare) and isinstance(tokens[1], Assignment):
		d = tokens[0]
		d.value = tokens[1]
		return d


def new_binary(tokens):
	pass


def new_if_block(tokens):
	# check for the special case
	if "discard_func" in tokens:
		return InlineIf(tokens["discard_func"], "discard")
	# determine whether its a if or an if/else
	if_block = IfBlock(None, None, None)
	if "if_block" in tokens:
		if_block.comparison = tokens["if_comp"]
		if_block.if_block = tokens["if_block"]
		if "else_block" in tokens:
			if_block.else_block = tokens["else_block"]

	return if_block


def parse(text):
	"""Run the parser on the given text"""

	# arithmetic and boolean operators
	operator = PLUS | DASH | ASTERIX | SLASH
	comparator = (
		Combine(EQ + EQ) | Combine(BANG + EQ) |
		Combine(LESS + EQ) | Combine(GREAT + EQ) |
		LESS | GREAT
	)

	# attribute types and qualifiers
	type_qualifier = oneOf("const attribute varying uniform")
	type_specifier = oneOf("float int bool vec2 vec3 vec4 mat2 mat3 mat4 sampler2D samplerCube")

	# built-in function names
	functions = """radians degrees sin cos tan asin acos atan pow exp log exp2
	log2 sqrt inversesqrt abs sign floor ceil fract mod min max clamp mix step
	smoothstep length distance dot cross normalize ftransform faceforward
	reflect refract	matrixCompMult outerProduct transpose lessThan lessThanEqual
	greaterThan	greaterThanEqual equal notEqual any all not texture1D texture1DProj
	texture1DLod texture1DProjLod texture2D texture2DProj texture2DLod
	texture2DProjLod texture3D texture3DProj texture3DLod texture3DProjLod
	textureCube textureCubeLod shadow1D shadow1DProj shadow1DLod shadow1DProjLod
	shadow2D shadow2DProj shadow2DLod shadow2DProjLod dFdx dFdy fwidth noise1
	noise2 noise3 noise4
	"""
	# TODO deal with types properly? really just constructor functions
	builtin_functions = oneOf(functions + "vec2 vec3 vec4 float")

	# constants
	float_const = Combine(Optional(DASH) + Word(nums) + DOT + Word(nums))
	float_const.setParseAction(lambda t : float(t[0]))

	int_const = Combine(Optional(DASH) + Word(nums))
	int_const.setParseAction(lambda t : int(t[0]))

	bool_const = Literal("true") | Literal("false")
	bool_const.setParseAction(lambda t : t[0] == "true")

	const = float_const | int_const | bool_const

	# identifiers
	array_index = LBRACK + Word(nums) + RBRACK
	ident = Word(alphas, alphanums + "_")
	identifier = ident.setResultsName("name") + Optional(array_index).setResultsName("array_index")

	# swizzle
	swizzle = Suppress(DOT) + Word("xyzw", min=1, max=4)
	ident_swizzle = identifier + Optional(swizzle).setResultsName("swizzle")
	ident_swizzle.setParseAction(lambda t : new_ident(t))

	# define macros
	definition = Suppress("#define") + ident_swizzle + ident_swizzle
	definition.setParseAction(lambda t : Define(t[0], t[1]))

	# declarations (constants, uniforms, attributes outside main)
	declaration = (
		Optional(type_qualifier).setResultsName("qualifier")
		+ type_specifier + ident_swizzle
	)
	declaration.setParseAction(lambda t : new_declare(t))

	# declaration with assignment
	assignment_value = type_specifier + Suppress(LPAR) + delimitedList(const) + Suppress(RPAR)
	assignment_value.setParseAction(lambda t : Assignment(t[0], t[1:]))

	assignment_expr = declaration + Suppress(EQ) + (assignment_value | const)
	assignment_expr.setParseAction(lambda t : new_assign(t))

	decl_expr = ((assignment_expr | declaration) + SEMI) | definition

	# instructions
	binary_operation = Forward()
	function = Forward()

	unary_expr = DASH + (function | ident_swizzle)
	unary_expr.setParseAction(lambda t : Unary(t[0], t[1]))

	operand = function | unary_expr | ident_swizzle | const
	function_param = binary_operation | operand

	function << (builtin_functions + Suppress(LPAR) + delimitedList(function_param) + Suppress(RPAR))
	binary_operation <<= (
		(LPAR + binary_operation + RPAR + (operator | comparator) + operand)
		| (LPAR + binary_operation + RPAR)
		| (operand + (operator | comparator) + binary_operation)
		| (operand + (operator | comparator) + operand)
	)

	function.setParseAction(lambda t : Function(t[0], t[1:]))
	binary_operation.setParseAction(lambda t : new_binary(t))

	comparison = operand + comparator + operand
	# specific instance of ternary expressoin encountered
	ternary_expr = LPAR + LPAR + comparison + RPAR + QUESTION + operand + COLON + operand + RPAR

	expr = ternary_expr | binary_operation | unary_expr | function | ident_swizzle

	instruction = ident_swizzle + Suppress(EQ) + expr + SEMI
	instruction.setParseAction(lambda t : Instruction(t[0], t[1:]))

	block = LBRACE + OneOrMore(instruction) + RBRACE

	if_only = (
		Literal("if") + LPAR + comparison.setResultsName("if_comp") + RPAR
		+ block.setResultsName("if_block")
	)
	if_else = if_only + Literal("else") + block.setResultsName("else_block")
	# one-off case for single line conditional discard
	if_discard = (
		Literal("if") + LPAR + function.setResultsName("discard_func")
		+ RPAR + Literal("discard")
	)
	conditional = if_else | if_only | if_discard + SEMI
	conditional.setParseAction(lambda t : new_if_block(t))

	statements = instruction | conditional

	# opengl version
	version = Suppress("#version") + Word(nums).setResultsName("version")

	# main function
	main_function = (
		Suppress("void") + Suppress("main") + Suppress(LPAR) + Suppress(RPAR) + LBRACE
		+ OneOrMore(statements).setResultsName("instructions")  + RBRACE
	)

	# top-level rule
	parser = (
		version + ZeroOrMore(decl_expr).setResultsName("declarations")
		+ main_function + StringEnd()
	)

	return parser.parseString(text)


def output(parsed, tab="\t"):
	print(f"#version {parsed.version}")

	for decl in parsed.declarations:
		print("{!s}".format(decl))

	print("\nvoid main()\n{")
	for ins in parsed.instructions:
		if isinstance(ins, IfBlock):
			print("{}{} {{".format(tab, ins))
			for inner_ins in ins.if_block:
				print("{0}{0}{1}".format(tab, inner_ins))
			if ins.else_block:
				print("{}}} else {{".format(tab))
				for inner_ins in ins.else_block:
					print("{0}{0}{1}".format(tab, inner_ins))
			print("{}}}".format(tab))
		else:
			print("{}{!s}".format(tab, ins))
	print("}")


def run_on_all(dir):
	# recurse all subdirs find vert and frag, catch errors, print file path
	total = 0
	failed = 0

	walk_dir = os.path.abspath(dir)

	for root, subdirs, files in os.walk(walk_dir):
		if "Standard" in root or "Pegasus" in root or "Legacy Shaders" in root:
			continue
		for filename in files:
			file_path = os.path.join(root, filename)
			ext = filename[-4:]
			if ext == "vert" or ext == "frag":
				total += 1
				with open(file_path) as f:
					contents = f.read()
				try:
					parse(contents)
				except ParseException as pe:
					failed += 1
					print(f"\nFAILED: {file_path}")
					print(f"\t{pe}\n")
					print(pe.markInputline())

	print(f"{total} files | {failed} failed")


def main():
	if len(sys.argv) < 3:
		print("usage: glsl_parser <-s|-r> <file>")
		return

	filepath = sys.argv[2]

	if sys.argv[1] == "-r":
		run_on_all(filepath)
	elif sys.argv[1] == '-s':
		with open(filepath) as f:
			contents = f.read()
		try:
			result = parse(contents)
			output(result)
		except ParseException as pe:
			print(pe)
			print(pe.markInputline())


if __name__ == "__main__":
	main()
