"""Useful enums and structs for dealing with RISC-V CSRs.

Attributes should match the addresses, fields, and offsets defined in the
`RISC-V Privileged Specification <https://riscv.org/specifications/ratified/>`_.
Therefore, I've only made basic remarks on registers fields and values
in these docs. Consult the spec for detailed descriptions.

Only the registers that are *not* read-only-0 or illegal are implemented
for Sentinel. And even then, only the used fields are explicitly laid out.
Most Unused :mod:`enum <amaranth:amaranth.lib.enum>` fields are defined, while
unused :class:`Structs <amaranth:amaranth.lib.data.Struct>` fields are **not**
implemented. See the :ref:`CSRs <csrs>` section for an idea of what is
implemented.
"""  # noqa: E501, RUF100

from amaranth import unsigned
from amaranth.lib.enum import Enum, IntEnum
from amaranth.lib.data import Struct


# Implemented in the order they are presented in Privileged Spec.
class MachineAddr(IntEnum):
    """Enumeration of all defined RISC-V Machine-Mode CSR addresses.

    .. note::
        Register names are UPPER_CASE versions of those defined in the spec.
        Please consult the spec for detailed information, because I don't feel
        like typing all the descriptions out :).
    """

    MVENDORID = 0xF11
    MARCHID = 0xF12
    MIMPID = 0xF13
    MHARTID = 0xF14
    MCONFIGPTR = 0xF15
    MSTATUS = 0x300
    MISA = 0x301
    MEDELEG = 0x302
    MIDELEG = 0x303
    MIE = 0x304
    MTVEC = 0x305
    MCOUNTEREN = 0x306
    MSTATUSH = 0x310
    MSCRATCH = 0x340
    MEPC = 0x341
    MCAUSE = 0x342
    MTVAL = 0x343
    MIP = 0x344
    MTINST = 0x34A
    MTVAL2 = 0x34B
    MENVCFG = 0x30A
    MENVCFGH = 0x31A
    MSECCFG = 0x747
    MSECCFGH = 0x757
    PMPCFG0 = 0x3A0
    PMPCFG1 = 0x3A1
    PMPCFG2 = 0x3A2
    PMPCFG3 = 0x3A3
    PMPCFG4 = 0x3A4
    PMPCFG5 = 0x3A5
    PMPCFG6 = 0x3A6
    PMPCFG7 = 0x3A7
    PMPCFG8 = 0x3A8
    PMPCFG9 = 0x3A9
    PMPCFG10 = 0x3AA
    PMPCFG11 = 0x3AB
    PMPCFG12 = 0x3AC
    PMPCFG13 = 0x3AD
    PMPCFG14 = 0x3AE
    PMPCFG15 = 0x3AF
    PMPADDR0 = 0x3B0
    PMPADDR1 = 0x3B1
    PMPADDR2 = 0x3B2
    PMPADDR3 = 0x3B3
    PMPADDR4 = 0x3B4
    PMPADDR5 = 0x3B5
    PMPADDR6 = 0x3B6
    PMPADDR7 = 0x3B7
    PMPADDR8 = 0x3B8
    PMPADDR9 = 0x3B9
    PMPADDR10 = 0x3BA
    PMPADDR11 = 0x3BB
    PMPADDR12 = 0x3BC
    PMPADDR13 = 0x3BD
    PMPADDR14 = 0x3BE
    PMPADDR15 = 0x3BF
    PMPADDR16 = 0x3C0
    PMPADDR17 = 0x3C1
    PMPADDR18 = 0x3C2
    PMPADDR19 = 0x3C3
    PMPADDR20 = 0x3C4
    PMPADDR21 = 0x3C5
    PMPADDR22 = 0x3C6
    PMPADDR23 = 0x3C7
    PMPADDR24 = 0x3C8
    PMPADDR25 = 0x3C9
    PMPADDR26 = 0x3CA
    PMPADDR27 = 0x3CB
    PMPADDR28 = 0x3CC
    PMPADDR29 = 0x3CD
    PMPADDR30 = 0x3CE
    PMPADDR31 = 0x3CF
    PMPADDR32 = 0x3D0
    PMPADDR33 = 0x3D1
    PMPADDR34 = 0x3D2
    PMPADDR35 = 0x3D3
    PMPADDR36 = 0x3D4
    PMPADDR37 = 0x3D5
    PMPADDR38 = 0x3D6
    PMPADDR39 = 0x3D7
    PMPADDR40 = 0x3D8
    PMPADDR41 = 0x3D9
    PMPADDR42 = 0x3DA
    PMPADDR43 = 0x3DB
    PMPADDR44 = 0x3DC
    PMPADDR45 = 0x3DD
    PMPADDR46 = 0x3DE
    PMPADDR47 = 0x3DF
    PMPADDR48 = 0x3E0
    PMPADDR49 = 0x3E1
    PMPADDR50 = 0x3E2
    PMPADDR51 = 0x3E3
    PMPADDR52 = 0x3E4
    PMPADDR53 = 0x3E5
    PMPADDR54 = 0x3E6
    PMPADDR55 = 0x3E7
    PMPADDR56 = 0x3E8
    PMPADDR57 = 0x3E9
    PMPADDR58 = 0x3EA
    PMPADDR59 = 0x3EB
    PMPADDR60 = 0x3EC
    PMPADDR61 = 0x3ED
    PMPADDR62 = 0x3EE
    PMPADDR63 = 0x3EF
    MCYCLE = 0xB00
    MINSTRET = 0xB02
    MHPMCOUNTER3 = 0xB03
    MHPMCOUNTER4 = 0xB04
    MHPMCOUNTER5 = 0xB05
    MHPMCOUNTER6 = 0xB06
    MHPMCOUNTER7 = 0xB07
    MHPMCOUNTER8 = 0xB08
    MHPMCOUNTER9 = 0xB09
    MHPMCOUNTER10 = 0xB0A
    MHPMCOUNTER11 = 0xB0B
    MHPMCOUNTER12 = 0xB0C
    MHPMCOUNTER13 = 0xB0D
    MHPMCOUNTER14 = 0xB0E
    MHPMCOUNTER15 = 0xB0F
    MHPMCOUNTER16 = 0xB10
    MHPMCOUNTER17 = 0xB11
    MHPMCOUNTER18 = 0xB12
    MHPMCOUNTER19 = 0xB13
    MHPMCOUNTER20 = 0xB14
    MHPMCOUNTER21 = 0xB15
    MHPMCOUNTER22 = 0xB16
    MHPMCOUNTER23 = 0xB17
    MHPMCOUNTER24 = 0xB18
    MHPMCOUNTER25 = 0xB19
    MHPMCOUNTER26 = 0xB1A
    MHPMCOUNTER27 = 0xB1B
    MHPMCOUNTER28 = 0xB1C
    MHPMCOUNTER29 = 0xB1D
    MHPMCOUNTER30 = 0xB1E
    MHPMCOUNTER31 = 0xB1F
    MCYCLEH = 0xB80
    MINSTRETH = 0xB82
    MHPMCOUNTER3H = 0xB83
    MHPMCOUNTER4H = 0xB84
    MHPMCOUNTER5H = 0xB85
    MHPMCOUNTER6H = 0xB86
    MHPMCOUNTER7H = 0xB87
    MHPMCOUNTER8H = 0xB88
    MHPMCOUNTER9H = 0xB89
    MHPMCOUNTER10H = 0xB8A
    MHPMCOUNTER11H = 0xB8B
    MHPMCOUNTER12H = 0xB8C
    MHPMCOUNTER13H = 0xB8D
    MHPMCOUNTER14H = 0xB8E
    MHPMCOUNTER15H = 0xB8F
    MHPMCOUNTER16H = 0xB90
    MHPMCOUNTER17H = 0xB91
    MHPMCOUNTER18H = 0xB92
    MHPMCOUNTER19H = 0xB93
    MHPMCOUNTER20H = 0xB94
    MHPMCOUNTER21H = 0xB95
    MHPMCOUNTER22H = 0xB96
    MHPMCOUNTER23H = 0xB97
    MHPMCOUNTER24H = 0xB98
    MHPMCOUNTER25H = 0xB99
    MHPMCOUNTER26H = 0xB9A
    MHPMCOUNTER27H = 0xB9B
    MHPMCOUNTER28H = 0xB9C
    MHPMCOUNTER29H = 0xB9D
    MHPMCOUNTER30H = 0xB9E
    MHPMCOUNTER31H = 0xB9F
    MCOUNTINHIBIT = 0x320
    MHPMEVENT3 = 0x323
    MHPMEVENT4 = 0x324
    MHPMEVENT5 = 0x325
    MHPMEVENT6 = 0x326
    MHPMEVENT7 = 0x327
    MHPMEVENT8 = 0x328
    MHPMEVENT9 = 0x329
    MHPMEVENT10 = 0x32A
    MHPMEVENT11 = 0x32B
    MHPMEVENT12 = 0x32C
    MHPMEVENT13 = 0x32D
    MHPMEVENT14 = 0x32E
    MHPMEVENT15 = 0x32F
    MHPMEVENT16 = 0x330
    MHPMEVENT17 = 0x331
    MHPMEVENT18 = 0x332
    MHPMEVENT19 = 0x333
    MHPMEVENT20 = 0x334
    MHPMEVENT21 = 0x335
    MHPMEVENT22 = 0x336
    MHPMEVENT23 = 0x337
    MHPMEVENT24 = 0x338
    MHPMEVENT25 = 0x339
    MHPMEVENT26 = 0x33A
    MHPMEVENT27 = 0x33B
    MHPMEVENT28 = 0x33C
    MHPMEVENT29 = 0x33D
    MHPMEVENT30 = 0x33E
    MHPMEVENT31 = 0x33F
    TSELECT = 0x7A0
    TDATA1 = 0x7A1
    TDATA2 = 0x7A2
    TDATA3 = 0x7A3
    MCONTEXT = 0x7A8
    DCSR = 0x7B0
    DPC = 0x7B1
    DSCRATCH0 = 0x7B2
    DSCRATCH1 = 0x7B3


class AccessMode(Enum, shape=unsigned(2)):
    """The top 2 bits of CSR address space."""

    _READ_WRITE_00 = 0b00
    _READ_WRITE_01 = 0b01
    _READ_WRITE_02 = 0b10
    #: Read-only CSR addresses.
    READ_ONLY = 0b11


class Quadrant(Enum, shape=unsigned(2)):
    """Bits 8 and 9 of the CSR address space."""

    #: Unpriviled Mode CSRs.
    UNPRIVILEGED = 0b00
    #: Supervisor Mode CSRs.
    SUPERVISOR = 0b01
    #: Hypervisor Mode CSRs.
    HYPERVISOR = 0b10
    #: Machine Mode CSRs.
    MACHINE = 0b11


class MStatus(Struct):
    """Machine Status Register (``mstatus``)."""

    _padding0: unsigned(3)
    #: Machine Interrupt Enable bit.
    mie: unsigned(1)
    _padding1: unsigned(3)
    #: Machine Previous Interrupt Enable bit.
    mpie: unsigned(1)
    _padding2: unsigned(3)
    #: Machine Previous Privilege bits. Constant ``C(3, 2)`` in Sentinel,
    #: meaning Machine Mode.
    mpp: unsigned(2)
    _padding3: unsigned(19)


class MTVec(Struct):
    """Machine Trap Vector Address Register (``mtvec``)."""

    class Mode(Enum, shape=unsigned(2)):
        """Low 2 bits of ``mtvec``."""

        #: Jump to the address in :attr:`~MTVec.base`.
        DIRECT = 0
        #: On asynchronous interruept, add an offset to the address in
        #: :attr:`~MTVec.base` before jumping, dependendent on :class:`MCause`.
        #: On synchornous exception, jump to the address in
        #: :attr:`~MTVec.base`.
        VECTORED = 1  # Not implemented

    #: Set how the exception/interrupt address is calculated.
    mode: Mode
    #: Base address to jump to on exception.
    base: unsigned(30)


class MIP(Struct):
    """Machine Interrupt Pending Register (``mip``)."""

    _padding0: unsigned(3)
    #: Machine Sofware Interrupt Pending bit. Not implemented.
    msip: unsigned(1)
    _padding1: unsigned(3)
    #: Machine Timer Interrupt Pending bit. Not implemented.
    mtip: unsigned(1)
    _padding2: unsigned(3)
    #: Machine External Interrupt Pending bit.
    meip: unsigned(1)
    _padding3: unsigned(20)


class MIE(Struct):
    """Machine Interrupt-Enable Register (``mie``)."""

    _padding0: unsigned(3)
    #: Machine Sofware Interrupt Enable bit. Not implemented.
    msie: unsigned(1)
    _padding1: unsigned(3)
    #: Machine Timer Interrupt Enable bit. Not implemented.
    mtie: unsigned(1)
    _padding2: unsigned(3)
    #: Machine External Interrupt Enable bit.
    meie: unsigned(1)
    _padding3: unsigned(20)


class MCause(Struct):
    """Machine Trap Cause Register (``mtcause``)."""

    class Cause(Enum, shape=unsigned(31)):
        """Cause of the current exception.

        .. note::
            For easy searching, the docstring for each enum variant (minus
            the period) should match a string in the
            `privileged spec <https://riscv.org/specifications/ratified/>`_.
        """

        #: Instruction address misaligned.
        INSN_MISALIGNED = 0
        #: Instruction access fault.
        INSN_FAULT = 1
        #: Illegal instruction.
        ILLEGAL_INSN = 2
        #: Breakpoint.
        BREAKPOINT = 3
        #: Load address misaligned.
        LOAD_MISALIGNED = 4
        #: Load access fault.
        LOAD_FAULT = 5
        #: Store/AMO address misaligned.
        STORE_MISALIGNED = 6
        #: Store/AMO access fault.
        STORE_FAULT = 7
        #: Environment call from U-mode.
        ECALL_UMODE = 8
        #: Environment call from S-mode.
        ECALL_SMODE = 9
        #: Environment call from M-mode.
        ECALL_MMODE = 11
        #: Instruction page fault.
        INSN_PAGE_FAULT = 12
        #: Load page fault.
        LOAD_PAGE_FAULT = 13
        #: Store/AMO page fault.
        STORE_PAGE_FAULT = 15
        #: Machine software interrupt.
        MSOFT_INT = 3
        #: Machine timer interrupt.
        MTIMER_INT = 7
        #: Machine external interrupt.
        MEXT_INT = 11

    #: Cause of the current trap/exception.
    cause: Cause
    #: Set if the current trap is an asynchronous interrupt, rather than a
    #: synchronous exception. If set, the values of
    #: :attr:`~MCause.Cause.MEXT_INT` and friends are valid.
    interrupt: unsigned(1)
