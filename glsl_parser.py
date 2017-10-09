#!/usr/bin/env python

"""A limited GLSL parser, specifically handles mojoshaders GLSL output"""

import os
import sys
from collections import namedtuple
from pyparsing import (
	Suppress, Word, Literal, OneOrMore, ZeroOrMore, Optional, Combine, SkipTo, 
	Group, delimitedList, oneOf, alphas, alphanums, nums, stringEnd, Forward,
	ParseException
)

LBRACE, RBRACE, LBRACK, RBRACK, LPAR, RPAR = map(Suppress, "{}[]()")
PLUS, DASH, SLASH, ASTERIX, PERCENT, EQ, DOT = map(Literal, "+-/*%=.")
COLON, SEMI, COMMA, HASH, QUESTION = map(Suppress, ":;,#?")
CARET, BAR, AMPERSAND, TILDE, BANG = map(Suppress, "^|&~!")
LESS, GREAT = map(Literal, "<>")


Defines = namedtuple("Defines", "src dest")
Function = namedtuple("Function", "name params")
Unary = namedtuple("Unary", "name op")


def parse(text):
	"""Run the parser on the given text"""

	# operators
	operator = PLUS | DASH | ASTERIX | SLASH
	comparator = Combine(EQ + EQ) | Combine(LESS + EQ) | (GREAT + EQ) | LESS | GREAT

	# keywords
	type_qualifier = oneOf("const attribute varying uniform")
	type_specifier = oneOf("float int bool vec2 vec3 vec4 mat2 mat3 mat4 sampler2D")

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
	builtin_functions = oneOf(functions + "vec2 vec3 vec4") # TODO deal vecX properly


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
	identifier = Combine(ident + Optional(array_index))
	# TODO deal with array indices

	# declarations (constants, uniforms, #define etc. outside main)
	declaration = Optional(type_qualifier) + type_specifier + identifier

	definition = Suppress("#define") + identifier + identifier
	definition.setParseAction(lambda t : Defines(t[1], t[0]))

	assignment_value = type_specifier + LPAR + delimitedList(const) + RPAR
	assignment_expr = declaration + EQ + (assignment_value | const)
	decl_expr = ((assignment_expr | declaration) + SEMI) | definition

	# swizzle
	swizzle = Suppress(DOT) + Word("xyzw", min=1, max=4)
	ident_swizzle = identifier + Optional(swizzle)

	# rhs expressions
	binary_operation = Forward()
	function = Forward()
	
	unary_expr = DASH + ident_swizzle
	unary_expr.setParseAction(lambda t : Unary(t[1], t[0]))	

	operand = function | (LPAR + binary_operation + RPAR) | unary_expr | ident_swizzle | const
	
	function << (builtin_functions + LPAR + delimitedList(operand) + RPAR)	
	binary_operation << (operand + (operator | comparator) + operand)
	
	function.setParseAction(lambda t : Function(t[0], t[1:]))

	comparison = operand + comparator + operand
	
	ternary_expr = LPAR + comparison + RPAR + QUESTION + operand + COLON + operand

	expr = ternary_expr | binary_operation | function | ident_swizzle

	instruction = ident_swizzle + EQ + expr + SEMI


	# main function
	main_function = Suppress("void") + Suppress("main") + LPAR + RPAR + \
		LBRACE + OneOrMore(instruction).setResultsName("instructions")  + RBRACE

	# opengl version
	version = Suppress("#version") + Word(nums).setResultsName("version")

	# top-level rule
	parser = version + ZeroOrMore(decl_expr) + main_function + stringEnd

	return parser.parseString(text)


def run_on_all(dir):
	# recurse all subdirs find vert and frag, catch errors, print file path
	total = 0
	failed = 0

	walk_dir = os.path.abspath(dir)

	for root, subdirs, files in os.walk(walk_dir):
		if "Standard" in root:
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
			parse(contents)
		except ParseException as pe:
			print(pe)
			print(pe.markInputline())


if __name__ == "__main__":
	main()
