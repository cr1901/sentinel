"""Exception control classes and Components."""

from amaranth import Signal, Module, unsigned
from amaranth.lib.data import Struct
from amaranth.lib.wiring import Component, Signature, Out, In

from .csr import MCause, MStatus, MIP, MIE
from .ucodefields import MemSel, ExceptCtl


#: Avoid circular imports.
class DecodeException(Struct):
    valid: unsigned(1)
    e_type: MCause.Cause


class ExceptionRouter(Component):
    """Detect exceptions throughout the Sentinel core.

    RISC-V defines a priority order for exceptions if multiple exceptions
    occur at the same time. Because Sentinel is microcoded and instructions
    take multiple cycles, priority checking is deferred to microcode routines.
    Specifcally, :class:`ExceptionRouter` only checks for exceptions when
    qualified by values of :class:`~sentinel.ucodefields.ExceptCtl` other than
    :attr:`~sentinel.ucodefields.ExceptCtl.NONE`; it can only check for
    one type of exception each clock cycle.

    When :class:`~sentinel.ucodefields.ExceptCtl` is not
    :attr:`~sentinel.ucodefields.ExceptCtl.NONE`, :class:`ExceptionRouter`
    will output whether the queried exception occurred and latch which
    exception occurred at the next active edge. The exception info latch
    matches the layout of the ``MCAUSE`` register. The :attr:`mcause` port
    is physically distinct from the ``MCAUSE`` register, and so microcode
    should save the latch value to the actual ``MCAUSE`` register as part of
    exception handling.

    While the :class:`~sentinel.csr.MCause`
    :class:`~amaranth.lib.data.Struct` knows about all currently-defined RISC-V
    M-Mode exception types, :class:`ExceptionRouter` can only trigger a subset
    of exceptions:

    * Anything from :attr:`DecodeException.e_type`.
    * :attr:`~sentinel.csr.MCause.Cause.MEXT_INT`
    * :attr:`~sentinel.csr.MCause.Cause.INSN_MISALIGNED`
    * :attr:`~sentinel.csr.MCause.Cause.LOAD_MISALIGNED`
    * :attr:`~sentinel.csr.MCause.Cause.STORE_MISALIGNED`

    """

    ControlSignature = Signature({
        "mem_sel": Out(MemSel),
        "except_ctl": Out(ExceptCtl),
        "exception": In(1)
    })

    # FIXME: Ugh, want to hide the ugly auto-extracted Signature from docs,
    # but can't seem to without disabling all annotations
    # (autodoc_typehints = "none"). Is autodoc_typehints = "description"
    # supposed to help?
    #: In(Signature): Exception router sources.
    #:
    #: The signature is of the form
    #:
    #: .. code-block::
    #:
    #:     Signature({
    #:         "alu_lo": Out(2),
    #:         "csr": Out(Signature({
    #:             "mstatus": Out(:class:MStatus),
    #:             "mip": Out(MIP),
    #:             "mie": Out(MIE)
    #:         })),
    #:         "ctrl": Out(Signature({
    #:             "mem_sel": Out(MemSel),
    #:             "except_ctl": Out(ExceptCtl)
    #:         })),
    #:         "decode": Out(DecodeException)
    #:     })
    #:
    #: where
    #:
    #: .. py:attribute:: alu_lo
    #:    :type: Out(2)
    #:
    #:    The low 2 bits of the :attr:`ALU output <sentinel.alu.ALU.o>`.
    #:
    #: .. py:attribute:: csr
    #:    :type: Out(Signature)
    #:
    #:    Snoop CSR registers containing exception state. See
    #:    :class:`~sentinel.csr.MStatus`, :class:`~sentinel.csr.MIP`, and
    #:    :class:`~sentinel.csr.MIE`.
    #:
    #: .. py:attribute:: ctrl
    #:    :type: Out(Signature)
    #:
    #:    Snoop microcode signals relevant to exceptions. See
    #:    :class:`~sentinel.ucodefields.MemSel` and
    #:    :class:`~sentinel.ucodefields.ExceptCtl`.
    #:
    #: .. py:attribute:: decode
    #:    :type: Out(~sentinel.decode.DecodeException)
    #:
    #:    Snoop decoder exception state.
    src: In(Signature({
        "alu_lo": Out(2),
        "csr": Out(Signature({
            "mstatus": Out(MStatus),
            "mip": Out(MIP),
            "mie": Out(MIE)
        })),
        "ctrl": Out(ControlSignature),
        "decode": Out(DecodeException)
    }))
    #: Out(Signature): Information on current exception.
    #:
    #: The signature is of the form
    #:
    #: .. code-block::
    #:
    #:     Signature({
    #:         "exception": Out(1),
    #:         "mcause": Out(MCause)
    #:     })
    #:
    #: where
    #:
    #: .. py:attribute:: exception
    #:    :type: Out(1)
    #:
    #:    If asserted, an exception occurred last cycle, and :attr:`mcause`
    #:    is valid.
    #:
    #: .. py:attribute:: mcause
    #:    :type: Out(~sentinel.csr.MCause)
    #:
    #:    Qualified by :attr:`exception`. Indicates the type of exception, if
    #:    any, which was detected last cycle where
    #:    :class:`~sentinel.ucodefields.ExceptCtl` was not
    #:    :attr:`~sentinel.ucodefields.ExceptCtl.NONE`. Must be saved by
    #:    microcode if the value is needed, as this is *not* meant to hold the
    #:    ``MCAUSE`` register.
    out: Out(Signature({
         "exception": Out(1),
         "mcause": Out(MCause)
    }))

    def elaborate(self, platform):  # noqa: D102
        m = Module()

        exception = Signal(1)
        mcause_latch = Signal(MCause)

        m.d.comb += [
            self.src.ctrl.exception.eq(exception),
            self.out.exception.eq(exception),
            self.out.mcause.eq(mcause_latch)
        ]

        with m.If(self.src.ctrl.except_ctl == ExceptCtl.LATCH_DECODER):
            with m.If(self.src.decode.valid):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(self.src.decode.e_type)

            with m.If(self.src.csr.mstatus.mie & self.src.csr.mip.meip &
                      self.src.csr.mie.meie):
                m.d.comb += exception.eq(1)
                m.d.sync += [
                    mcause_latch.cause.eq(11),
                    mcause_latch.interrupt.eq(1)
                ]
        with m.Elif(self.src.ctrl.except_ctl == ExceptCtl.LATCH_STORE_ADR):
            with m.If((((self.src.ctrl.mem_sel == MemSel.HWORD) &
                        self.src.alu_lo[0] == 1)) |
                      ((self.src.ctrl.mem_sel == MemSel.WORD) &
                      ((self.src.alu_lo[0] == 1) |
                       (self.src.alu_lo[1] == 1)))):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(
                    MCause.Cause.STORE_MISALIGNED)
        with m.Elif(self.src.ctrl.except_ctl == ExceptCtl.LATCH_LOAD_ADR):
            with m.If((((self.src.ctrl.mem_sel == MemSel.HWORD) &
                        self.src.alu_lo[0] == 1)) |
                      ((self.src.ctrl.mem_sel == MemSel.WORD) &
                      ((self.src.alu_lo[0] == 1) |
                       (self.src.alu_lo[1] == 1)))):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(MCause.Cause.LOAD_MISALIGNED)
        with m.Elif(self.src.ctrl.except_ctl == ExceptCtl.LATCH_JAL):
            with m.If(self.src.alu_lo[1] == 1):
                m.d.comb += exception.eq(1)
                m.d.sync += mcause_latch.cause.eq(MCause.Cause.INSN_MISALIGNED)

        return m
