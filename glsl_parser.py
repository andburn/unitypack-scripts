#!/usr/bin/env python

"""A limited GLSL parser, specifically handles mojoshaders GLSL output"""

import sys
from pyparsing import (
	Suppress, Word, Literal, OneOrMore, ZeroOrMore, Optional, Combine, SkipTo, 
	Group, delimitedList, oneOf, alphas, alphanums, nums, stringEnd, Forward
)

LBRACE, RBRACE, LBRACK, RBRACK, LPAR, RPAR, LESS, GREAT = map(Suppress, "{}[]()<>")
PLUS, DASH, SLASH, ASTERIX, PERCENT, EQ, DOT = map(Literal, "+-/*%=.")
CARET, BAR, AMPERSAND, TILDE, BANG, COLON, SEMI, COMMA, HASH, QUESTION = map(Suppress, "^|&~!:;,#?")


def parse(text):
	"""Run the parser on the given text"""

	float_const = Combine(Optional(DASH) + Word(nums) + DOT + Word(nums))
	float_const.setParseAction(lambda tokens : float(tokens[0]))

	int_const = Combine(Optional(DASH) + Word(nums)).setParseAction(lambda tokens : int(tokens[0]))
	
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

	operator = PLUS | DASH | ASTERIX
	comparator = (EQ + EQ) | (LESS + EQ) | (GREAT + EQ) | LESS | GREAT
	
	unary_ident = Optional(DASH) + ident_swizzle
	arith_expr = unary_ident + operator + unary_ident

	comparison = unary_ident + comparator + (unary_ident | const)
	ternary_expr = LPAR + LPAR + comparison + RPAR + QUESTION + unary_ident + COLON + unary_ident + RPAR

	func_call = Forward()
	param = assignment_value | func_call | arith_expr | ident_swizzle | const
	param_list = delimitedList(param)
	func_name = "texture2D min dot mix clamp fract"
	func_call << Group( oneOf(func_name) + LPAR + param_list + RPAR )
	
	compound_arith_expr = LPAR + arith_expr + RPAR + operator + unary_ident

	right_expr = func_call | ternary_expr | compound_arith_expr | arith_expr | unary_ident

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
