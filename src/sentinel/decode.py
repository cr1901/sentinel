from amaranth import Signal, Module, Cat, Value, C, unsigned
from amaranth.lib import enum
from amaranth.lib.data import Struct, StructLayout
from amaranth.lib.wiring import Component, Signature, In, Out

from .csr import MCause, Quadrant, AccessMode, MachineAddr as CSRM


class Insn:
    """View of all immediately-apparent information in a RISC-V instruction."""

    # "Immediately-apparent" means "I can get this info with Cats, Slices,
    # and Replicates".

    # Does not inherit from View because Layouts are not designed to retrieve
    # non-contiguous bits.
    class _Imm:
        def __init__(self, value):
            self.raw = value
            self.sign = self.raw[-1]

        @property
        def I(self):  # noqa: E743
            return Cat(self.raw[20:31], Value.replicate(self.sign, 21))

        @property
        def S(self):
            return Cat(self.raw[7], self.raw[8:12], self.raw[25:31],
                       Value.replicate(self.sign, 21))

        @property
        def B(self):
            return Cat(C(0), self.raw[8:12], self.raw[25:31], self.raw[7],
                       Value.replicate(self.sign, 20))

        @property
        def U(self):
            return Cat(C(0, 12), self.raw[12:20], self.raw[20:31], self.sign)

        @property
        def J(self):
            return Cat(C(0), self.raw[21:25], self.raw[25:31], self.raw[20],
                       self.raw[12:20], Value.replicate(self.sign, 12))

    class _CSR:
        def __init__(self, value):
            self.raw = value[20:]

        @property
        def addr(self):
            return self.raw

        @property
        def quadrant(self):
            return enum.EnumView(Quadrant, self.raw[8:10])

        @property
        def access(self):
            return enum.EnumView(AccessMode, self.raw[10:])

    class OpcodeType(enum.Enum, shape=unsigned(5)):
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

    def __init__(self, value):
        self.raw = value
        self.imm = Insn._Imm(self.raw)
        self.csr = Insn._CSR(self.raw)

    @property
    def opcode(self):
        return Insn.OpcodeType(self.raw[2:7])

    @property
    def rd(self):
        return self.raw[7:12]

    @property
    def funct3(self):
        return self.raw[12:15]

    @property
    def rs1(self):
        return self.raw[15:20]

    @property
    def rs2(self):
        return self.raw[20:25]

    @property
    def funct7(self):
        return self.raw[25:]

    @property
    def funct12(self):
        return self.raw[20:]

    @property
    def sign(self):
        return self.raw[-1]


class CSRAccessControl(Component):
    _DataLayout = StructLayout({
        "ill": unsigned(1),
        "ro": unsigned(1)
    })
    _Implemented = C({}, _DataLayout)
    _Illegal = C({"ill": 1}, _DataLayout)
    _Ro0 = C({"ro": 1}, _DataLayout)

    # No plans to support Supervisor Mode, but User Mode might be worthwhile.
    class _MachineROM:
        def __init__(self, init):
            self.rom = init

        def idx(self, csr_addr):
            return (csr_addr & 0xff) + ((csr_addr & 0xc00) >> 2)

        def __getitem__(self, k):
            self.rom[self.idx(k)]

        def __setitem__(self, k, v):
            self.rom[self.idx(k)] = v

        def __iter__(self):
            return iter(self.rom)

    def __init__(self):
        # illegal: bit 0 set
        # zero: bit 1 set
        # mstatus, mie, mtvec, mscratch, mepc, mcause, mip: both bits clear
        # ^These registers are actually implemented.
        # By default, access is illegal.
        self._machine = CSRAccessControl._MachineROM(
            [CSRAccessControl._Illegal] * 1024)

        sig = {
            "addr": Out(12),
            "data": In(StructLayout({
                "ill": unsigned(1),
                "ro": unsigned(1)
            })),
        }

        self._machine_rom_init()
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        # FIXME: Use _CSR somehow to make self.addr slicing nicer?
        # Use cases to let the optimizer decide whether to use a BRAM or not.
        with m.Switch(Cat(self.addr[0:8], self.addr[10:])):
            for i, v in enumerate(self._machine):
                with m.Case(i):
                    m.d.sync += self.data.eq(v)

        return m

    def _machine_rom_init(self):
        self._machine[CSRM.MVENDORID] = CSRAccessControl._Ro0
        self._machine[CSRM.MARCHID] = CSRAccessControl._Ro0
        self._machine[CSRM.MIMPID] = CSRAccessControl._Ro0
        self._machine[CSRM.MHARTID] = CSRAccessControl._Ro0
        self._machine[CSRM.MCONFIGPTR] = CSRAccessControl._Ro0
        self._machine[CSRM.MSTATUS] = CSRAccessControl._Implemented
        self._machine[CSRM.MISA] = CSRAccessControl._Ro0
        self._machine[CSRM.MIE] = CSRAccessControl._Implemented
        self._machine[CSRM.MTVEC] = CSRAccessControl._Implemented
        self._machine[CSRM.MSTATUSH] = CSRAccessControl._Ro0
        self._machine[CSRM.MSCRATCH] = CSRAccessControl._Implemented
        self._machine[CSRM.MEPC] = CSRAccessControl._Implemented
        self._machine[CSRM.MCAUSE] = CSRAccessControl._Implemented
        self._machine[CSRM.MTVAL] = CSRAccessControl._Ro0
        self._machine[CSRM.MIP] = CSRAccessControl._Implemented
        self._machine[CSRM.MCYCLE] = CSRAccessControl._Ro0
        self._machine[CSRM.MINSTRET] = CSRAccessControl._Ro0
        for i in range(CSRM.MHPMCOUNTER3, CSRM.MHPMCOUNTER31 + 1):
            self._machine[i] = CSRAccessControl._Ro0
        self._machine[CSRM.MCYCLEH] = CSRAccessControl._Ro0
        self._machine[CSRM.MINSTRETH] = CSRAccessControl._Ro0
        for i in range(CSRM.MHPMCOUNTER3H, CSRM.MHPMCOUNTER31H + 1):
            self._machine[i] = CSRAccessControl._Ro0
        self._machine[CSRM.MCOUNTINHIBIT] = CSRAccessControl._Ro0
        for i in range(CSRM.MHPMEVENT3, CSRM.MHPMEVENT31 + 1):
            self._machine[i] = CSRAccessControl._Ro0  # mhpmevent3-31


class DecodeException(Struct):
    valid: unsigned(1)
    e_type: MCause.Cause


class Decode(Component):
    def __init__(self, *, formal=False):
        self.formal = formal
        self.csr_ctrl = CSRAccessControl()

        sig = {
            "do_decode": Out(1),
            "insn": Out(32),
            "src_a_unreg": In(5),
            "src_a": In(5),
            "src_b": In(5),
            "imm": In(32),
            "dst": In(5),
            "opcode": In(Insn.OpcodeType),
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

            sig["rvfi"] = In(rvfi)

        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        m.submodules.csr_ctrl = self.csr_ctrl

        insn = Insn(self.insn)

        m.d.comb += [
            self.opcode.eq(insn.opcode),
            self.src_a_unreg.eq(insn.rs1),
            self.csr_ctrl.addr.eq(insn.csr.addr)
        ]

        forward_csr = Signal()
        csr_quadrant = Signal(Quadrant)
        csr_op = Signal.like(insn.funct3)
        csr_ro_space = Signal()

        m.d.sync += [
            forward_csr.eq(0),
            self.exception.e_type.eq(MCause.Cause.ILLEGAL_INSN),
            self.exception.valid.eq(0),
            csr_quadrant.eq(insn.csr.quadrant),
            csr_op.eq(insn.funct3),
            csr_ro_space.eq(insn.csr.access == AccessMode.READ_ONLY)
        ]

        with m.If(self.do_decode):
            m.d.sync += [
                # For now, unconditionally propogate these and rely on
                # microcode program to ignore when necessary.
                self.src_a.eq(insn.rs1),
                self.src_b.eq(insn.rs2),
                self.dst.eq(insn.rd),
            ]

            # TODO: Might be worth hoisting comb statements out of m.If?
            with m.Switch(self.opcode):
                with m.Case(Insn.OpcodeType.OP_IMM):
                    m.d.sync += self.imm.eq(insn.imm.I)

                    with m.If((insn.funct3 == 1) | (insn.funct3 == 5)):
                        op_map = Cat(insn.funct3, insn.funct7[-2], C(4))
                        with m.If(insn.funct3 == 1):
                            with m.If(insn.funct7 != 0):
                                m.d.sync += self.exception.valid.eq(1)
                        with m.Else():
                            with m.If((insn.funct7 != 0) & (insn.funct7 != 0b0100000)):  # noqa: E501
                                m.d.sync += self.exception.valid.eq(1)
                        m.d.sync += self.requested_op.eq(op_map)
                    with m.Else():
                        op_map = Cat(insn.funct3, 0, C(4))
                        m.d.sync += self.requested_op.eq(op_map)
                with m.Case(Insn.OpcodeType.LUI):
                    m.d.sync += self.imm.eq(insn.imm.U)
                    m.d.sync += self.requested_op.eq(0xD0)
                with m.Case(Insn.OpcodeType.AUIPC):
                    m.d.sync += self.imm.eq(insn.imm.U)
                    m.d.sync += self.requested_op.eq(0x50)
                with m.Case(Insn.OpcodeType.OP):
                    op_map = Cat(insn.funct3, insn.funct7[-2], C(0xC))
                    with m.If((insn.funct3 == 0) | (insn.funct3 == 5)):
                        with m.If((insn.funct7 != 0) & (insn.funct7 != 0b0100000)):  # noqa: E501
                            m.d.sync += self.exception.valid.eq(1)
                        m.d.sync += self.requested_op.eq(op_map)
                    with m.Else():
                        with m.If(insn.funct7 != 0):
                            m.d.sync += self.exception.valid.eq(1)
                        m.d.sync += self.requested_op.eq(op_map)
                with m.Case(Insn.OpcodeType.JAL):
                    m.d.sync += self.imm.eq(insn.imm.J)
                    m.d.sync += self.requested_op.eq(0xB0)
                with m.Case(Insn.OpcodeType.JALR):
                    m.d.sync += self.imm.eq(insn.imm.I)
                    m.d.sync += self.requested_op.eq(0x98)

                    with m.If(insn.funct3 != 0):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(Insn.OpcodeType.BRANCH):
                    m.d.sync += self.imm.eq(insn.imm.B)
                    m.d.sync += self.requested_op.eq(Cat(insn.funct3, C(0x11)))

                    with m.If((insn.funct3 == 2) | (insn.funct3 == 3)):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(Insn.OpcodeType.LOAD):
                    op_map = Cat(insn.funct3, C(1))
                    m.d.sync += self.imm.eq(insn.imm.I)
                    m.d.sync += self.requested_op.eq(op_map)

                    with m.If((insn.funct3 == 3) | (insn.funct3 == 6) | (insn.funct3 == 7)):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(Insn.OpcodeType.STORE):
                    op_map = Cat(insn.funct3, C(0x10))
                    m.d.sync += self.imm.eq(insn.imm.S)
                    m.d.sync += self.requested_op.eq(op_map)

                    with m.If(insn.funct3 >= 3):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(Insn.OpcodeType.CUSTOM_0):
                    m.d.sync += self.exception.valid.eq(1)
                with m.Case(Insn.OpcodeType.MISC_MEM):
                    # RS1 and RD should be ignored for FENCE insn in a base
                    # impl.
                    m.d.sync += self.requested_op.eq(0x30)

                    with m.If(insn.funct3 != 0):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(Insn.OpcodeType.SYSTEM):
                    m.d.sync += self.exception.valid.eq(1)
                    with m.Switch(insn.funct3):
                        zeroes = (insn.rs1 == 0) & (insn.rd == 0)
                        with m.Case(0):
                            with m.If((insn.funct12 == 0) & zeroes):
                                # ecall
                                m.d.sync += self.exception.e_type.eq(MCause.Cause.ECALL_MMODE)  # noqa: E501
                            with m.Elif((insn.funct12 == 1) & zeroes):
                                # ebreak
                                m.d.sync += self.exception.e_type.eq(MCause.Cause.BREAKPOINT)  # noqa: E501
                            with m.Elif((insn.funct12 == 0b001100000010) & zeroes):
                                # mret
                                m.d.sync += [
                                    self.requested_op.eq(248),
                                    self.exception.valid.eq(0)
                                ]
                            with m.Elif((insn.funct12 == 0b000100000101) & zeroes):
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
                            csr_encode = Cat(insn.funct12[0:3], insn.funct12[6])
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
            m.d.sync += self.exception.e_type.eq(MCause.Cause.ILLEGAL_INSN)
            m.d.sync += self.exception.valid.eq(0)

            with m.Switch(csr_quadrant):
                # Machine Mode CSRs.
                with m.Case(Quadrant.MACHINE):
                    # Most CSR accesses.
                    with m.If(self.csr_ctrl.data.ill):
                        m.d.sync += self.exception.valid.eq(1)

                    # Read-only Zero CSRs. Includes CSRs that are in actually
                    # read-only space (top 2 bits set), all of which are 0
                    # for this core.
                    with m.Elif(self.csr_ctrl.data.ro):
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
                self.rvfi.rs1.eq(insn.rs1),
                self.rvfi.rs2.eq(insn.rs2),
                self.rvfi.rd.eq(insn.rd),
                self.rvfi.do_decode.eq(self.do_decode),
                self.rvfi.funct12.eq(insn.funct12),
                self.rvfi.funct3.eq(insn.funct3),
                self.rvfi.insn.eq(self.insn),
            ]

            m.d.comb += self.rvfi.rd_valid.eq(
                ~((self.opcode == Insn.OpcodeType.BRANCH) |
                  (self.opcode == Insn.OpcodeType.MISC_MEM) |
                  (self.opcode == Insn.OpcodeType.STORE)))

        return m
