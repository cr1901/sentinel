from amaranth import Cat, C, Module, Signal, Elaboratable, Memory
from amaranth.lib.wiring import Component, Signature, In, Out

from sentinel.ucoderom import UCodeFieldClasses


class ProgramCounter(Elaboratable):
    def __init__(self, PcAction):
        self.pc = Signal(32)
        self.PcAction = PcAction
        self.action = Signal(self.PcAction)
        self.dat_w = Signal(30)

    def elaborate(self, platform):
        m = Module()

        with m.Switch(self.action):
            with m.Case(self.PcAction.INC):
                m.d.sync += self.pc.eq(self.pc + 4)
            with m.Case(self.PcAction.LOAD_ABS):
                m.d.sync += self.pc.eq(Cat(C(0, 2), self.dat_w))
            with m.Case(self.PcAction.LOAD_REL):
                m.d.sync += self.pc.eq(self.pc + Cat(C(0, 2), self.dat_w))

        return m


class RegFile(Elaboratable):
    def __init__(self, GpAction):
        self.adr = Signal(5)
        self.dat_r = Signal(32)
        self.dat_w = Signal(32)
        self.GpAction = GpAction
        self.action = Signal(self.GpAction)
        self.mem = Memory(width=32, depth=32)

    def elaborate(self, platform):
        m = Module()

        # Re: transparent, let's attempt to save some resources for now.
        m.submodules.rdport = rdport = self.mem.read_port(transparent=False)
        m.submodules.wrport = wrport = self.mem.write_port()

        m.d.comb += [
            rdport.addr.eq(self.adr),
            wrport.addr.eq(self.adr),
            wrport.data.eq(self.dat_w),
        ]

        # Zero register logic- ignore writes/return 0 for reads.
        with m.If(self.adr == 0):
            m.d.comb += self.dat_r.eq(0)
        with m.Else():
            m.d.comb += [
                self.dat_r.eq(rdport.data),
                wrport.en.eq(self.action == self.GpAction.WRITE_DST)
            ]

        return m


def data_path_ctrl_signature(GpAction, PcAction):
    return Signature({
        "gp_action": Out(GpAction),
        "pc_action": Out(PcAction)
    })


class DataPath(Component):
    @property
    def signature(self):
        return Signature({
            "gp": Out(Signature({
                "adr": Out(5),
                "dat_r": In(32),
                "dat_w": Out(32),
            })),
            "pc": Out(Signature({
                "dat_r": In(32),
                "dat_w": Out(32),
            })),
            "ctrl": Out(data_path_ctrl_signature(self.GpAction, self.PcAction))
        }).flip()

    def __init__(self, ucode: UCodeFieldClasses):
        self.GpAction = ucode["reg_op"]
        self.PcAction = ucode["pc_action"]
        super().__init__()

        self.pc_mod = ProgramCounter(self.PcAction)
        self.regfile = RegFile(self.GpAction)

    def elaborate(self, platform):
        m = Module()

        m.submodules.pc_mod = self.pc_mod
        m.submodules.regfile = self.regfile

        m.d.comb += [
            self.regfile.adr.eq(self.gp.adr),
            self.regfile.dat_w.eq(self.gp.dat_w),
            self.regfile.action.eq(self.ctrl.gp_action),
            self.gp.dat_r.eq(self.regfile.dat_r),

            self.pc_mod.action.eq(self.ctrl.pc_action),
            self.pc.dat_r.eq(self.pc_mod.pc),
            self.pc_mod.dat_w.eq(self.pc.dat_w[2:])
        ]

        return m
