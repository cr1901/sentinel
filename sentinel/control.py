from nmigen import *

from .decode import OpcodeType
from .alu import OpType
from .ucoderom import UCodeROM

class Control(Elaboratable):
    def __init__(self):
        self.ucoderom = UCodeROM()
        self.sequencer = Sequencer(self.ucoderom)
        self.mapper = Mapper()

        # Control inputs
        self.vec_adr = Signal.like(self.ucoderom.signals["target"])
        # Direct 5 high bits of opcode.
        self.opcode = Signal(OpcodeType)
        # Like ALU.OpType, but is direct concatenation of funct3 and funct7
        # opcode bits.
        self.requested_op = Signal(4)
        # funct12 ECALL (0) or EBREAK (1)
        self.e_type = Signal(1)
        # Load should zero-extend, not sign extend.
        # self.load_unsigned = Signal(1)

        # Predicates for test mux.
        self.alu_ready = Signal()
        self.mem_valid = Signal()
        self.compare_okay = Signal()
        # OR of illegal insn, ecall, ebreak, misaligned load/store,
        # misaligned insn.
        self.exception = Signal()
        self.interrupt = Signal()
        self.raw_test = Signal() # Output of test mux.
        self.test = Signal() # Possibly-inverted test result.

        # Internally-used microcode signals
        self.target = Signal.like(self.ucoderom.signals["target"])
        self.jmp_type = Signal.like(self.ucoderom.signals["jmp_type"])
        self.cond_test = Signal.like(self.ucoderom.signals["cond_test"])
        self.invert_test = Signal.like(self.ucoderom.signals["invert_test"])

        # Control outputs- mostly from microcode ROM.
        self.pc_action = Signal.like(self.ucoderom.signals["pc_action"])
        self.a_src = Signal.like(self.ucoderom.signals["a_src"])
        self.b_src = Signal.like(self.ucoderom.signals["b_src"])
        self.alu_op = Signal.like(self.ucoderom.signals["alu_op"])
        self.reg_op = Signal.like(self.ucoderom.signals["reg_op"])
        self.mem_req = Signal.like(self.ucoderom.signals["mem_req"])
        self.do_decode = Signal.like(self.ucoderom.signals["do_decode"])

        # Enums from microcode ROM.
        self.CondTest = self.ucoderom.fields["cond_test"]

    def elaborate(self, platform):
        m = Module()

        m.submodules.ucoderom = self.ucoderom
        m.submodules.sequencer = self.sequencer
        m.submodules.mapper = self.mapper

        # Propogate ucode control signals
        m.d.comb += [
            self.target.eq(self.ucoderom.signals["target"]),
            self.jmp_type.eq(self.ucoderom.signals["jmp_type"]),
            self.cond_test.eq(self.ucoderom.signals["cond_test"]),
            self.invert_test.eq(self.ucoderom.signals["invert_test"]),
            self.pc_action.eq(self.ucoderom.signals["pc_action"]),
            self.a_src.eq(self.ucoderom.signals["a_src"]),
            self.b_src.eq(self.ucoderom.signals["b_src"]),
            self.alu_op.eq(self.ucoderom.signals["alu_op"]),
            self.reg_op.eq(self.ucoderom.signals["reg_op"]),
            self.mem_req.eq(self.ucoderom.signals["mem_req"]),
            self.do_decode.eq(self.ucoderom.signals["do_decode"])
        ]

        # Connect ucode ROM to sequencer
        m.d.comb += [
            self.ucoderom.adr.eq(self.sequencer.adr),
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
            self.sequencer.vec_adr.eq(self.vec_adr)
        ]

        # Test mux
        with m.Switch(self.cond_test):
            with m.Case(self.CondTest.false):
                m.d.comb += self.raw_test.eq(0)
            with m.Case(self.CondTest.intr):
                m.d.comb += self.raw_test.eq(self.interrupt)
            with m.Case(self.CondTest.exception):
                m.d.comb += self.raw_test.eq(self.exception)
            with m.Case(self.CondTest.cmp_okay):
                m.d.comb += self.raw_test.eq(self.compare_okay)
            with m.Case(self.CondTest.mem_valid):
                m.d.comb += self.raw_test.eq(self.mem_valid)
            with m.Case(self.CondTest.alu_ready):
                m.d.comb += self.raw_test.eq(self.alu_ready)
            with m.Case(self.CondTest.true):
                m.d.comb += self.raw_test.eq(1)

        with m.If(self.invert_test):
            m.d.comb += self.test.eq(~self.raw_test)
        with m.Else():
            m.d.comb += self.test.eq(self.raw_test)

        return m

    def ports(self):
        # TODO: Make internally-used signals visible to outside modules
        # for custom insns.
        return [self.vec_adr, self.opcode, self.alu_op, self.test,
            self.pc_action, self.a_src, self.b_src, self.alu_op,
            self.reg_op, self.mem_req, self.do_decode]

    def sim_hooks(self, sim):
        pass


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
                m.d.comb += self.map_adr.eq(8 + self.requested_op)
            with m.Case(OpcodeType.SYSTEM):
                m.d.comb += self.map_adr.eq(128 + self.e_type)

        return m


# Microprogram address generation.
class Sequencer(Elaboratable):
    def __init__(self, ucoderom):
        # Get info required from ucoderom.
        self.target = Signal.like(ucoderom.signals["target"])
        self.jmp_type = Signal.like(ucoderom.signals["jmp_type"])
        self.JumpType = ucoderom.fields["jmp_type"]

        self.adr = Signal.like(ucoderom.signals["target"])
        self.opcode_adr = Signal.like(self.adr)
        self.vec_adr = Signal.like(self.adr)
        self.next_adr = Signal.like(self.adr)

        # If test succeeds, branch in target/vec_adr is taken, otherwise
        # next_adr.
        self.test = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.sync += self.next_adr.eq(self.adr + 1)

        with m.Switch(self.jmp_type):
            # Also handles self.JumpType.nop
            with m.Case(self.JumpType.cont):
                m.d.comb += self.adr.eq(self.next_adr)
            with m.Case(self.JumpType.map):
                m.d.comb += self.adr.eq(self.opcode_adr)
            with m.Case(self.JumpType.direct):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(self.next_adr)
            with m.Case(self.JumpType.vec):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.vec_adr)
                with m.Else():
                    m.d.comb += self.adr.eq(self.next_adr)

        return m
