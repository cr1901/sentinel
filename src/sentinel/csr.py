from amaranth import unsigned
from amaranth.lib.enum import Enum
from amaranth.lib.data import Struct

# Only the registers that are _not_ read-only-0 or illegal are implemented
# for Sentinel. And even then, only the used fields are explicitly laid out.


class MStatus(Struct):
    _padding0: unsigned(3)
    mie: unsigned(1)
    _padding1: unsigned(3)
    mpie: unsigned(1)
    _padding2: unsigned(3)
    mpp: unsigned(2)
    _padding3: unsigned(9)


class MTVec(Struct):
    class Mode(Enum, shape=unsigned(2)):
        DIRECT = 0
        VECTORED = 1  # Not implemented

    mode: Mode
    base: unsigned(30)


class MIP(Struct):
    _padding0: unsigned(3)
    msip: unsigned(1)  # Not implemented
    _padding1: unsigned(3)
    mtip: unsigned(1)  # Not implemented
    _padding2: unsigned(3)
    meip: unsigned(1)
    _padding3: unsigned(20)


class MIE(Struct):
    _padding0: unsigned(3)
    msip: unsigned(1)  # Not implemented
    _padding1: unsigned(3)
    mtip: unsigned(1)  # Not implemented
    _padding2: unsigned(3)
    meip: unsigned(1)
    _padding3: unsigned(20)


class MCause(Struct):
    class Cause(Enum, shape=unsigned(31)):
        INSN_MISALIGNED = 0
        INSN_FAULT = 1
        ILLEGAL_INSN = 2
        BREAKPOINT = 3
        LOAD_MISALIGNED = 4
        LOAD_FAULT = 5
        STORE_MISALIGNED = 6
        STORE_FAULT = 7
        ECALL_UMODE = 8
        ECALL_SMODE = 9
        ECALL_MMODE = 11
        INSN_PAGE_FAULT = 12
        LOAD_PAGE_FAULT = 13
        STORE_PAGE_FAULT = 15
        MSOFT_INT = 3
        MTIMER_INT = 7
        MEXT_INT = 11

    cause: Cause
    interrupt: unsigned(1)
