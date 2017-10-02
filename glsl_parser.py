#!/usr/bin/env python

"""A limited GLSL parser, specifically handles mojoshaders GLSL output"""

import sys
from pyparsing import (
	Suppress, Word, Literal, OneOrMore, ZeroOrMore, Optional, Combine, SkipTo, 
	Group, delimitedList, oneOf, alphas, alphanums, nums, stringEnd
)

LBRACE, RBRACE, LBRACK, RBRACK, LPAR, RPAR, LANG, RANG = map(Suppress, "{}[]()<>")
PLUS, DASH, SLASH, ASTERIX, PERCENT, EQ, DOT = map(Literal, "+-/*%=.")
CARET, BAR, AMPERSAND, TILDE, BANG, COLON, SEMI, COMMA, HASH = map(Suppress, "^|&~!:;,#")


def parse(text):
	"""Run the parser on the given text"""

	float_const = Combine(Word(nums) + DOT + Word(nums))
	float_const.setParseAction(lambda tokens : float(tokens[0]))

	int_const = Word(nums).setParseAction(lambda tokens : int(tokens[0]))
	
	const = float_const | int_const

	ident = Word(alphas, alphanums + "_") # gl_* are reserved, but doesn't really matter

	array_element = ident + LBRACK + Word(nums) + RBRACK

	version = Suppress("#version") + Word(nums).setResultsName("version")

	type_qualifier = oneOf("const attribute varying uniform")
	type_specifier = oneOf("void float int bool vec2 vec3 vec4 mat2 mat3 mat4 sampler2D")

	declaration = Optional(type_qualifier) + type_specifier + (array_element | ident)
	definition = Literal("#define") + ident + (array_element | ident)

	assignment_value = type_specifier + LPAR + delimitedList(const) + RPAR
	assignment_expr = declaration + EQ + assignment_value
	expr = ((assignment_expr | declaration) + SEMI) | definition

	swizzle = Suppress(DOT) + Word("xyzw", min=1, max=4)
	ident_swizzle = ident + Optional(swizzle).setResultsName("swizzle")

	ident_list = delimitedList(ident_swizzle)
	func_name = "texture2D min dot mix"
	func_call = oneOf(func_name) + LPAR + ident_list + RPAR

	operator = PLUS | DASH | ASTERIX
	arith_expr = ident_swizzle + operator + ident_swizzle
	compound_arith_expr = LPAR + arith_expr + RPAR + operator + ident_swizzle

	right_expr = func_call | compound_arith_expr | arith_expr | ident_swizzle

	full_expr = Group(ident_swizzle + EQ + right_expr) + Suppress(SEMI)

	main_funciton = Literal("void") + Literal("main") + LPAR + RPAR + LBRACE + \
		OneOrMore(full_expr).setResultsName("instructions")  + RBRACE

	parser = version + ZeroOrMore(expr) + main_funciton + stringEnd

	return parser.parseString(text)


def main():
	if len(sys.argv) < 2:
		print("usage: glsl_parser <file>")
		return

	filepath = sys.argv[1]
	with open(filepath) as f:
		contents = f.read()	

	print(parse(contents))


if __name__ == "__main__":
	main()
