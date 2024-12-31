import pymsch, re, sys, os, subprocess, math, datetime

def ERROR(msg: str):
	print(f"ERROR: {msg}")
	sys.exit()

def parse_mlog_markup_language(code: str) -> list[list[str]]:
	lines = re.findall(r"(?:^|;)\s*((?: ?[^#\s;]+)+)", code, re.M)
	lines = [re.findall(r'".*"|\S+', x) for x in lines]
	return lines

def require_args(line, count):
	if(len(line) < count + 1):
		ERROR(f"Instruction '{line[0]}' expected {count} arguments")

def maybe_string(value: str) -> str:
	if value[0] == '"' and value[-1] == '"':
		return value[1:-1]
	return value

class CodeParser:
	def __init__(self, code: str):
		self.blocks = []
		self.procs = []

		self.block_positions = []

		self.compiler = None
		self.header = None
		self.trailer = None
		self.name = "Unnamed"
		self.desc = ""

		self.vars = {}

		self._handle_instructions(code)

	def _handle_instructions(self, code: str):
		for line in parse_mlog_markup_language(code):
			instruction = line[0]
			try:
				if(instruction[0] == '_'):
					ERROR(f"Unknown instruction '{instruction}'")
				else:
					getattr(CodeParser, instruction)(self, line)
			except AttributeError:
				ERROR(f"Unknown instruction '{instruction}'")

	def set(self, line):
		require_args(line, 2)
		match line[1]:
			case "compiler":
				self.compiler = maybe_string(line[2])
			case "trailer":
				self.trailer = maybe_string(line[2])
			case "header":
				self.header = maybe_string(line[2])
			case "name":
				self.name = maybe_string(line[2])
			case "description":
				self.desc = maybe_string(line[2])
			case _:
				ERROR(f"Unknown argument {line[1]} for 'set'")

	def var(self, line):
		require_args(line, 2)
		self.vars[line[1]] = line[2]


	def block(self, line):
		require_args(line, 2)
		self.blocks.append({"type": pymsch.Content[line[1].upper().replace('-', '_')], "name": line[2]})

	def proc(self, line):
		require_args(line, 1)
		self.procs.append({"path": maybe_string(line[1]), "iteration": 0, "iteration_count": 1})

	def repeatproc(self, line):
		require_args(line, 2)
		for i in range(int(line[2])):
			self.procs.append({"path": maybe_string(line[1]), "iteration": i, "iteration_count": int(line[2])})

def create_schematic(code: CodeParser, path: str) -> tuple[pymsch.Schematic, list]:
	schem = pymsch.Schematic()
	schem.set_tag("name", code.name)
	schem.set_tag("description", code.desc)
	schem_add_blocks(code, schem)
	errors = schem_add_procs(code, schem, path)
	return (schem, errors)

def schem_add_procs(code: CodeParser, schem: pymsch.Schematic, path: str) -> list:
	errors = []
	if code.header:
		with open(path + code.header) as f:
			header = f.read() + '\n'
	else:
		header = ""
	if code.trailer:
		with open(path + code.trailer) as f:
			trailer = '\n' + f.read()
	else:
		trailer = ""
	for i, proc in enumerate(code.procs):
		with open(path + proc["path"]) as f:
			proc_code = header + f.read() + trailer
		proc_code = proc_code.replace("{iteration}", str(proc["iteration"]))
		proc_code = proc_code.replace("{iteration_count}", str(proc["iteration_count"]))
		for var_name, value in code.vars.items():
			proc_code = proc_code.replace("{" + var_name + "}", value)
		if code.compiler != None:
			with open(path + ".smpm_tmp", "w") as f:
				f.write(proc_code)
			time = datetime.datetime.now()
			status, proc_code = subprocess.getstatusoutput(code.compiler.format(file = path + ".smpm_tmp"))
			if status != 0:
				errors.append(proc["path"])
			if(proc["iteration_count"] > 1):
				print(f"proc {proc["iteration"]} of {proc["path"]} in {(datetime.datetime.now()-time).total_seconds()} seconds")
			else:
				print(f"proc {proc["path"]} in {(datetime.datetime.now()-time).total_seconds()} seconds")

		square_size = math.ceil(math.sqrt(len(code.procs)))
		x = i % square_size
		y = i // square_size

		links = []
		for block in code.block_positions:
			links.append(pymsch.ProcessorLink(block[0] - x, block[1] - y, "hi chat"))
		schem.add_block(pymsch.Block(pymsch.Content.WORLD_PROCESSOR, x, y, pymsch.ProcessorConfig(proc_code, links), 0))
	return list(set(errors))

def schem_add_blocks(code: CodeParser, schem: pymsch.Schematic):
	x = 0
	for block in code.blocks:
		block_type = block["type"]
		block_name = block["name"]

		schem.add_block(pymsch.Block(block_type, x + math.ceil(block_type.value.size/2) - 1, -(block_type.value.size//2) - 1, None, 0))
		
		code.block_positions.append((x + math.ceil(block_type.value.size/2) - 1, -(block_type.value.size//2) - 1))
		x += block_type.value.size

start_time = datetime.datetime.now()
path = sys.argv[1]
path = path + "/" if path[-1] != '/' else path
file = open(path + "config.smpm", "r")
code = file.read()
file.close()
code = CodeParser(code)
schem, errors = create_schematic(code, path)
schem.write_clipboard()
#schem.write_file(path + "outfile.msch")
if(len(errors) == 0):
	print(f"finished in {(datetime.datetime.now()-start_time).total_seconds()} seconds")
else:
	print(f"finished in {(datetime.datetime.now()-start_time).total_seconds()} seconds, with errors in {", ".join(errors)}")