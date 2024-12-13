from amaranth import Signal, Module, Cat, C, unsigned
from amaranth.lib.data import Struct, StructLayout
from amaranth.lib.wiring import Component, Signature, In, Out

from .control import MappingROM
from .csr import MCause, Quadrant, AccessMode, MachineAddr as CSRM
from .insn import Insn, OpcodeType


class DecodeException(Struct):
    valid: unsigned(1)
    e_type: MCause.Cause


# Only valid for Machine Mode CSRs at present (bits 8 and 9 stripped). No plans
# to support Supervisor Mode, but User Mode might be worthwhile.
# Read-only mode can be easily calculated from bits 10 and 11, so not handled
# here.
class CSRAttributes(Component):
    _DataLayout = StructLayout({
        "ill": unsigned(1),
        "ro0": unsigned(1)
    })
    _Implemented = C({}, _DataLayout)
    _Illegal = C({"ill": 1}, _DataLayout)
    _Ro0 = C({"ro0": 1}, _DataLayout)

    class _ROM:
        def __init__(self, init):
            self.rom = init

        def idx(self, csr_addr):
            # Strip bits 8 and 9 and concatenate to index into ROM.
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
        # By default, access is illegal. Any fields added should nominally
        # be one-hot (zero allowed).
        self._rom = CSRAttributes._ROM(
            [CSRAttributes._Illegal] * 1024)

        sig = {
            "addr": Out(12),
            "data": In(CSRAttributes._DataLayout),
        }

        self._rom_init()
        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        # FIXME: Use _CSR somehow to make self.addr slicing nicer?
        # Use Cases to let the optimizer decide whether to use a BRAM or not.
        with m.Switch(Cat(self.addr[0:8], self.addr[10:])):
            for i, v in enumerate(self._rom):
                with m.Case(i):
                    m.d.sync += self.data.eq(v)

        return m

    def _rom_init(self):
        self._rom[CSRM.MVENDORID] = CSRAttributes._Ro0
        self._rom[CSRM.MARCHID] = CSRAttributes._Ro0
        self._rom[CSRM.MIMPID] = CSRAttributes._Ro0
        self._rom[CSRM.MHARTID] = CSRAttributes._Ro0
        self._rom[CSRM.MCONFIGPTR] = CSRAttributes._Ro0
        self._rom[CSRM.MSTATUS] = CSRAttributes._Implemented
        self._rom[CSRM.MISA] = CSRAttributes._Ro0
        self._rom[CSRM.MIE] = CSRAttributes._Implemented
        self._rom[CSRM.MTVEC] = CSRAttributes._Implemented
        self._rom[CSRM.MSTATUSH] = CSRAttributes._Ro0
        self._rom[CSRM.MSCRATCH] = CSRAttributes._Implemented
        self._rom[CSRM.MEPC] = CSRAttributes._Implemented
        self._rom[CSRM.MCAUSE] = CSRAttributes._Implemented
        self._rom[CSRM.MTVAL] = CSRAttributes._Ro0
        self._rom[CSRM.MIP] = CSRAttributes._Implemented
        self._rom[CSRM.MCYCLE] = CSRAttributes._Ro0
        self._rom[CSRM.MINSTRET] = CSRAttributes._Ro0
        for i in range(CSRM.MHPMCOUNTER3, CSRM.MHPMCOUNTER31 + 1):
            self._rom[i] = CSRAttributes._Ro0
        self._rom[CSRM.MCYCLEH] = CSRAttributes._Ro0
        self._rom[CSRM.MINSTRETH] = CSRAttributes._Ro0
        for i in range(CSRM.MHPMCOUNTER3H, CSRM.MHPMCOUNTER31H + 1):
            self._rom[i] = CSRAttributes._Ro0
        self._rom[CSRM.MCOUNTINHIBIT] = CSRAttributes._Ro0
        for i in range(CSRM.MHPMEVENT3, CSRM.MHPMEVENT31 + 1):
            self._rom[i] = CSRAttributes._Ro0


class ImmediateGenerator(Component):
    def __init__(self):
        sig = {
            "enable": Out(1),
            "insn": Out(32),
            "imm": In(32)
        }

        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        insn = Insn(self.insn)

        with m.If(self.enable):
            with m.Switch(insn.opcode):
                with m.Case(OpcodeType.OP_IMM):
                    m.d.sync += self.imm.eq(insn.imm.I)
                with m.Case(OpcodeType.JALR):
                    m.d.sync += self.imm.eq(insn.imm.I)
                with m.Case(OpcodeType.LOAD):
                    m.d.sync += self.imm.eq(insn.imm.I)
                with m.Case(OpcodeType.LUI):
                    m.d.sync += self.imm.eq(insn.imm.U)
                with m.Case(OpcodeType.AUIPC):
                    m.d.sync += self.imm.eq(insn.imm.U)
                with m.Case(OpcodeType.JAL):
                    m.d.sync += self.imm.eq(insn.imm.J)
                with m.Case(OpcodeType.BRANCH):
                    m.d.sync += self.imm.eq(insn.imm.B)
                with m.Case(OpcodeType.STORE):
                    m.d.sync += self.imm.eq(insn.imm.S)

        return m


# ExceptionControl is aware of CSR decode cycles.
class ExceptionControl(Component):
    def __init__(self):
        sig = {
            "start": Out(1),
            "insn": Out(32),
            "csr_attr": Out(CSRAttributes._DataLayout),
            "exception": In(DecodeException),
        }

        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        insn = Insn(self.insn)

        src_a = Signal.like(insn.rs1)
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

        with m.If(self.start):
            m.d.sync += src_a.eq(insn.rs1)

            # TODO: Might be worth hoisting comb statements out of m.If?
            with m.Switch(insn.opcode):
                with m.Case(OpcodeType.OP_IMM):
                    with m.If((insn.funct3 == 1) | (insn.funct3 == 5)):
                        with m.If(insn.funct3 == 1):
                            with m.If(insn.funct7 != 0):
                                m.d.sync += self.exception.valid.eq(1)
                        with m.Else():
                            with m.If((insn.funct7 != 0) & (insn.funct7 != 0b0100000)):
                                m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.LUI):
                    pass
                with m.Case(OpcodeType.AUIPC):
                    pass
                with m.Case(OpcodeType.OP):
                    with m.If((insn.funct3 == 0) | (insn.funct3 == 5)):
                        with m.If((insn.funct7 != 0) & (insn.funct7 != 0b0100000)):  # noqa: E501
                            m.d.sync += self.exception.valid.eq(1)
                    with m.Else():
                        with m.If(insn.funct7 != 0):
                            m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.JAL):
                    pass
                with m.Case(OpcodeType.JALR):
                    with m.If(insn.funct3 != 0):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.BRANCH):
                    with m.If((insn.funct3 == 2) | (insn.funct3 == 3)):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.LOAD):
                    with m.If((insn.funct3 == 3) | (insn.funct3 == 6) | (insn.funct3 == 7)):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.STORE):
                    with m.If(insn.funct3 >= 3):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.CUSTOM_0):
                    m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.MISC_MEM):
                    # RS1 and RD should be ignored for FENCE insn in a base
                    # impl.
                    with m.If(insn.funct3 != 0):
                        m.d.sync += self.exception.valid.eq(1)
                with m.Case(OpcodeType.SYSTEM):
                    m.d.sync += self.exception.valid.eq(1)
                    # Yes, stripping the lower bits inexplicably makes a
                    # difference in resource usage...
                    with m.If(insn.raw[7:] == (Insn.ECALL >> 7)):
                        m.d.sync += self.exception.e_type.eq(MCause.Cause.ECALL_MMODE)  # noqa: E501
                    with m.Elif(insn.raw == Insn.EBREAK):
                        m.d.sync += self.exception.e_type.eq(MCause.Cause.BREAKPOINT)  # noqa: E501
                    with m.Elif(insn.raw == Insn.MRET):
                        m.d.sync += self.exception.valid.eq(0)
                    with m.Elif(insn.raw == Insn.WFI):
                        m.d.sync += self.exception.valid.eq(0)
                    with m.Elif((insn.funct3 != 0) & (insn.funct3 != 4)):
                        # CSR ops take two cycles to decode. Rather than
                        # penalize the rest of the core, have the microcode
                        # jump to a temporary location. The next cycle
                        # will have the microcode jump to the _real_ CSR
                        # routine.
                        m.d.sync += [
                            forward_csr.eq(1),
                            self.exception.valid.eq(0),
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

            with m.If(self.csr_attr.ill):
                m.d.sync += self.exception.valid.eq(1)

            # Read-only CSRs. AFAICT, writing to ro0 registers outside
            # of the read-only space should succeed (but the write is
            # ignored). CSRRW and CSRRWI don't have a mechanism to only
            # read a register.
            with m.Elif(csr_ro_space & ((csr_op == Insn._CSR.RW) |
                                        (csr_op == Insn._CSR.RWI) |
                                        (src_a != 0))):
                m.d.sync += self.exception.valid.eq(1)

            # Machine Mode CSRs- CSRAttributes only valid for Machine Mode
            # Quadrant for now (User mode may follow... Supervisor probably
            # not).
            with m.Elif(csr_quadrant != Quadrant.MACHINE):
                m.d.sync += self.exception.valid.eq(1)

        return m


class Decode(Component):
    def __init__(self, *, formal=False):
        self.formal = formal
        self.csr_attr = CSRAttributes()
        self.imm_gen = ImmediateGenerator()
        self.mapping = MappingROM()
        self.except_ctrl = ExceptionControl()

        sig = {
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

            sig["rvfi"] = In(rvfi)

        super().__init__(Signature(sig).flip())

    def elaborate(self, platform):
        m = Module()

        m.submodules.csr_attr = self.csr_attr
        m.submodules.imm_gen = self.imm_gen
        m.submodules.mapping = self.mapping
        m.submodules.except_ctrl = self.except_ctrl

        insn = Insn(self.insn)

        m.d.comb += [
            self.opcode.eq(insn.opcode),
            self.src_a_unreg.eq(insn.rs1),
            self.imm.eq(self.imm_gen.imm),

            self.csr_attr.addr.eq(insn.csr.addr),

            self.imm_gen.enable.eq(self.do_decode),
            self.imm_gen.insn.eq(self.insn),

            self.mapping.start.eq(self.do_decode),
            self.mapping.insn.eq(self.insn),
            self.mapping.csr_attr.eq(self.csr_attr.data),
            self.requested_op.eq(self.mapping.requested_op),
            self.csr_encoding.eq(self.mapping.csr_encoding),

            self.except_ctrl.start.eq(self.do_decode),
            self.except_ctrl.insn.eq(self.insn),
            self.except_ctrl.csr_attr.eq(self.csr_attr.data),
            self.exception.eq(self.except_ctrl.exception)
        ]

        with m.If(self.do_decode):
            m.d.sync += [
                # For now, unconditionally propogate these and rely on
                # microcode program to ignore when necessary.
                self.src_a.eq(insn.rs1),
                self.src_b.eq(insn.rs2),
                self.dst.eq(insn.rd),
            ]

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
                ~((self.opcode == OpcodeType.BRANCH) |
                  (self.opcode == OpcodeType.MISC_MEM) |
                  (self.opcode == OpcodeType.STORE)))

        return m
