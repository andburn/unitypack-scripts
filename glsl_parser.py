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
from glsl_objects import (
	Identifier, Define, Declare, Assignment, Function, Instruction, Unary,
	Binary, Ternary, FloatLiteral, IfBlock, new_ident, new_declare,
	new_assign, new_binary,	new_if_block
)

LBRACE, RBRACE, LBRACK, RBRACK = map(Suppress, "{}[]")
PLUS, DASH, SLASH, ASTERIX, PERCENT, EQ, DOT = map(Literal, "+-/*%=.")
COLON, SEMI, COMMA, HASH, QUESTION = map(Suppress, ":;,#?")
CARET, BAR, AMPERSAND, TILDE = map(Suppress, "^|&~")
LESS, GREAT, LPAR, RPAR, BANG = map(Literal, "<>()!")


def parse(text):
	"""Run the parser on the given text"""

	idents = {} # store all identifiers

	# arithmetic and boolean operators
	algebraic_operator = PLUS | DASH | ASTERIX | SLASH
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
	float_const.setParseAction(lambda t : FloatLiteral(t[0]))

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
	ident_swizzle.setParseAction(lambda t : new_ident(t, idents))

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
	operator = algebraic_operator | comparator

	function << (
		builtin_functions + Suppress(LPAR)
		+ delimitedList(function_param) + Suppress(RPAR)
	)

	binary_operation << (
		(LPAR + binary_operation + RPAR + operator + operand)
		| (LPAR + binary_operation + RPAR)
		| (operand + operator + binary_operation)
		| (operand + operator + operand)
	)

	function.setParseAction(lambda t : Function(t[0], t[1:]))
	binary_operation.setParseAction(lambda t : new_binary(t))

	# specific instance of ternary expressoin encountered
	ternary_expr = (
		Suppress(LPAR) + Suppress(LPAR) + binary_operation + Suppress(RPAR)
		+ QUESTION + operand + COLON + operand + Suppress(RPAR)
	)
	ternary_expr.setParseAction(lambda t : Ternary(t[0], t[1], t[2]))

	expr = ternary_expr | binary_operation | unary_expr | function | ident_swizzle

	instruction = ident_swizzle + Suppress(EQ) + expr + SEMI
	instruction.setParseAction(lambda t : Instruction(t[0], t[1:]))

	block = LBRACE + OneOrMore(instruction) + RBRACE

	if_only = (
		Literal("if") + LPAR + binary_operation.setResultsName("if_comp") + RPAR
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

	# glsl version
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

	return (parser.parseString(text), idents)

# TODO move this to shaders.py
def build(parsed, tab="\t", version=None, keywords=None, declarations=None):
	output = []

	# add any keywords/tags as a comment at top of the file
	if keywords:
		comment = "// KEYWORDS {}".format(" ".join(keywords))
		output.append(comment)

	# allow the parsed version to be overwritten
	output.append("#version {}".format(
		version if version else parsed.version
	))

	# used customized declarations string if available
	if declarations:
		output.extend(declarations)
	else:
		for decl in parsed.declarations:
			output.append("{!s}".format(decl))

	output.append("\nvoid main()\n{")
	for ins in parsed.instructions:
		if isinstance(ins, IfBlock):
			output.append("{}{} {{".format(tab, ins))
			for inner_ins in ins.if_block:
				output.append("{0}{0}{1}".format(tab, inner_ins))
			if ins.else_block:
				output.append("{}}} else {{".format(tab))
				for inner_ins in ins.else_block:
					output.append("{0}{0}{1}".format(tab, inner_ins))
			output.append("{}}}".format(tab))
		else:
			output.append("{}{!s}".format(tab, ins))
	output.append("}")
	return "\n".join(output)


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
					result = parse(contents)
					success = compare(contents, build(result))
					if not success:
						raise Exception(("Comparison Failed:", file_path))
				except ParseException as pe:
					failed += 1
					print(f"\nFAILED: {file_path}")
					print(f"\t{pe}\n")
					print(pe.markInputline())
				except Exception as e:
					print(f"\nERROR: {file_path}")
					print(f"\t{e}\n")

	print(f"{total} files | {failed} failed")


def remove_empty_trailing(lines):
	for i in range(len(lines) - 1, 0, -1):
		if not lines[i].strip():
			del lines[i]
		else:
			break
	return lines


def compare(input, output):
	left = remove_empty_trailing(input.split("\n"))
	right = remove_empty_trailing(output.split("\n"))
	num_lines = len(left)

	if num_lines != len(right):
		print("Mismatch in number of lines: {} != {}".format(num_lines, len(right)))
		return False

	for i in range(num_lines):
		if left[i] != right[i]:
			print("Lines are different at {}:".format(i))
			print(" LEFT: {}".format(left[i]))
			print("RIGHT: {}".format(right[i]))
			return False

	return True


def main():
	if len(sys.argv) < 3:
		print("usage: glsl_parser <-s|-r|-c> <file>")
		return

	filepath = sys.argv[2]

	if sys.argv[1] == "-r":
		run_on_all(filepath)
	elif sys.argv[1] == '-s' or sys.argv[1] == '-c':
		with open(filepath) as f:
			contents = f.read()
		try:
			result, idents = parse(contents)
			out_str = build(result)
			if sys.argv[1] == '-c':
				compare(contents, out_str)
			else:
				print(out_str)
		except ParseException as pe:
			print(pe)
			print(pe.markInputline())


if __name__ == "__main__":
	main()
