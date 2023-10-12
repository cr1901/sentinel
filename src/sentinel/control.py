from amaranth import Signal, Elaboratable, Module
from amaranth.lib.wiring import Component, Signature, In, Out

from .decode import OpcodeType, DecodeControlGasket
from .alu import AluCtrlSignature
from .ucoderom import UCodeROM
from .datapath import GPControlSignature, PCControlSignature

from .ucodefields import JmpType, CondTest


ControlSignature = Signature({
    "alu": Out(AluCtrlSignature),
    "decode": In(DecodeControlGasket.signature),
    "gp": Out(GPControlSignature),
    "pc": Out(PCControlSignature),
})


class Control(Component):
    signature = ControlSignature

    def __init__(self, ucode: str = ""):
        self.ucoderom = UCodeROM(main_file=ucode)
        # Enums from microcode ROM.
        self.sequencer = Sequencer(self.ucoderom)
        self.mapper = Mapper()

        # Control inputs
        self.vec_adr = Signal.like(self.ucoderom.fields.target)
        # Direct 5 high bits of opcode.
        self.opcode = Signal(OpcodeType)
        # funct* fields converted to a 4-bit ID.
        self.requested_op = Signal(4)
        # funct12 ECALL (0) or EBREAK (1)
        self.e_type = Signal(1)
        # Load should zero-extend, not sign extend.
        # self.load_unsigned = Signal(1)

        # Predicates for test mux.
        self.mem_valid = Signal()
        # OR of illegal insn, ecall, ebreak, misaligned load/store,
        # misaligned insn.
        self.exception = Signal()
        self.interrupt = Signal()
        self.raw_test = Signal()  # Output of test mux.
        self.test = Signal()  # Possibly-inverted test result.

        # Internally-used microcode signals
        self.target = Signal.like(self.ucoderom.fields.target)
        self.jmp_type = Signal.like(self.ucoderom.fields.jmp_type)
        self.cond_test = Signal.like(self.ucoderom.fields.cond_test)
        self.invert_test = Signal.like(self.ucoderom.fields.invert_test)

        # Control outputs- mostly from microcode ROM.
        self.a_src = Signal.like(self.ucoderom.fields.a_src)
        self.b_src = Signal.like(self.ucoderom.fields.b_src)
        self.src_op = Signal.like(self.ucoderom.fields.src_op)
        self.mem_req = Signal.like(self.ucoderom.fields.mem_req)
        self.mem_sel = Signal.like(self.ucoderom.fields.mem_sel)
        self.latch_adr = Signal.like(self.ucoderom.fields.latch_adr)
        self.latch_data = Signal.like(self.ucoderom.fields.latch_data)
        self.write_mem = Signal.like(self.ucoderom.fields.write_mem)
        self.insn_fetch = Signal.like(self.ucoderom.fields.insn_fetch)
        self.reg_r_sel = Signal.like(self.ucoderom.fields.reg_r_sel)

        super().__init__()

    def elaborate(self, platform):
        m = Module()

        m.submodules.ucoderom = self.ucoderom
        m.submodules.sequencer = self.sequencer
        m.submodules.mapper = self.mapper

        # Propogate ucode control signals
        m.d.comb += [
            self.target.eq(self.ucoderom.fields.target),
            self.jmp_type.eq(self.ucoderom.fields.jmp_type),
            self.cond_test.eq(self.ucoderom.fields.cond_test),
            self.invert_test.eq(self.ucoderom.fields.invert_test),
            self.pc.action.eq(self.ucoderom.fields.pc_action),
            self.gp.reg_read.eq(self.ucoderom.fields.reg_read),
            self.gp.reg_write.eq(self.ucoderom.fields.reg_write),
            self.reg_r_sel.eq(self.ucoderom.fields.reg_r_sel),
            self.a_src.eq(self.ucoderom.fields.a_src),
            self.b_src.eq(self.ucoderom.fields.b_src),
            self.src_op.eq(self.ucoderom.fields.src_op),
            self.alu.op.eq(self.ucoderom.fields.alu_op),
            self.alu.imod.eq(self.ucoderom.fields.alu_i_mod),
            self.alu.omod.eq(self.ucoderom.fields.alu_o_mod),
            self.mem_req.eq(self.ucoderom.fields.mem_req),
            self.mem_sel.eq(self.ucoderom.fields.mem_sel),
            self.latch_adr.eq(self.ucoderom.fields.latch_adr),
            self.latch_data.eq(self.ucoderom.fields.latch_data),
            self.write_mem.eq(self.ucoderom.fields.write_mem),
            self.insn_fetch.eq(self.ucoderom.fields.insn_fetch),
        ]

        # Connect ucode ROM to sequencer
        m.d.comb += [
            self.ucoderom.addr.eq(self.sequencer.adr),
            self.sequencer.target.eq(self.target),
            self.sequencer.jmp_type.eq(self.jmp_type)
        ]

        # Connect mapper to Control.
        m.d.comb += [
            self.mapper.opcode.eq(self.opcode),
            self.mapper.requested_op.eq(self.requested_op),
            self.mapper.e_type.eq(self.e_type),
        ]

        # Connect sequencer to Control/Mapper.
        m.d.comb += [
            # Test not implemented yet!
            self.sequencer.test.eq(self.test),
            self.sequencer.opcode_adr.eq(self.mapper.map_adr),
            self.sequencer.vec_adr.eq(self.vec_adr),
            self.sequencer.req_op.eq(self.requested_op)
        ]

        # Test mux
        with m.Switch(self.cond_test):
            with m.Case(CondTest.INTR):
                m.d.comb += self.raw_test.eq(self.interrupt)
            with m.Case(CondTest.EXCEPTION):
                m.d.comb += self.raw_test.eq(self.exception)
            with m.Case(CondTest.CMP_ALU_O_5_LSBS_ZERO):
                m.d.comb += self.raw_test.eq(self.alu.lsbs_5_zero)
            with m.Case(CondTest.CMP_ALU_O_ZERO):
                m.d.comb += self.raw_test.eq(self.alu.zero)
            with m.Case(CondTest.MEM_VALID):
                m.d.comb += self.raw_test.eq(self.mem_valid)
            with m.Case(CondTest.TRUE):
                m.d.comb += self.raw_test.eq(1)

        with m.If(self.invert_test):
            m.d.comb += self.test.eq(~self.raw_test)
        with m.Else():
            m.d.comb += self.test.eq(self.raw_test)

        return m


# Map from Opcode to start location in UCodeROM
class Mapper(Elaboratable):
    def __init__(self):
        self.opcode = Signal(OpcodeType)
        self.requested_op = Signal(4)
        self.e_type = Signal(1)
        self.map_adr = Signal(8)

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.opcode):
            with m.Case(OpcodeType.OP_IMM):
                m.d.comb += self.map_adr.eq(8)
            with m.Case(OpcodeType.OP):
                m.d.comb += self.map_adr.eq(9)
            with m.Case(OpcodeType.LUI):
                m.d.comb += self.map_adr.eq(10)
            with m.Case(OpcodeType.MISC_MEM):
                m.d.comb += self.map_adr.eq(11)
            with m.Case(OpcodeType.AUIPC):
                m.d.comb += self.map_adr.eq(12)
            with m.Case(OpcodeType.JAL):
                m.d.comb += self.map_adr.eq(13)
            with m.Case(OpcodeType.STORE):
                m.d.comb += self.map_adr.eq(14)
            with m.Case(OpcodeType.LOAD):
                m.d.comb += self.map_adr.eq(15)
            with m.Case(OpcodeType.JALR):
                m.d.comb += self.map_adr.eq(16)
            with m.Case(OpcodeType.BRANCH):
                m.d.comb += self.map_adr.eq(17)
            with m.Case(OpcodeType.SYSTEM):
                m.d.comb += self.map_adr.eq(128)

        return m


# Microprogram address generation.
class Sequencer(Elaboratable):
    def __init__(self, ucoderom):
        # Get info required from ucoderom.
        self.target = Signal.like(ucoderom.fields.target)
        self.jmp_type = Signal.like(ucoderom.fields.jmp_type)

        self.adr = Signal.like(ucoderom.fields.target)
        self.opcode_adr = Signal.like(self.adr)
        self.vec_adr = Signal.like(self.adr)
        self.next_adr = Signal.like(self.adr)
        self.req_op = Signal(4)

        # If test succeeds, branch in target/vec_adr is taken, otherwise
        # next_adr.
        self.test = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.sync += self.next_adr.eq(self.adr + 1)

        with m.Switch(self.jmp_type):
            # Also handles JumpType.NOP
            with m.Case(JmpType.CONT):
                m.d.comb += self.adr.eq(self.next_adr)
            with m.Case(JmpType.MAP):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(self.opcode_adr)
            with m.Case(JmpType.DIRECT):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(self.next_adr)
            with m.Case(JmpType.MAP_FUNCT):
                m.d.comb += self.adr.eq(self.target + self.req_op)
            with m.Case(JmpType.DIRECT_ZERO):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(0)

        return m
