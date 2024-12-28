"""Instruction View classes.

This file is used to avoid circular import problems I had when using it
directly in :mod:`sentinel.decode` (IIRC).
"""

from amaranth import Cat, Value, C, unsigned
from amaranth.lib import enum

from .csr import Quadrant, AccessMode


class Insn:
    """View of all immediately-apparent information in a RISC-V instruction.

    "Immediately-apparent" means "I can get this info with
    :ref:`concatenation, slices and replicates <amaranth:lang-ioops>`. This
    class is morally equivalent to a :class:`~amaranth.lib.data.View` for the
    32-bit :ref:`Signal <amaranth:lang-signals>` representing a RISC-V
    instruction. However, it does not inherit from
    :class:`~amaranth.lib.data.View` because
    :class:`Layouts <amaranth.lib.data.Layout>` are not designed to retrieve
    non-contiguous bits.

    Parameters
    ----------
    value: ~amaranth.hdl.Value
        Raw value to interpret as a RISC-V instruction.

    Attributes
    ----------
    raw: ~amaranth.hdl.Value
        The raw instruction value.
    imm: Imm
        A moral equivalent to a :class:`~amaranth.lib.data.View` for extracting
        RISC-V immediate values from :attr:`raw`.
    csr: CSR
        A moral equivalent to a :class:`~amaranth.lib.data.View` for extracting
        CSR information from :attr:`raw`.
    """

    #: Bit pattern for ``ECALL`` instruction.
    ECALL = 0b00000000000000000000000001110011
    #: Bit pattern for ``EBREAK`` instruction.
    EBREAK = 0b00000000000100000000000001110011
    #: Bit pattern for ``MRET`` instruction.
    MRET = 0b00110000001000000000000001110011
    #: Bit pattern for ``WFI`` instruction.
    WFI = 0b00010000010100000000000001110011

    class Imm:
        """Extract a RISC-V immediate value from an instruction.

        This class does *not* (and *can not*) check whether the given
        instruction contains an immediate field or whether the requested
        immediate type is correct. The user is expected to known which
        immediate type to use using external logic. See
        :class:`~sentinel.decode.ImmediateGenerator` for an example.

        Parameters
        ----------
        value: ~amaranth.hdl.Value
            Raw value to interpret as a RISC-V immediate.

        Attributes
        ----------
        raw: ~amaranth.hdl.Value
            The raw instruction value.
        sign: ~amaranth.hdl.Value
        """

        def __init__(self, value):
            self.raw = value
            self.sign = self.raw[-1]

        @property
        def I(self):  # noqa: E743
            """~amaranth.hdl.Value: Extract an ``I``-type immediate."""
            return Cat(self.raw[20:31], Value.replicate(self.sign, 21))

        @property
        def S(self):
            """~amaranth.hdl.Value: Extract an ``S``-type immediate."""
            return Cat(self.raw[7], self.raw[8:12], self.raw[25:31],
                       Value.replicate(self.sign, 21))

        @property
        def B(self):
            """~amaranth.hdl.Value: Extract a ``B``-type immediate."""
            return Cat(C(0), self.raw[8:12], self.raw[25:31], self.raw[7],
                       Value.replicate(self.sign, 20))

        @property
        def U(self):
            """~amaranth.hdl.Value: Extract a ``U``-type immediate."""
            return Cat(C(0, 12), self.raw[12:20], self.raw[20:31], self.sign)

        @property
        def J(self):
            """~amaranth.hdl.Value: Extract a ``J``-type immediate."""
            return Cat(C(0), self.raw[21:25], self.raw[25:31], self.raw[20],
                       self.raw[12:20], Value.replicate(self.sign, 12))

    class CSR:
        """Extract a RISC-V CSR info from an instruction.

        This class does *not* (and *can not*) check whether the given
        instruction is a CSR instruction. The user is expected to know a priori
        that the current instruction is a CSR instruction for results from
        this class to be valid. See :class:`~sentinel.decode.ExceptionControl`
        for an example.

        .. todo::

            Constants aren't meaningfully used that much. Get rid of them
            and convert uses into properties?

        Parameters
        ----------
        value: ~amaranth.hdl.Value
            Raw value from which to retrieve CSR info.

        Attributes
        ----------
        raw: ~amaranth.hdl.Value
            The top 12 bits of the raw instruction value.
        """

        #: Read-Write CSR instruction.
        RW = 0b001
        #: Read-Set CSR instruction.
        RS = 0b010
        #: Read-Clear CSR instruction.
        RC = 0b011
        #: Read-Write Immediate CSR instruction.
        RWI = 0b101
        #: Read-Set Immediate CSR instruction.
        RSI = 0b110
        #: Read-Clear Immediate CSR instruction.
        RCI = 0b111

        def __init__(self, value):
            self.raw = value[20:]

        @property
        def addr(self):
            """~amaranth.hdl.Value: Return the CSR address."""
            return self.raw

        @property
        def quadrant(self):
            """~amaranth.lib.enum.EnumView: Return the CSR privilege level.

            :attr:`raw` is interpreted as a :class:`~sentinel.csr.Quadrant`.
            """
            return enum.EnumView(Quadrant, self.raw[8:10])

        @property
        def access(self):
            """~amaranth.lib.enum.EnumView: Return whether the CSR is read-only.

            :attr:`raw` is interpreted as an
            :class:`~sentinel.csr.AccessMode`.
            """  # noqa: E501
            return enum.EnumView(AccessMode, self.raw[10:])

    def __init__(self, value):
        self.raw = value
        self.imm = Insn.Imm(self.raw)
        self.csr = Insn.CSR(self.raw)

    @property
    def opcode(self):
        """OpcodeType: Return the major opcode."""
        return OpcodeType(self.raw[2:7])

    @property
    def rd(self):
        """~amaranth.hdl.Value: Return the destination register bits."""
        return self.raw[7:12]

    @property
    def funct3(self):
        """~amaranth.hdl.Value: Return the minor opcode/``funct3`` bits."""
        return self.raw[12:15]

    @property
    def rs1(self):
        """~amaranth.hdl.Value: Return the first source register bits."""
        return self.raw[15:20]

    @property
    def rs2(self):
        """~amaranth.hdl.Value: Return the second source register bits."""
        return self.raw[20:25]

    @property
    def funct7(self):
        """~amaranth.hdl.Value: Return the ``funct7`` bits."""
        return self.raw[25:]

    @property
    def funct12(self):
        """~amaranth.hdl.Value: Return the ``funct12`` bits."""
        return self.raw[20:]

    @property
    def sign(self):
        """~amaranth.hdl.Value: Return the sign bit."""
        return self.raw[-1]


class OpcodeType(enum.Enum, shape=unsigned(5)):
    """Enumeration of RV32I Major Opcode bit patterns."""

    #: Immediate Op instructions.
    OP_IMM = 0b00100
    #: Load Unsigned Immediate.
    LUI = 0b01101
    #: Add Upper Immediate To Program Counter.
    AUIPC = 0b00101
    #: Register Op instructions.
    OP = 0b01100
    #: Jump And Link.
    JAL = 0b11011
    #: Jump And Link Register.
    JALR = 0b11001
    #: Branch instructions.
    BRANCH = 0b11000
    #: Load instructions.
    LOAD = 0b00000
    #: Store instructions.
    STORE = 0b01000
    #: Unused Major Opcode for future custom instructions.
    CUSTOM_0 = 0b00010
    #: Miscellaneous instructions.
    MISC_MEM = 0b00011
    #: System instructions.
    SYSTEM = 0b11100
