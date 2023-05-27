import pyrtl

# Initialize your memblocks here: 

# When working on large designs, such as this CPU implementation, it is
# useful to partition your design into smaller, reusable, hardware
# blocks. In PyRTL, one way to do this is through functions. Here are 
# some examples of hardware blocks that can help you get started on this
# CPU design. You may have already worked on this logic in prior labs.





def decode(instr):
	op = pyrtl.WireVector(bitwidth=6, name='op_')
	rs = pyrtl.WireVector(bitwidth=5, name='rs')
	rt = pyrtl.WireVector(bitwidth=5, name='rt')
	rd = pyrtl.WireVector(bitwidth=5, name='rd')
	sh = pyrtl.WireVector(bitwidth=16, name='sh')
	func = pyrtl.WireVector(bitwidth=6, name='func_')
	imm = pyrtl.WireVector(bitwidth=16, name='imm')


	op <<=   instr[32 - 6 : 32 - 0  ]
	rs <<=   instr[32 - 11 : 32 - 6  ]
	rt <<=   instr[32 - 16 : 32 - 11 ]
	rd <<=   instr[32 - 21 : 32 - 16 ]
	sh <<=   instr[32 - 26 : 32 - 21 ]
	func <<= instr[32 - 32 : 32 - 26 ]
	imm <<=  instr[32 - 32 : 32 - 16 ]
	imm_se = imm.sign_extended(32)
	imm_ze, imm_se = pyrtl.match_bitwidth(imm, imm_se) # make zero-extended immediate
	return op, rs, rt, rd, sh, func, imm, imm_se, imm_ze





def alu(data0, data1, imm_se, imm_ze, alu_src, alu_op):
	# PUT VARIOUS ALU OPS // control sigs later in separate part
	alu_out = pyrtl.WireVector(bitwidth=32, name="alu_out")


	alu_in0 = data0


	data1 = pyrtl.mux(alu_src, data1, imm_se, imm_ze, default=0xAA) # src=0 r type
														# src=1 se imm
														# src=2 ze imm

	# ops
	op_add = (data0 + data1)[:32]
	op_and = data0 & data1
	op_or = data0 | data1
	op_sub = (data0 - data1)[:32]
	op_slt = ((data0[:-1] < data1[:-1]) & ~((~data0[-1]) & data1[-1] )) | (data0[-1] & ~data1[-1])

	# # I originally had:
	# op_slt = data0 < data1 # this sometimes doesn't work because
	# # 	# it treats the bits in data0 and data1 as representing unsigned numbers 
	# # 	# (they're negative but it thinks they're positive)
	# # 	# so instead I have:
	# op_slt = (data0[:-1] < data1[:-1]) ^ ((~data0[-1]) & data1[-1] )
	# # 	# which is basically "data0 < data1" but it corrects for signed numbers
	# # I'd had
	# 	op_slt = (data0[:-1] < data1[:-1]) & ~((~data0[-1]) & data1[-1] )
	# # THIS IS WRONG IT ONLY PREVENTS THE FALSE POSITIVE NOT THE FALSE NEGAITIVE
	# 	op_slt = (data0[:-1] < data1[:-1]) & ~((~data0[-1]) & data1[-1] )
	# 	# THIS I THINK IS CORRECT
	# 	# NO THAT ACTUALLY MAKES A LOT LESS SENSE
	# 	# DEFINITELY NOT THAT

	# # ((~data0[-1] & data1[-1]) 
	# # 	| (~data0[-1] & ~data1[-1] & (data0[:-1] < data1[:-1]))
	# # 	| (data0[-1] & data1[-1] & (data0[:-1] < data1[:-1]))
	# # )
	# op_slt = (data0[:-1] < data1[:-1]) & ~((~data0[-1]) & data1[-1] ) | (data0[-1] & ~data1[-1])
	# # NOW WE'RE TALKING
	# op_slt = (data0[:-1] < data1[:-1])  # magnitude
	# 	& ~((~data0[-1]) & data1[-1] )  # catch false positive
	# 	| (data0[-1] & ~data1[-1]) # catch false NEGAITIVE


	z = pyrtl.WireVector(bitwidth=16)
	z <<= 0
	op_lui = pyrtl.concat(imm, z)

	with pyrtl.conditional_assignment:
		with alu_op == 0:
			# ADD
			alu_out |= op_add
		with alu_op == 1:
			# and
			alu_out |= op_and
		with alu_op == 2:
			# lui
			alu_out |= op_lui
		with alu_op == 3:
			# OR
			alu_out |= op_or
		with alu_op == 4:
			# SLT
			alu_out |= op_slt
		with alu_op == 5:
			# SUB
			alu_out |= op_sub

	zero = (alu_out == 0)

	return alu_out, zero






	




def controller(op, funct):
	cccontrol = pyrtl.WireVector(bitwidth=10)
	memread = 0			
	with pyrtl.conditional_assignment:
		with op == 0x0:
			with funct == 0x20:
				#add
				cccontrol |= 0x280
			with funct == 0x24:
				#and
				cccontrol |= 0x281
			with funct == 0x2a:
				#slt
				cccontrol |= 0x284
		with op == 0x8:
			#addi
			cccontrol |= 0x0A0
		with op == 0xf:
			#lui
			cccontrol |= 0x0C2
		with op == 0xd:
			#ori
			cccontrol |= 0x0C3
		with op == 0x23:
			#lw
			cccontrol |= 0x0A8
			memread = 1		
		with op == 0x2b:
			#sw
			cccontrol |= 0x030
		with op == 0x4:
			#beq
			cccontrol |= 0x105

	regdst, branch, regwrite, alu_src, memwrite, memtoreg, alu_op = pyrtl.chop(cccontrol, 1, 1, 1, 2, 1, 1, 3)

	return regdst, branch, memread, memwrite, memtoreg, regwrite, alu_op, alu_src

#done?
def reg_io(rs, rt, rd, regdst, regwrite, write_data = None):
	if write_data is None:
		write_data = pyrtl.WireVector(bitwidth=32)
	rf = pyrtl.MemBlock(bitwidth=32, addrwidth=5, name="rf", asynchronous=True)

	data0 = rf[rs]
	data1 = rf[rt]
	writereg = pyrtl.select(regdst, rd, rt)
	rf[writereg] <<= pyrtl.MemBlock.EnabledWrite(write_data, enable=regwrite & (writereg != 0))


	return data0, data1, write_data, rf

#done?
def pc_update(s_ext_imm, branch, zero):
	pc = pyrtl.Register(bitwidth=32)
	i_mem = pyrtl.MemBlock(bitwidth=32, addrwidth=32, name="i_mem") #can be async; doesn't need to be

	nojump = pc + 1
	jump = (nojump + s_ext_imm)[0:32]

	dobranch = branch & zero

	pc.next <<= pyrtl.select(dobranch, jump, nojump)
	instr = i_mem[pc]
	return instr, i_mem, pc

def mem_sl(addr, write_data, memwrite):
	d_mem = pyrtl.MemBlock(bitwidth=32, addrwidth=32, asynchronous=True, name="d_mem") # async

	d_mem[addr] <<= pyrtl.MemBlock.EnabledWrite(write_data, enable=memwrite)
	mem_data = d_mem[addr]
	# pyrtl.WireVector(bitwidth=32)
	# mem_data <<=
	return mem_data, d_mem



def write_back(write_data):
	raise NotImplementedError

# These functions implement smaller portions of the CPU design. A 
# top-level function is required to bring these smaller portions
# together and finish your CPU design. Here you will instantiate 
# the functions, i.e., build hardware, and orchestrate the various 
# parts of the CPU together. 


imm_se = pyrtl.WireVector(bitwidth=32, name="se_immediate")
op = pyrtl.WireVector(bitwidth=6, name="op")
func = pyrtl.WireVector(bitwidth=6, name="func")
regdst, branch, memread, memwrite, memtoreg, regwrite, alu_op, alu_src = controller(op, func)

zero = pyrtl.WireVector(bitwidth=1, name="zero")
instr, i_mem, pc = pc_update(imm_se, branch, zero)

op_, rs, rt, rd, sh, func_, imm, imm_se_, imm_ze = decode(instr)
imm_se <<= imm_se_ # completing the loops
op <<= op_
func <<= func_

data0, data1, write_data, rf = reg_io(rs, rt, rd, regdst, regwrite)

alu_out, zero_ = alu(data0, data1, imm_se, imm_ze, alu_src, alu_op)
zero <<= zero_

mem_data, d_mem = mem_sl(addr=alu_out, write_data=data1, memwrite=memwrite)
write_data <<= pyrtl.select(memtoreg, mem_data, alu_out)




	# raise NotImplementedError
# rf, i_mem, d_mem = top()
if __name__ == '__main__':

	"""

	Here is how you can test your code.
	This is very similar to how the autograder will test your code too.

	1. Write a MIPS program. It can do anything as long as it tests the
	 instructions you want to test.

	2. Assemble your MIPS program to convert it to machine code. Save
	 this machine code to the "i_mem_init.txt" file.
	 You do NOT want to use QtSPIM for this because QtSPIM sometimes
	 assembles with errors. One assembler you can use is the following:

	 https://alanhogan.com/asu/assembler.php

	3. Initialize your i_mem (instruction memory).

	4. Run your simulation for N cycles. Your program may run for an unknown
	 number of cycles, so you may want to pick a large number for N so you
	 can be sure that the program so that all instructions are executed.

	5. Test the values in the register file and memory to make sure they are
	 what you expect them to be.

	6. (Optional) Debug. If your code didn't produce the values you thought
	 they should, then you may want to call sim.render_trace() on a small
	 number of cycles to see what's wrong. You can also inspect the memory
	 and register file after every cycle if you wish.

	Some debugging tips:

		- Make sure your assembly program does what you think it does! You
		 might want to run it in a simulator somewhere else (SPIM, etc)
		 before debugging your PyRTL code.

		- Test incrementally. If your code doesn't work on the first try,
		 test each instruction one at a time.

		- Make use of the render_trace() functionality. You can use this to
		 print all named wires and registers, which is extremely helpful
		 for knowing when values are wrong.

		- Test only a few cycles at a time. This way, you don't have a huge
		 500 cycle trace to go through!

	"""
	instrstr = ["AND $t1 $zero $zero",
		"AND $t2 $zero $zero",
		"LUI $t1 0xFFFF",
		"ORI $t1 $t1 0xFFFF",
		"ORI $t2 $t2 0x00FC",
		"SW $t1 0x0004 $t2",
		"AND $t1 $t1 $t2",
		"ADDI $t1 $t1 0xFFFE",
		"LW $t3 0x0004 $t2",
		"SLT $t4 $t1 $t3",
		"BEQ $t4 $zero 0xFFFB",
		"AND $zero $t1 $t2",
		"BEQ $zero $zero 0xFFFE"]


	# Start a simulation trace
	sim_trace = pyrtl.SimulationTrace()

	# Initialize the i_mem with your instructions.
	i_mem_init = {}
	with open('i_mem_init.txt', 'r') as fin:
		i = 0
		for line in fin.readlines():
			i_mem_init[i] = int(line, 16)
			i += 1


	sim = pyrtl.Simulation(tracer=sim_trace, memory_value_map={
		i_mem : i_mem_init
	})

	# Run for an arbitrarily large number of cycles.
	for cycle in range(500):
		sim.step({})
		print(instrstr[sim.inspect(pc)])
		print("rf:", sim.inspect_mem(rf))
		print("d_mem:", sim.inspect_mem(d_mem))
		print(cycle)
		input()

	# 	print()
	# 	print(sim.inspect_mem(rf))
	# 	print(sim.inspect(memwrite))
	# 	print(sim.inspect_mem(d_mem))
	# 	print("pc:", sim.inspect(pc))
	# 	print(sim.inspect(op), sim.inspect(func))
	# 	print(sim.inspect(regdst), sim.inspect(branch), sim.inspect(regwrite), sim.inspect(alu_src), sim.inspect(memwrite), sim.inspect(memtoreg), sim.inspect(alu_op))

	# # Use render_trace() to debug if your code doesn't work.
	# # sim_trace.render_trace()

	# # You can also print out the register file or memory like so if you want to debug:
	# # print(sim.inspect_mem(d_mem))
	# # print(sim.inspect_mem(rf))

	# # Perform some sanity checks to see if your program worked correctly
	# print(sim.inspect_mem(d_mem)[0] == 10)
	print(sim.inspect_mem(d_mem))    # $v0 = rf[8]
	print(sim.inspect_mem(rf))    # $v0 = rf[8]
	# print('Passed!')