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
    """

    #: When asserted, latch the :attr:`selected <sentinel.alu.ASrcMux.sel>`
    #: input into :attr:`~sentinel.alu.ASrcMux.data` on the next clock edge.
    latch: In(1)
    #: In(ASrc): Select input.
    sel: In(ASrc)
    #: Input source. Register from the
    #: :class:`register file <sentinel.datapath.RegFile>`
    #: whose value is currently on the read port (e.g. the read address was
    #: supplied on the previous clock cycle).
    gp: In(32)
    #: Input source. :attr:`Decoded immediate <sentinel.decoder.Decode.imm>`
    #: from current instruction.
    imm: In(32)
    #: Input source. :attr:`Decoded immediate <sentinel.decoder.Decode.imm>`
    #: from current instruction.
    alu: In(32)
    #: The output. When :attr:`~sentinel.alu.ASrcMux.latch` is asserted, the
    #: data input selected by :attr:`~sentinel.alu.ASrcMux.sel` will appear
    #: here on the next clock cycle.
    data: Out(32)

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

    When requested, this module will automatically
    :class:`move/align <sentinel.align.ReadDataAlign>` the top 16-bits
    of the 32-bit :attr:`read data bus input <BSrcMux.dat_r>` to the bottom
    16-bits, or any of of 3 high bytes into the bottom 8-bits. The mux will
    latch the aligned data when :attr:`selected <sentinel.alu.BSrcMux.sel>`
    rather than the original input data.
    """

    #: When asserted, latch the :attr:`selected <sentinel.alu.BSrcMux.sel>`
    #: input into :attr:`~sentinel.alu.BSrcMux.data` on the next clock edge.
    latch: In(1)
    #: In(BSrc): Select input.
    sel: In(BSrc)

    #: In(MemSel): Choose which slice of the input :attr:`dat_r` appears on the
    #: `~BSrcMux.data` output when :attr:`selected <sentinel.alu.BSrcMux.sel>`.
    mem_sel: In(MemSel)
    #: In(MemExtend): When :attr:`mem_sel` is less than word width, choose
    #: whether to sign or zero-extend :attr:`dat_r` when it's output onto
    #: :attr:`data`.
    mem_extend: In(MemExtend)
    #: Contents of the internal address register latched by
    #: :class:`~sentinel.ucodefields.LatchAdr`. Used for deciding how to
    #: align :attr:`dat_r`.
    data_adr: In(32)

    #: Input source. Register from the
    #: :class:`register file <sentinel.datapath.RegFile>`
    #: whose value is currently on the read port (e.g. the read address was
    #: supplied on the previous clock cycle).
    gp: In(32)
    #: Input source. :attr:`Decoded immediate <sentinel.decoder.Decode.imm>`
    #: from current instruction.
    imm: In(32)
    #: Input source. Current contents of the
    #: :class:`Program Counter <sentinel.datapath.ProgramCounter>`.
    pc: In(30)
    #: Input source. Current contents of the *unregistered* ``DAT_I``
    #: in :attr:`Top's Wishbone Bus <sentinel.top.Top.bus>`. Only valid when
    #: qualified by :attr:`~CondTest.MEM_VALID`.
    #:
    #: As an input, ``DAT_I`` is always 32-bit aligned. The mux contains
    #: :class:`internal alignment circuitry <sentinel.align.ReadDataAlign>`
    #: when a read of 8 or 16-bits on a less-than-32-bit alignment is
    #: requested. When :attr:`selected <sentinel.alu.BSrcMux.sel>`, the mux
    #: will latched this modified/aligned data into :attr:`~BSrcMux.data`.
    dat_r: In(32)
    #: Input source. :attr:`Decoded src_a <sentinel.decoder.Decode.src_a>`
    #: from the current instruction, which for CSR instructions is reused
    #: for specifying 5-bit CSR immediates.
    csr_imm: In(5)
    #: Input source. Register from the
    #: :class:`CSR file <sentinel.datapath.CSRFile>`
    #: whose value is currently on the read port (e.g. the read address was
    #: supplied on the previous clock cycle).
    csr: In(32)
    #: In(MCause): Input source. Current ``MCAUSE`` as determined by
    #: :class:`~sentinel.exception.ExceptionRouter`.
    mcause: In(MCause)
    #: The output. When :attr:`~sentinel.alu.BSrcMux.latch` is asserted, the
    #: data input selected by :attr:`~sentinel.alu.BSrcMux.sel` will appear
    #: here on the next clock cycle.
    data: Out(32)

    def __init__(self):
        self.rdata_align = ReadDataAlign()
        super().__init__()

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


class ALU(Component):
    """Basic Arithmetic Logic Unit.

    The ALU Performs "A OP B", where "OP" is chosen by :attr:`ctrl`. More
    operations can be synthesized from the ones directly supported by
    :class:`sentinel.ucodefields.OpType` by using :attr:`ctrl` modifiers.

    Parameters
    ----------
    width: int
        Width in bits of the ALU inputs and output.

    Attributes
    ----------
    a: In(width)
        ALU A input.
    b: In(width)
        ALU B input.
    o: Out(width)
        ALU output. Valid 1 clock cycle after inputs.
    ctrl: In(:attr:`~sentinel.alu.ALU.ControlSignature`)
        Choose the ALU op to perform this cycle, possibly modifying the input
        or output. Also check if the ALU op on the previous cycle was ``0``.
    """

    #: Signature: ALU microcode signals and useful state.
    #:
    #: The signature is of the form
    #:
    #: .. code-block::
    #:
    #:    Signature({
    #:        "op": Out(OpType),
    #:        "imod": Out(ALUIMod),
    #:        "omod": Out(ALUOMod),
    #:        "zero": In(1)
    #:    })
    #:
    #: where
    #:
    #: .. py:attribute:: op
    #:    :type: Out(~sentinel.ucodefields.OpType)
    #:
    #:    ALU operation to perform this cycle.
    #:
    #: .. py:attribute:: imod
    #:    :type: Out(~sentinel.ucodefields.ALUIMod)
    #:
    #:    Modify the inputs :attr:`a` and :attr:`b` before doing ALU
    #:    operation.
    #:
    #: .. py:attribute:: omod
    #:    :type: Out(~sentinel.ucodefields.ALUOMod)
    #:
    #:    Modify the output after doing ALU operation, but before latching
    #:    the ALU output into :attr:`o` (for next cycle).
    #:
    #: .. py:attribute:: zero
    #:    :type: In(1)
    #:
    #:    Set if  the current :attr:`output <o>` (i.e. the result of the ALU
    #:    operation done *last* cycle) is ``0``.
    ControlSignature = Signature({
        "op": Out(OpType),
        "imod": Out(ALUIMod),
        "omod": Out(ALUOMod),
        "zero": In(1)
    })

    class _Unit(Elaboratable):
        """Wrapper class for implementing basic arithmetic/logic ops."""

        def __init__(self, width, op):
            self.a = Signal(width)
            self.b = Signal(width)
            self.o = Signal(width)
            self.op = op

        def elaborate(self, platform):
            m = Module()
            m.d.comb += self.o.eq(self.op(self.a, self.b))
            return m

    # Assumes: op is held steady for duration of op.
    def __init__(self, width: int):
        self.width = width
        super().__init__(Signature({
            "a": Out(self.width),
            "b": Out(self.width),
            "o": In(self.width),
            "ctrl": Out(ALU.ControlSignature),
        }).flip())

        ###

        self.o_mux = Signal(width)
        self.add = ALU._Unit(width, lambda a, b: a + b)
        self.sub = ALU._Unit(width + 1, lambda a, b: a - b)  # width + 1 for borrow bit.  # noqa: E501
        self.and_ = ALU._Unit(width, lambda a, b: a & b)
        self.or_ = ALU._Unit(width, lambda a, b: a | b)
        self.xor = ALU._Unit(width, lambda a, b: a ^ b)
        self.sll = ALU._Unit(width, lambda a, _: a << 1)
        self.srl = ALU._Unit(width, lambda a, _: a >> 1)
        self.sar = ALU._Unit(width, lambda a, _: a.as_signed() >> 1)

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
