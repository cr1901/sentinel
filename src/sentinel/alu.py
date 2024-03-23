from .align import ReadDataAlign
from .csr import MCause
from .ucodefields import OpType, ALUIMod, ALUOMod, ASrc, BSrc, MemSel, \
    MemExtend

from amaranth import Elaboratable, Signal, Module, C, Cat
from amaranth.lib.wiring import Component, Signature, In, Out


class ASrcMux(Component):
    def __init__(self):
        sig = {
            "latch": Out(1),
            "sel": Out(ASrc),
            "gp": Out(32),
            "imm": Out(32),
            "alu": Out(32),
            "data": In(32)
        }
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        with m.If(self.latch):
            with m.Switch(self.sel):
                with m.Case(ASrc.GP):
                    m.d.sync += self.data.eq(self.gp)
                with m.Case(ASrc.IMM):
                    m.d.sync += self.data.eq(self.imm)
                with m.Case(ASrc.ZERO):
                    m.d.sync += self.data.eq(0)
                with m.Case(ASrc.ALU_O):
                    m.d.sync += self.data.eq(self.alu)
                with m.Case(ASrc.FOUR):
                    m.d.sync += self.data.eq(4)
                with m.Case(ASrc.NEG_ONE):
                    m.d.sync += self.data.eq(C(-1, 32))
                with m.Case(ASrc.THIRTY_ONE):
                    m.d.sync += self.data.eq(31)

        return m


class BSrcMux(Component):
    def __init__(self):
        sig = {
            "latch": Out(1),
            "sel": Out(BSrc),

            "mem_sel": Out(MemSel),
            "mem_extend": Out(MemExtend),
            "data_adr": Out(32),

            "gp": Out(32),
            "imm": Out(32),
            "pc": Out(30),
            "dat_r": Out(32),
            "csr_imm": Out(5),
            "csr": Out(32),
            "mcause": Out(MCause),
            "data": In(32)
        }
        self.rdata_align = ReadDataAlign()
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        m.submodules.rdata_align = self.rdata_align

        m.d.comb += [
            self.rdata_align.mem_sel.eq(self.mem_sel),
            self.rdata_align.mem_extend.eq(self.mem_extend),
            self.rdata_align.latched_adr.eq(self.data_adr),
            self.rdata_align.wb_dat_r.eq(self.dat_r)
        ]

        with m.If(self.latch):
            with m.Switch(self.sel):
                with m.Case(BSrc.GP):
                    m.d.sync += self.data.eq(self.gp)
                with m.Case(BSrc.IMM):
                    m.d.sync += self.data.eq(self.imm)
                with m.Case(BSrc.ONE):
                    m.d.sync += self.data.eq(1)
                with m.Case(BSrc.PC):
                    m.d.sync += self.data.eq(Cat(C(0, 2), self.pc))
                with m.Case(BSrc.DAT_R):
                    m.d.sync += self.data.eq(self.rdata_align.data)
                with m.Case(BSrc.CSR_IMM):
                    m.d.sync += self.data.eq(self.csr_imm)
                with m.Case(BSrc.CSR):
                    m.d.sync += self.data.eq(self.csr)
                with m.Case(BSrc.MCAUSE_LATCH):
                    m.d.sync += self.data.eq(self.mcause)

        return m


class Unit(Elaboratable):
    def __init__(self, width, op):
        self.a = Signal(width)
        self.b = Signal(width)
        self.o = Signal(width)
        self.op = op

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.op(self.a, self.b))
        return m


class Adder(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a + b)


class Subtractor(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a - b)


class AND(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a & b)


class OR(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a | b)


class XOR(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, b: a ^ b)


class ShiftLogicalLeft(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, _: a << 1)


class ShiftLogicalRight(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, _: a >> 1)


class ShiftArithmeticRight(Unit):
    def __init__(self, width):
        super().__init__(width, lambda a, _: a.as_signed() >> 1)


AluCtrlSignature = Signature({
    "op": Out(OpType),
    "imod": Out(ALUIMod),
    "omod": Out(ALUOMod),
    "zero": In(1)
})


class ALU(Component):
    # Assumes: op is held steady for duration of op.
    def __init__(self, width: int):
        self.width = width
        super().__init__(Signature({
            "a": Out(self.width),
            "b": Out(self.width),
            "o": In(self.width),
            "ctrl": Out(AluCtrlSignature),
        }).flip())

        ###

        self.o_mux = Signal(width)

        self.add = Adder(width)
        self.sub = Subtractor(width + 1)
        self.and_ = AND(width)
        self.or_ = OR(width)
        self.xor = XOR(width)
        self.sll = ShiftLogicalLeft(width)
        self.srl = ShiftLogicalRight(width)
        self.sar = ShiftArithmeticRight(width)

    def elaborate(self, platform):
        m = Module()
        m.submodules.add = self.add
        m.submodules.sub = self.sub
        m.submodules.and_ = self.and_
        m.submodules.or_ = self.or_
        m.submodules.xor = self.xor
        m.submodules.sll = self.sll
        m.submodules.srl = self.srl
        m.submodules.sal = self.sar

        mod_a = Signal.like(self.a)
        mod_b = Signal.like(self.b)

        m.d.comb += [
            mod_a.eq(self.a),
            mod_b.eq(self.b)
        ]

        with m.If(self.ctrl.imod == ALUIMod.INV_MSB_A_B):
            m.d.comb += [
                mod_a[-1].eq(~self.a[-1]),
                mod_b[-1].eq(~self.b[-1]),
            ]

        for submod in [self.add, self.sub, self.and_, self.or_, self.xor,
                       self.sll, self.srl, self.sar]:
            m.d.comb += [
                submod.a.eq(mod_a),
                submod.b.eq(mod_b),
            ]

        with m.Switch(self.ctrl.op):
            with m.Case(OpType.ADD):
                m.d.comb += self.o_mux.eq(self.add.o)
            with m.Case(OpType.SUB):
                m.d.comb += self.o_mux.eq(self.sub.o)
            with m.Case(OpType.AND):
                m.d.comb += self.o_mux.eq(self.and_.o)
            with m.Case(OpType.OR):
                m.d.comb += self.o_mux.eq(self.or_.o)
            with m.Case(OpType.XOR):
                m.d.comb += self.o_mux.eq(self.xor.o)
            with m.Case(OpType.SLL):
                m.d.comb += self.o_mux.eq(self.sll.o)
            with m.Case(OpType.SRL):
                m.d.comb += self.o_mux.eq(self.srl.o)
            with m.Case(OpType.SRA):
                m.d.comb += self.o_mux.eq(self.sar.o)
            with m.Case(OpType.CMP_LTU):
                m.d.comb += self.o_mux.eq(self.sub.o[32])

        m.d.sync += self.o.eq(self.o_mux)
        with m.If(self.ctrl.omod == ALUOMod.INV_LSB_O):
            m.d.sync += self.o[0].eq(~self.o_mux[0])
        with m.Elif(self.ctrl.omod == ALUOMod.CLEAR_LSB_O):
            m.d.sync += self.o[0].eq(0)

        # TODO: LSBS_2_ZERO for JALR/JAL misaligned exceptions?
        m.d.comb += self.ctrl.zero.eq(self.o == 0)

        return m
