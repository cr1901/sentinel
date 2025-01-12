"""Exception control classes and Components."""

from amaranth import Signal, Module, unsigned
from amaranth.lib.data import Struct
from amaranth.lib.wiring import Component, Signature, Out, In

from .csr import MCause, MStatus, MIP, MIE
from .ucodefields import MemSel, ExceptCtl


#: Avoid circular imports.
class DecodeException(Struct):
    """Exception info from :class:`~sentinel.decode.Decode`.

    This :class:`~amaranth.lib.data.Struct` has a very similar purpose to
    :attr:`ExceptionRouter.out`. In fact, the
    :class:`~amaranth:amaranth.lib.data.Layout` is the same as the
    :class:`~amaranth:amaranth.lib.wiring.Signature` of
    :attr:`~ExceptionRouter.out`! The main differences compared to
    :attr:`~ExceptionRouter.out` is that:

    * :class:`~sentinel.decode.Decode` can only physically trigger a subset of
      exceptions that :attr:`~ExceptionRouter.out` can:

        * :attr:`~sentinel.csr.MCause.Cause.ILLEGAL_INSN`
        * :attr:`~sentinel.csr.MCause.Cause.ECALL_MMODE`
        * :attr:`~sentinel.csr.MCause.Cause.BREAKPOINT`

    * Both :attr:`valid` and :attr:`e_type` are synchronous to the ``sync``
      :ref:`clock domain <amaranth:lang-domains>` (which is why, AFAIR,
      :class:`DecodeException` can be a :class:`~amaranth.lib.data.Struct` in
      the first place). In :attr:`~ExceptionRouter.out`,
      only :attr:`~ExceptionRouter.mcause` is synchronous to ``sync``;
      :attr:`~ExceptionRouter.exception` is combinationally driven.

    :class:`DecodeException` physically belongs to
    :class:`~sentinel.decode.Decode`, but is placed in the
    :mod:`~sentinel.exception` module to solve circular import issues.

    .. todo::

        Eventually :class:`DecodeException` should be defined as a nested
        class under :class:`~sentinel.decode.Decode`, similar to e.g.
        :class:`ALU.RoutingSignature <sentinel.alu.ALU.RoutingSignature>`.
    """

    #: If asserted, :class:`~sentinel.decode.Decode` detected an exception
    #: *last* cycle.
    valid: unsigned(1)
    #: :class:`MCause.Cause <sentinel.csr.MCause.Cause>`: Qualified by
    #: :attr:`valid`. Indicates the type of exception, if any, that
    #: :class:`~sentinel.decode.Decode` detected last cycle.
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
    will output whether the queried exception type occurred immediately. It
    will latch which *specific* exception occurred at the next active edge.
    The exception info latch matches the layout of the ``MCAUSE`` register.
    The :attr:`mcause` port is physically distinct from the ``MCAUSE``
    register, and so microcode should save the latch value to the actual
    ``MCAUSE`` register as part of exception handling.

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

    #: Signature: Exception Router microcode signals and useful state.
    #:
    #: The signature is of the form
    #:
    #: .. code-block::
    #:
    #:    Signature({
    #:        "mem_sel": Out(MemSel),
    #:        "except_ctl": Out(ExceptCtl),
    #:        "exception": In(1)
    #:    })
    #:
    #: where
    #:
    #: .. py:attribute:: op
    #:    :type: Out(~sentinel.ucodefields.MemSel)
    #:
    #:    Memory operation in progress this cycle.
    #:
    #: .. py:attribute:: except_ctl
    #:    :type: Out(~sentinel.ucodefields.ExceptCtl)
    #:
    #:    Choose which action :class:`ExceptionRouter` performs this cycle,
    #:    such as checking for a specific exception, or entering/leaving
    #:    the exception handler.
    #:
    #: .. py:attribute:: exception
    #:    :type: In(1)
    #:    :no-index:
    #:
    #:    Sent back to :class:`~sentinel.control.Control`; if asserted, an
    #:    exception condition was detected this cycle. The
    #:    :attr:`cause <mcause>` will be available on the next active edge.
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
    #:    :type: Out(DecodeException)
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
    #:    If asserted, an exception occurred *this* cycle, and :attr:`mcause`
    #:    will be valid *next* cycle.
    #:
    #: .. py:attribute:: mcause
    #:    :type: Out(~sentinel.csr.MCause)
    #:
    #:    Qualified by :attr:`exception` on the previous cycle. Indicates the
    #:    type of exception, if any, which was detected last cycle where
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
