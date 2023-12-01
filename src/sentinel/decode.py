from amaranth import Signal, Module, Cat, Value, C, unsigned
from amaranth.lib import enum
from amaranth.lib.data import Struct
from amaranth.lib.wiring import Component, Signature, In, Out

from .csr import MCause


class InsnImmFormat(enum.Enum):
    R = 0
    I = 1  # noqa: E741
    S = 2
    B = 3  # Accepted in place of S.
    U = 4
    J = 5  # Accepted in place of U.


class OpcodeType(enum.Enum):
    OP_IMM = 0b00100
    LUI = 0b01101
    AUIPC = 0b00101
    OP = 0b01100
    JAL = 0b11011
    JALR = 0b11001
    BRANCH = 0b11000
    LOAD = 0b00000
    STORE = 0b01000
    CUSTOM_0 = 0b00010
    MISC_MEM = 0b00011
    SYSTEM = 0b11100


class DecodeException(Struct):
    valid: unsigned(1)
    e_type: MCause.Cause


class Decode(Component):
    @property
    def signature(self):
        base = {
            "do_decode": Out(1),
            "insn": Out(32),
            "src_a_unreg": In(5),
            "src_a": In(5),
            "src_b": In(5),
            "imm": In(32),
            "dst": In(5),
            "opcode": In(OpcodeType),
            "exception": In(DecodeException),
            # Map from opcode, funct3, and funct7, and funct12 bits to a 8-bit
            # ID to index into ucode ROM. Chosen through trial and error.
            "requested_op": In(8),
            # Squash CSR encoding down to only bits that vary between
            # the 7 implemented CSRs.
            "csr_encoding": In(4)
        }

        if self.formal:
            rvfi = Signature({
                "rs1": Out(5),
                "rs2": Out(5),
                "rd": Out(5),
                "rd_valid": Out(1),
                "do_decode": Out(1),
                "funct12": Out(12),
                "funct3": Out(3),
                "insn": Out(32),
            })

            # Base part of signature is from peripheral/responder POV
            sig = Signature(base).flip()
            # But RVFI is from initiator POV, extending sig is easier to read
            # than doing In(Out(rvfi)) to cancel out flip.
            sig.members += {
                "rvfi": Out(rvfi)
            }

            return sig
        else:
            return Signature(base).flip()

    def __init__(self, *, formal=False):
        self.formal = formal
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        rd = Signal(5)
        rs1 = Signal(5)
        rs2 = Signal(5)
        funct3 = Signal(3)
        funct7 = Signal(7)
        funct12 = Signal(12)

        m.d.comb += [
            self.opcode.eq(self.insn[2:7]),
            rd.eq(self.insn[7:12]),
            funct3.eq(self.insn[12:15]),
            rs1.eq(self.insn[15:20]),
            rs2.eq(self.insn[20:25]),
            funct7.eq(self.insn[25:32]),
            funct12.eq(self.insn[20:32]),
            self.src_a_unreg.eq(rs1)
        ]

        csr_map = Signal(2)
        with m.Switch(Cat(funct12[0:8], funct12[10:12])):
            for i, v in enumerate(self.mmode_csr_quadrant_init()):
                with m.Case(i):
                    m.d.sync += csr_map.eq(v)

        forward_csr = Signal()
        csr_quadrant = Signal(2)
        csr_op = Signal.like(funct3)
        csr_ro_space = Signal()

        m.d.sync += [
            forward_csr.eq(0),
            self.exception.e_type.eq(MCause.Cause.ILLEGAL_INSN),
            self.exception.valid.eq(0),
            csr_quadrant.eq(funct12[8:10]),
            csr_op.eq(funct3),
            csr_ro_space.eq(funct12[10:12] == 0b11)
        ]

        with m.If(self.do_decode):
            m.d.sync += [
                # For now, unconditionally propogate these and rely on
                # microcode program to ignore when necessary.
                self.src_a.eq(rs1),
                self.src_b.eq(rs2),
                self.dst.eq(rd),
            ]

            # TODO: Might be worth hoisting comb statements out of m.If?
            with m.Switch(self.opcode):
                with m.Case(OpcodeType.OP_IMM):
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.I))

                    with m.If((funct3 == 1) | (funct3 == 5)):
                        op_map = Cat(funct3, funct7[-2], C(4))
                        with m.If(funct3 == 1):
                            with m.If(funct7 != 0):
                                m.d.sync += self.exception.valid.eq(1)
                        with m.Else():
                            with m.If((funct7 != 0) & (funct7 != 0b0100000)):
                                m.d.sync += self.exception.valid.eq(1)
                        m.d.sync += self.requested_op.eq(op_map)
                    with m.Else():
                        op_map = Cat(funct3, 0, C(4))
                        m.d.sync += self.requested_op.eq(op_map)
                with m.Case(OpcodeType.LUI):
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.U))
                    m.d.sync += self.requested_op.eq(0xD0)
                with m.Case(OpcodeType.AUIPC):
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.U))
                    m.d.sync += self.requested_op.eq(0x50)
                with m.Case(OpcodeType.OP):
                    op_map = Cat(funct3, funct7[-2], C(0xC))
                    with m.If((funct3 == 0) | (funct3 == 5)):
                        with m.If((funct7 != 0) & (funct7 != 0b0100000)):
                            m.d.sync += self.exception.valid.eq(1)
                        m.d.sync += self.requested_op.eq(op_map)
                    with m.Else():
                        with m.If(funct7 != 0):
                            m.d.sync += self.exception.valid.eq(1)
                        m.d.sync += self.requested_op.eq(op_map)
                with m.Case(OpcodeType.JAL):
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.J))
                    m.d.sync += self.requested_op.eq(0xB0)
                with m.Case(OpcodeType.JALR):
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.I))
                    m.d.sync += self.requested_op.eq(0x98)

                    with m.If(funct3 != 0):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.BRANCH):
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.B))
                    m.d.sync += self.requested_op.eq(Cat(funct3, C(0x11)))

                    with m.If((funct3 == 2) | (funct3 == 3)):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.LOAD):
                    op_map = Cat(funct3, C(1))
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.I))
                    m.d.sync += self.requested_op.eq(op_map)

                    with m.If((funct3 == 3) | (funct3 == 6) | (funct3 == 7)):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.STORE):
                    op_map = Cat(funct3, C(0x10))
                    m.d.sync += self.imm.eq(self.imm_bits(InsnImmFormat.S))
                    m.d.sync += self.requested_op.eq(op_map)

                    with m.If(funct3 >= 3):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.CUSTOM_0):
                    m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.MISC_MEM):
                    # RS1 and RD should be ignored for FENCE insn in a base
                    # impl.
                    m.d.sync += self.requested_op.eq(0x30)

                    with m.If(funct3 != 0):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.SYSTEM):
                    m.d.sync += self.exception.valid.eq(1)
                    with m.Switch(funct3):
                        zeroes = (rs1 == 0) & (rd == 0)
                        with m.Case(0):
                            with m.If((funct12 == 0) & zeroes):
                                # ecall
                                m.d.sync += self.exception.e_type.eq(MCause.Cause.ECALL_MMODE)  # noqa: E501
                            with m.Elif((funct12 == 1) & zeroes):
                                # ebreak
                                m.d.sync += self.exception.e_type.eq(MCause.Cause.BREAKPOINT)  # noqa: E501
                            with m.Elif((funct12 == 0b001100000010) & zeroes):
                                # mret
                                m.d.sync += [
                                    self.requested_op.eq(248),
                                    self.exception.valid.eq(0)
                                ]
                            with m.Elif((funct12 == 0b000100000101) & zeroes):
                                # wfi
                                m.d.sync += [
                                    self.requested_op.eq(0x30),
                                    self.exception.valid.eq(0)
                                ]

                        with m.Case(4):
                            pass
                        with m.Default():
                            # CSR ops take two cycles to decode. Rather than
                            # penalize the rest of the core, have the microcode
                            # jump to a temporary location. The next cycle
                            # will have the microcode jump to the _real_ CSR
                            # routine.
                            csr_encode = Cat(funct12[0:3], funct12[6])
                            m.d.sync += [
                                self.requested_op.eq(0x24),
                                forward_csr.eq(1),
                                self.exception.valid.eq(0),
                                self.csr_encoding.eq(csr_encode)
                            ]

                with m.Default():
                    # Catch-all for all ones.
                    m.d.sync += self.exception.valid.eq(1)

            # Catch-all for compressed insns, zero insn.
            with m.If(self.insn[0:2] != 0b11):
                m.d.sync += self.exception.valid.eq(1)

        # Second decode cycle if this is a CSR access.
        with m.If(forward_csr):
            ro0 = Signal()
            illegal = Signal()

            m.d.comb += illegal.eq(csr_map[0])
            m.d.comb += ro0.eq(csr_map[1])
            m.d.sync += self.exception.e_type.eq(MCause.Cause.ILLEGAL_INSN)
            m.d.sync += self.exception.valid.eq(0)

            with m.Switch(csr_quadrant):
                # Machine Mode CSRs.
                with m.Case(0b11):
                    # Most CSR accesses.
                    with m.If(illegal):
                        m.d.sync += self.exception.valid.eq(1)

                    # Read-only Zero CSRs. Includes CSRs that are in actually
                    # read-only space (top 2 bits set), all of which are 0
                    # for this core.
                    with m.Elif(ro0):
                        # AFAICT, writing to ro0 registers outside of the
                        # read-only space should succeed (but the write is
                        # ignored).
                        # None of the ro0 registers have side effects either?
                        # csrro0
                        m.d.sync += self.requested_op.eq(0x25)
                        with m.If(csr_ro_space):
                            # CSRRW and CSRRWI don't have a mechanism to only
                            # read a register.
                            with m.If((csr_op == 1) |
                                      (csr_op == 5) |
                                      (self.src_a != 0)):
                                m.d.sync += self.exception.valid.eq(1)

                    with m.Else():
                        # Jump to microcode routines for actual, implemented
                        # CSR registers.
                        with m.If((csr_op == 1) & (self.dst == 0)):
                            # csrw
                            m.d.sync += self.requested_op.eq(0x26)
                        with m.Elif((csr_op == 1) & (self.dst != 0)):
                            # csrrw
                            m.d.sync += self.requested_op.eq(0x27)
                        with m.Elif((csr_op == 2) & (self.src_a == 0)):
                            # csrr
                            m.d.sync += self.requested_op.eq(0x28)
                        with m.Elif((csr_op == 2) & (self.src_a != 0)):
                            # csrrs
                            m.d.sync += self.requested_op.eq(0x29)
                        with m.Elif((csr_op == 3) & (self.src_a == 0)):
                            # csrrc, no write
                            m.d.sync += self.requested_op.eq(0x28)
                        with m.Elif((csr_op == 3) & (self.src_a != 0)):
                            # csrrc
                            m.d.sync += self.requested_op.eq(0x2a)
                        with m.Elif((csr_op == 5) & (self.dst == 0)):
                            # csrwi
                            m.d.sync += self.requested_op.eq(0x2b)
                        with m.Elif((csr_op == 5) & (self.dst != 0)):
                            # csrrwi
                            m.d.sync += self.requested_op.eq(0x2c)
                        with m.Elif((csr_op == 6) & (self.src_a == 0)):
                            # csrrsi, no write
                            m.d.sync += self.requested_op.eq(0x28)
                        with m.Elif((csr_op == 6) & (self.src_a != 0)):
                            # csrrsi
                            m.d.sync += self.requested_op.eq(0x2d)
                        with m.Elif((csr_op == 7) & (self.src_a == 0)):
                            # csrrci, no write
                            m.d.sync += self.requested_op.eq(0x28)
                        with m.Elif((csr_op == 7) & (self.src_a != 0)):
                            # csrrci
                            m.d.sync += self.requested_op.eq(0x2e)
                        with m.Else():
                            # TODO: cover via rvformal.
                            # This might be reachable, but not while
                            # requested_op has a meaningful value in it.
                            # Make sure this is actually the case.
                            pass

                # Other Modes (User, Supervisor).
                with m.Default():
                    m.d.sync += self.exception.valid.eq(1)

        if self.formal:
            m.d.comb += [
                self.rvfi.rs1.eq(rs1),
                self.rvfi.rs2.eq(rs2),
                self.rvfi.rd.eq(rd),
                self.rvfi.do_decode.eq(self.do_decode),
                self.rvfi.funct12.eq(funct12),
                self.rvfi.funct3.eq(funct3),
                self.rvfi.insn.eq(self.insn),
            ]

            m.d.comb += self.rvfi.rd_valid.eq(
                ~((self.opcode == OpcodeType.BRANCH) |
                  (self.opcode == OpcodeType.MISC_MEM) |
                  (self.opcode == OpcodeType.STORE)))

        return m

    def imm_bits(self, imm_type):
        sign = self.insn[31]

        match imm_type:
            case InsnImmFormat.I:
                return Cat(self.insn[20:31], Value.replicate(sign, 21))
            case InsnImmFormat.S:
                return Cat(self.insn[7], self.insn[8:12], self.insn[25:31],
                           Value.replicate(sign, 21))
            case InsnImmFormat.B:
                return Cat(C(0), self.insn[8:12], self.insn[25:31],
                           self.insn[7], Value.replicate(sign, 20))
            case InsnImmFormat.U:
                return Cat(C(0, 12), self.insn[12:20], self.insn[20:31], sign)
            case InsnImmFormat.J:
                return Cat(C(0), self.insn[21:25], self.insn[25:31],
                           self.insn[20], self.insn[12:20],
                           Value.replicate(sign, 12))

    def mmode_csr_quadrant_init(self):
        def idx(csr_addr):
            return (csr_addr & 0xff) + ((csr_addr & 0xc00) >> 2)

        # illegal: bit 0 set
        # zero: bit 1 set
        # mstatus, mie, mtvec, mscratch, mepc, mcause, mip: both bits clear
        # ^These registers are actually implemented.
        init = [1]*1024  # By default, access is illegal.

        init[idx(0xF11)] = 2  # mvendorid
        init[idx(0xF12)] = 2  # marchid
        init[idx(0xF13)] = 2  # mimpid
        init[idx(0xF14)] = 2  # mhartid
        init[idx(0xF15)] = 2  # mconfigptr
        init[idx(0x300)] = 0  # mstatus
        init[idx(0x301)] = 2  # misa
        init[idx(0x302)] = 1  # medeleg
        init[idx(0x303)] = 1  # mideleg
        init[idx(0x304)] = 0  # mie
        init[idx(0x305)] = 0  # mtvec
        init[idx(0x306)] = 1  # mcounteren
        init[idx(0x310)] = 2  # mstatush
        init[idx(0x340)] = 0  # mscratch
        init[idx(0x341)] = 0  # mepc
        init[idx(0x342)] = 0  # mcause
        init[idx(0x343)] = 2  # mtval
        init[idx(0x344)] = 0  # mip
        init[idx(0x34A)] = 1  # mtinst
        init[idx(0x34B)] = 1  # mtval2
        init[idx(0x30A)] = 1  # menvcfg
        init[idx(0x31A)] = 1  # menvcfgh
        init[idx(0x747)] = 1  # mseccfg
        init[idx(0x757)] = 1  # mseccfgh
        for i in range(0x3A0, 0x3B0):
            init[idx(i)] = 1  # pmpcfg0-15 illegal
        for i in range(0x3B0, 0x3F0):
            init[idx(i)] = 1  # pmpaddr0-63 illegal
        init[idx(0xB00)] = 2  # mcycle
        init[idx(0xB02)] = 2  # minstret
        for i in range(0xB03, 0xB1F):
            init[idx(i)] = 2  # mhpmcounter3-31
        init[idx(0xB80)] = 2  # mcycleh
        init[idx(0xB82)] = 2  # minstreth
        for i in range(0xB83, 0xB8F):
            init[idx(i)] = 2  # mhpmcounter3h-31
        init[idx(0x320)] = 2  # mcountinhibit
        for i in range(0x323, 0x340):
            init[idx(i)] = 2  # mhpmevent3-31
        init[idx(0x7A0)] = 1  # tselect
        init[idx(0x7A1)] = 1
        init[idx(0x7A2)] = 1
        init[idx(0x7A3)] = 1  # tdata1-3
        init[idx(0x7A8)] = 1  # mcontext
        init[idx(0x7B0)] = 1  # dcsr
        init[idx(0x7B1)] = 1  # dpc
        init[idx(0x7B2)] = 1  # dscratch0
        init[idx(0x7B3)] = 1  # dscratch1

        return init
