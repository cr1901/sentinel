"""Arithmetic Logic Unit (ALU) Components."""

from .align import ReadDataAlign
from .csr import MCause
from .ucodefields import OpType, ALUIMod, ALUOMod, ASrc, BSrc, MemSel, \
    MemExtend

from amaranth import Elaboratable, Signal, Module, C, Cat
from amaranth.lib.wiring import Component, Signature, In, Out


class ASrcMux(Component):
    """Latch one of many :attr:`ALU A input <sentinel.alu.ALU.a>` sources.

    The ALU does not have registered inputs; the
    :attr:`~sentinel.alu.ASrcMux.data` output is registered and feeds
    immediately into the ALU A input.

    Attributes
    ----------
    latch: In(1)
        When asserted, latch the :attr:`selected <sentinel.alu.ASrcMux.sel>`
        input into :attr:`~sentinel.alu.ASrcMux.data` on the next clock edge.
    sel: In(ASrc)
        Select input. See :class:`~sentinel.ucodefields.ASrc`.
    gp: In(32)
        Input source. Register from the
        :class:`register file <sentinel.datapath.RegFile>`
        whose value is currently on the read port (e.g. the read address was
        supplied on the previous clock cycle).
    imm: In(32)
        Input source. :attr:`Decoded immediate <sentinel.decoder.Decode.imm>`
        from current instruction.
    alu: In(32)
        Input source. :attr:`ALU output <sentinel.alu.ALU.o>`, fed back as an
        input.
    data: Out(32)
        The output. When :attr:`~sentinel.alu.ASrcMux.latch` is asserted, the
        data input selected by :attr:`~sentinel.alu.ASrcMux.sel` will appear
        here on the next clock cycle.
    """

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

    def elaborate(self, platform):  # noqa: D102
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
    """Latch one of many :attr:`ALU B input <sentinel.alu.ALU.b>` sources.

    The ALU does not have registered inputs; the
    :attr:`~sentinel.alu.BSrcMux.data` output is registered and feeds
    immediately into the ALU B input.

    When requested, this module will automatically move/align the top 16-bits
    of the 32-bit :attr:`read data bus input <BSrcMux.dat_r>` to the bottom
    16-bits, or any of of 3 high bytes into the bottom 8-bits. The mux will
    latch the aligned data when :attr:`selected <sentinel.alu.BSrcMux.sel>`
    rather than the original input data.

    Attributes
    ----------
    latch: In(1)
        When asserted, latch the :attr:`selected <sentinel.alu.BSrcMux.sel>`
        input into :attr:`~sentinel.alu.BSrcMux.data` on the next clock edge.
    sel: In(BSrc)
        Select input. See :class:`~sentinel.ucodefields.BSrc`.
    mem_sel: In(MemSel)
        Select width of :attr:`dat_r` to be output onto :attr:`data`.
    mem_extend: In(MemExtend)
        When :attr:`mem_sel` is less than word width, choose whether to sign
        or zero-extend :attr:`dat_r` when it's output onto :attr:`data`.
    data_adr: In(32)
        Contents of the internal address register latched by
        :class:`~sentinel.ucodefields.LatchAdr`. Used for deciding how to
        align :attr:`dat_r`.
    gp: In(32)
        Input source. Register from the
        :class:`register file <sentinel.datapath.RegFile>`
        whose value is currently on the read port (e.g. the read address was
        supplied on the previous clock cycle).
    imm: In(32)
        Input source. :attr:`Decoded immediate <sentinel.decoder.Decode.imm>`
        from current instruction.
    pc: In(30)
        Input source. Current contents of the
        :class:`Program Counter <sentinel.datapath.ProgramCounter>`.
    dat_r: In(32)
        Input source. Current contents of the *unregistered* ``dat_r``
        in :attr:`Top's Wishbone Bus <sentinel.Top.top.bus>`. Only valid when
        qualified by :attr:`~CondTest.MEM_VALID`.

        As an input, ``dat_r`` is always 32-bit aligned. The mux contains
        internal alignment circuitry when a read of 8 or 16-bits on a less than
        32-bit alignment is requested. When
        :attr:`selected <sentinel.alu.BSrcMux.sel>`, the mux will latched this
        modified/aligned data into `~BSrcMux.data`.
    csr_imm: In(5)
        Input source. :attr:`Decoded src_a <sentinel.decoder.Decode.src_a>`
        from the current instruction, which for CSR instructions is reused
        for specifying 5-bit CSR immediates.
    csr: In(32)
        Input source. Register from the
        :class:`CSR file <sentinel.datapath.CSRFile>`
        whose value is currently on the read port (e.g. the read address was
        supplied on the previous clock cycle).
    mcause: In(MCause)
        Input source. Current mcause as determined by
        :class:`~sentinel.exception.ExceptionRouter`.
    data: Out(32)
        The output. When :attr:`~sentinel.alu.BSrcMux.latch` is asserted, the
        data input selected by :attr:`~sentinel.alu.BSrcMux.sel` will appear
        here on the next clock cycle.
    """

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

    def elaborate(self, platform):  # noqa: D102
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

    def elaborate(self, platform):  # noqa: D102
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
    """Basic Arithmetic Logic Unit.

    The ALU Performs "A OP B", where "OP" is chosen by :attr:`ctrl`.

    Attributes
    ----------
    a: In(width)
        ALU A input.
    b: In(width)
        ALU B input.
    o: Out(width)
        ALU output. Valid 1 clock cycle after inputs.
    ctrl: In(AluCtrlSignature)
        Choose the ALU op to perform this cycle, possibly modifying the output.
        Also check if the ALU op on the previous cycle was ``0``.
    """

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

    def elaborate(self, platform):  # noqa: D102
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
