"""Classes to organize the ouput of GLSL shader parsing"""

class Identifier:
	def __init__(self, name, index, swizzle):
		self.name = name
		self.index = None
		self.swizzle = None

	def __repr__(self):
		r = ["Ident(name=", self.name]
		if self.index != None:
			r.append(", index={}".format(self.index))
		if self.swizzle:
			r.append(", swizzle={}".format(self.swizzle))
		r.append(")")
		return "".join(r)

	def __str__(self):
		s = [self.name]
		if self.index != None:
			s.extend(["[", str(self.index), "]"])
		if self.swizzle:
			s.extend([".", self.swizzle])
		return "".join(s)


class Define:
	def __init__(self, dest, src):
		self.src = src
		self.dest = dest

	def __repr__(self):
		return "Define(dest={!r} src={!r})".format(self.dest, self.src)

	def __str__(self):
		return "#define {} {}".format(self.dest, self.src)


class Declare:
	def __init__(self, qualifier, dtype, ident, value=None):
		self.qualifier = qualifier
		self.type = dtype
		self.ident = ident
		self.value = value

	def __repr__(self):
		return "Declare(qual={} type={} ident={!r} value={!r})".format(
			self.qualifier, self.type, self.ident, self.value)

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
		return "Assign(type={}, value={!r})".format(self.type, self.value)

	def __str__(self):
		values = ", ".join(map(str, self.value))
		return "{}({})".format(self.type, values)


class Function:
	def __init__(self, name, params):
		self.name = name
		self.params = params

	def __repr__(self):
		return "Func(name={}, params={!r})".format(self.name, self.params)

	def __str__(self):
		return "{}({})".format(self.name, ", ".join(map(str, self.params)))


class Instruction:
	def __init__(self, ident, expr):
		self.ident = ident
		self.expression = expr

	def __repr__(self):
		return "Ins(ident={!r}, expr={!r})".format(self.ident, self.expression)

	def __str__(self):
		return "{} = {};".format(self.ident, " ".join(map(str, self.expression)))


class Unary:
	def __init__(self, op, param):
		self.operation = op
		self.param = param

	def __repr__(self):
		return "Unary(op={}, expr={!r})".format(self.operation, self.param)

	def __str__(self):
		return "{}{}".format(self.operation, self.param)


class Binary:
	def __init__(self, op, paraml, paramr, precedence=False):
		self.operation = op
		self.param_left = paraml
		self.param_right = paramr
		self.precedence = precedence

	def __repr__(self):
		return "Binary(op={} pl={!r} pr={!r} prec={})".format(
			self.operation, self.param_left,
			self.param_right, self.precedence)

	def __str__(self):
		return "{}{} {} {}{}".format(
				"(" if self.precedence else "",
				self.param_left,
				self.operation,
				self.param_right,
				")" if self.precedence else ""
			)


class Ternary:
	def __init__(self, cond, expr_true, expr_false):
		self.condition = cond
		self.expr_true = expr_true
		self.expr_false = expr_false

	def __repr__(self):
		return "Ternary(codn={!r} true={!r} false={!r})".format(
			self.condition, self.expr_true, self.expr_false)

	def __str__(self):
		return "(({}) ? {} : {})".format(
				self.condition,
				self.expr_true,
				self.expr_false,
			)


class FloatLiteral:
	"""Want to keep the string for equivalence (i.e. scientific notation)"""
	def __init__(self, string):
		self.value = float(string)
		self.string = string

	def __repr__(self):
		return "Float(v={}, s={})".format(self.value, self.string)

	def __str__(self):
		if self.string:
			return self.string
		else:
			return str(self.value)


class IfBlock:
	def __init__(self, comp, if_block, else_block):
		self.comparison = comp
		self.if_block = if_block
		self.else_block = else_block

	def __repr__(self):
		return "If(comp={!r}, if={}, else={})".format(
			self.comparison, self.if_block, self.else_block)

	def __str__(self):
		return "if ({})".format(self.comparison)


class InlineIf:
	def __init__(self, func, command):
		self.function = func
		self.command = command

	def __repr__(self):
		return "IfInline(func={}, cmd={})".format(self.function, self.command)

	def __str__(self):
		return "if ({}) {};".format(self.function, self.command)


# creator/factory functions for above classes


def new_ident(tokens):
	ident = Identifier(None, None, None)
	if "name" in tokens:
		ident.name = tokens["name"]
	if "array_index" in tokens and len(tokens["array_index"]) == 1:
		ident.index = int(tokens["array_index"][0])
	if "swizzle" in tokens and len(tokens["swizzle"]) == 1:
		ident.swizzle = tokens["swizzle"][0]
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
	ops = "+ - * / > < >= <= == !=".split()
	nested = 0
	op = None
	preced = False
	param = []
	binary = Binary(None, None, None)
	for t in tokens:
		if t == "(":
			nested += 1
			preced = True
		elif t == ")":
			nested -= 1
		elif t in ops:
			if nested == 0:
				binary.operation = t
				if preced:
					try:
						# if param is a Binary, add precedence
						# should be single param
						assert len(param) == 1
						param[0].precedence = preced
					except:
						raise
				binary.param_left = param[0]
				param = []
				preced = False
		else:
			param.append(t)
	assert len(param) == 1
	binary.param_right = param[0]

	return binary


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

