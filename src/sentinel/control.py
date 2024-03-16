from amaranth import Signal, Elaboratable, Module
from amaranth.lib.wiring import Component, Signature, In, Out

from .decode import Insn
from .alu import AluCtrlSignature
from .ucoderom import UCodeROM
from .datapath import GPControlSignature, PCControlSignature, \
    CSRControlSignature

from .ucodefields import JmpType, CondTest

from typing import TextIO, Optional


ControlSignature = Signature({
    "alu": Out(AluCtrlSignature),
    "decode": In(1),
    "gp": Out(GPControlSignature),
    "pc": Out(PCControlSignature),
    "csr": Out(CSRControlSignature)
})


class Control(Component):
    def __init__(self, ucode: Optional[TextIO] = None):
        self.ucoderom = UCodeROM(main_file=ucode)
        # Enums from microcode ROM.
        self.sequencer = Sequencer(self.ucoderom)

        # Control inputs
        self.vec_adr = Signal.like(self.ucoderom.fields.target)
        # Direct 5 high bits of opcode.
        self.opcode = Signal(Insn.OpcodeType)
        # RISCV major/minor opcodes compressed into 8 bits to index into
        # ucode ROM. Chosen through trial and error.
        self.requested_op = Signal(8)
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
        self.latch_a = Signal.like(self.ucoderom.fields.latch_a)
        self.latch_b = Signal.like(self.ucoderom.fields.latch_b)
        self.mem_req = Signal.like(self.ucoderom.fields.mem_req)
        self.mem_sel = Signal.like(self.ucoderom.fields.mem_sel)
        self.latch_adr = Signal.like(self.ucoderom.fields.latch_adr)
        self.latch_data = Signal.like(self.ucoderom.fields.latch_data)
        self.write_mem = Signal.like(self.ucoderom.fields.write_mem)
        self.insn_fetch = Signal.like(self.ucoderom.fields.insn_fetch)
        self.reg_r_sel = Signal.like(self.ucoderom.fields.reg_r_sel)
        self.reg_w_sel = Signal.like(self.ucoderom.fields.reg_w_sel)
        self.csr_sel = Signal.like(self.ucoderom.fields.csr_sel)
        self.mem_extend = Signal.like(self.ucoderom.fields.mem_extend)
        self.except_ctl = Signal.like(self.ucoderom.fields.except_ctl)

        super().__init__({
            "alu": Out(AluCtrlSignature),
            "decode": In(1),
            "gp": Out(GPControlSignature),
            "pc": Out(PCControlSignature),
            "csr": Out(CSRControlSignature)
        })

    def elaborate(self, platform):
        m = Module()

        m.submodules.ucoderom = self.ucoderom
        m.submodules.sequencer = self.sequencer

        # Propogate ucode control signals
        m.d.comb += [
            self.target.eq(self.ucoderom.fields.target),
            self.jmp_type.eq(self.ucoderom.fields.jmp_type),
            self.cond_test.eq(self.ucoderom.fields.cond_test),
            self.invert_test.eq(self.ucoderom.fields.invert_test),
            self.pc.action.eq(self.ucoderom.fields.pc_action),
            self.gp.reg_read.eq(self.ucoderom.fields.reg_read),
            self.gp.reg_write.eq(self.ucoderom.fields.reg_write),
            self.csr.op.eq(self.ucoderom.fields.csr_op),
            self.reg_r_sel.eq(self.ucoderom.fields.reg_r_sel),
            self.reg_w_sel.eq(self.ucoderom.fields.reg_w_sel),
            self.csr_sel.eq(self.ucoderom.fields.csr_sel),
            self.a_src.eq(self.ucoderom.fields.a_src),
            self.b_src.eq(self.ucoderom.fields.b_src),
            self.latch_a.eq(self.ucoderom.fields.latch_a),
            self.latch_b.eq(self.ucoderom.fields.latch_b),
            self.alu.op.eq(self.ucoderom.fields.alu_op),
            self.alu.imod.eq(self.ucoderom.fields.alu_i_mod),
            self.alu.omod.eq(self.ucoderom.fields.alu_o_mod),
            self.mem_req.eq(self.ucoderom.fields.mem_req),
            self.mem_sel.eq(self.ucoderom.fields.mem_sel),
            self.latch_adr.eq(self.ucoderom.fields.latch_adr),
            self.latch_data.eq(self.ucoderom.fields.latch_data),
            self.write_mem.eq(self.ucoderom.fields.write_mem),
            self.insn_fetch.eq(self.ucoderom.fields.insn_fetch),
            self.mem_extend.eq(self.ucoderom.fields.mem_extend),
            self.except_ctl.eq(self.ucoderom.fields.except_ctl)
        ]

        # Connect ucode ROM to sequencer
        m.d.comb += [
            self.ucoderom.addr.eq(self.sequencer.adr),
            self.sequencer.target.eq(self.target),
            self.sequencer.jmp_type.eq(self.jmp_type)
        ]

        # Connect sequencer to Control.
        m.d.comb += [
            self.sequencer.test.eq(self.test),
            self.sequencer.opcode_adr.eq(self.requested_op),
            self.sequencer.vec_adr.eq(self.vec_adr),
        ]

        # Test mux
        with m.Switch(self.cond_test):
            with m.Case(CondTest.EXCEPTION):
                m.d.comb += self.raw_test.eq(self.exception)
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


# Microprogram address generation.
class Sequencer(Elaboratable):
    def __init__(self, ucoderom):
        # Get info required from ucoderom.
        self.target = Signal.like(ucoderom.fields.target)
        self.jmp_type = Signal.like(ucoderom.fields.jmp_type)

        # upc == 2 is reset; 0 is "do insn fetch". 0 is so important, that
        # it's an implied target in DIRECT_ZERO.
        self.adr = Signal.like(ucoderom.fields.target, init=2)
        self.opcode_adr = Signal.like(self.adr)
        self.vec_adr = Signal.like(self.adr)
        self.next_adr = Signal.like(self.adr)
        self.ice40_rst_guard = Signal(init=1)

        # If test succeeds, branch in target/vec_adr is taken, otherwise
        # next_adr.
        self.test = Signal()

    def elaborate(self, platform):
        m = Module()

        m.d.sync += self.next_adr.eq(self.adr + 1)
        m.d.sync += self.ice40_rst_guard.eq(0)

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
            with m.Case(JmpType.DIRECT_ZERO):
                with m.If(self.test):
                    m.d.comb += self.adr.eq(self.target)
                with m.Else():
                    m.d.comb += self.adr.eq(0)

        # self.adr is combinational, and indirectly gets its value from the
        # read outputs (latches) of the block RAM holding the ucode
        # (particularly the JumpType and CondTest fields); the read latches are
        # reset_less. We don't want self.adr to take on random transient values
        # in read latches after POR because we need address 2 to be the first
        # ucode ROM location read after sync reset ends. Feeding self.adr with
        # the reset value of self.next_adr works fine.
        #
        # In principle this line is not needed, but iCE40 has a BRAM bug that
        # prevents the intended logic self.adr logic from firing without this
        # line. Read below for more info.
        #
        # Detailed background:
        #
        # This line is not needed in principle because Amaranth/yosys forces
        # the read value of a block RAM to 0 for the first cycle after POR ends
        # ("plugging in the board", "resetting the board", or otherwise):
        # https://github.com/amaranth-lang/amaranth/blob/f9da3c0d166dd2be189945dca5a94e781e74afeb/amaranth/hdl/mem.py#L153  # noqa: E501
        #
        # 0 in the relevant ucode BRAM field corresponds to JmpType.CONT,
        # which is equivalent to the below code. 0 in the other ucode fields
        # are mostly no-ops as well, and don't affect anything we care about.
        # So on subsequent clock cycles until reset of self.next_adr ends, the
        # block RAM latches will hold the value of ucode address 2, which
        # "conveniently" also sets the relevant ucode field to JumpType.CONT.
        #
        # However, on iCE40 there's a BRAM bug where BRAM doesn't initialize
        # properly until ~3us after internal POR. This will be many clock
        # cycles after POR is released by iCE40. By default, Amaranth will
        # generate a POR circuit that accomodates this behavior by holding the
        # sync domain in rst for 15 us after POR ends). But self.adr feeds
        # back into the ucode BRAM, which in turns feeds the _reset-less_ read
        # latches, without any intermediate storage elements. So the POR
        # circuit does not apply.
        #
        # Without this line, observed behavior on iCE40 is interesting; for
        # the first clock cycle after POR ends, self.adr is 2. This is the
        # aforementioned Amaranth/yosys behavior correctly firing.
        # However on subsequent clock cycles, the ucode outputs will take on
        # _the values the read-latches had just before an internal POR was
        # triggered_ by e.g. "iceprog -t". Without this line, if the jump_type
        # ucode field from the read latches isn't JmpType.CONT, self.adr will
        # read garbage.
        #
        # Once the iCE40 BRAM initializes properly, nothing except
        # self.next_adr holds self.adr at its current position during rst.
        # Thus, the ucode program will start executing until either:
        #
        # * The ucode program gets stuck waiting for insn memory at address 0.
        # * The jmp_type ucode field of the current insn is JumpType.CONT,
        #   which will stall the program at address 2 until sync reset is
        #   released.
        #
        # If the ucode makes it back to address 2, running the ucode program
        # during reset probably has no ill effects. Unfortunately, if we
        # end at address 0, we then skip the initialization ucode that ensures
        # x0 is actually 0, essentially breaking the core.
        #
        # This behavior is not consistent, but happens very often after resets
        # triggered by e.g. "iceprog -t", and not so much for resets triggered
        # by "plugging a board in".
        #
        # Speculation follows...
        #
        # Perhaps "rest values" of read latches are 0, but hysteresis causes
        # initial values to change after POR from "plugging in the board"? The
        # LA traces I've taken makes me believe that the BRAM bug is more
        # correctly described as outputting stale values from the read latches
        # for up to 3us after POR, rather than outputting 0 during those 3us,
        # as the bug is usually described.
        with m.If(self.ice40_rst_guard):
            m.d.comb += self.adr.eq(self.next_adr)

        return m
