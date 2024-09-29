from dataclasses import dataclass


@dataclass
class RV32Regs:
    @classmethod
    def from_top_module(cls, m, ctx):
        gpregs = []
        for r_id in range(32):
            gpregs.append(ctx.get(m.datapath.regfile.m_data[r_id]))

        return cls(*gpregs, PC=(ctx.get(m.datapath.pc.dat_r)))

    R0: int = 0
    R1: int = 0
    R2: int = 0
    R3: int = 0
    R4: int = 0
    R5: int = 0
    R6: int = 0
    R7: int = 0
    R8: int = 0
    R9: int = 0
    R10: int = 0
    R11: int = 0
    R12: int = 0
    R13: int = 0
    R14: int = 0
    R15: int = 0
    R16: int = 0
    R17: int = 0
    R18: int = 0
    R19: int = 0
    R20: int = 0
    R21: int = 0
    R22: int = 0
    R23: int = 0
    R24: int = 0
    R25: int = 0
    R26: int = 0
    R27: int = 0
    R28: int = 0
    R29: int = 0
    R30: int = 0
    R31: int = 0
    PC: int = 0


@dataclass
class CSRRegs:
    @classmethod
    def from_top_module(cls, m, ctx):
        csrregs = {}

        csrregs["MSCRATCH"] = ctx.get(m.datapath.regfile.m_data[0x28])
        csrregs["MSTATUS"] = ctx.get(m.datapath.csr.mstatus_r.as_value())
        csrregs["MTVEC"] = ctx.get(m.datapath.regfile.m_data[0x25])
        csrregs["MIE"] = ctx.get(m.datapath.csr.mie_r.as_value())
        csrregs["MIP"] = ctx.get(m.datapath.csr.mip_r.as_value())
        csrregs["MEPC"] = ctx.get(m.datapath.regfile.m_data[0x29])
        csrregs["MCAUSE"] = ctx.get(m.datapath.regfile.m_data[0x2A])

        return cls(**csrregs)

    MSCRATCH: int = 0
    MSTATUS: int = 0b11000_0000_0000
    MTVEC: int = 0
    MEPC: int = 0
    MCAUSE: int = 0
    MIP: int = 0
    MIE: int = 0
