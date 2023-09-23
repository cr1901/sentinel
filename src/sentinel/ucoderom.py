import os.path
import enum
from pathlib import Path
from collections import OrderedDict
from operator import attrgetter

from amaranth import *
from m5pre import *
from m5meta import *

class UCodeROM(Elaboratable):
    def __init__(self, *, field_defs=None, hex=None):
        self.main_file = (Path(__file__).parent / "microcode.asm").resolve()
        self.field_defs = field_defs
        self.hex = hex
        self.ucode_contents = [0]*256
        self.fields = {}
        self.signals = OrderedDict()

        self.assemble()
        self.ucode_mem = Memory(width=32, depth=256, init=self.ucode_contents)

        self.adr = Signal(8)
        self.dat_r = Signal(32)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.ucode_mem.read_port(transparent=False)

        m.d.comb += [
            rdport.addr.eq(self.adr),
            self.dat_r.eq(rdport.data),
            Cat(*self.signals.values()).eq(self.dat_r)
        ]

        return m

    def ports(self):
        return [*self.signals.values(), self.adr] # , self.dat_r]


    # Like M5Meta.assemble(), but pass3 is more flexible and tailored to my
    # needs.
    def assemble(self):
        with open(self.main_file) as mfp:
            self.m5meta = M5Meta(mfp, obj_base_fn = "microcode.asm")
            self.m5meta.src = M5Pre(mfp).read()

        passes = [None,
                  self.m5meta.pass12,
                  self.m5meta.pass12]

        for p in range(1, len(passes)):
            self.m5meta.pass_num = p
            passes[p]()

        # We only have one address space in this core. Call it
        # "block_ram" for consistency.
        assert(len(self.m5meta.spaces) == 1)

        # pass3- Create enums and signals for amaranth code. Optionally
        # generate extra files for debugging.
        for name, space in self.m5meta.spaces.items():
            assert(space.name == "block_ram")
            space.generate_object()

            self.create_mem_init(space)
            self.create_field_enums_and_signals(space)

            if self.hex:
                space.write_hex_file(self.hex)

            if self.field_defs:
                with open(self.field_defs, 'w') as f:
                    space.write_fdef(f)

    def create_mem_init(self, space):
        prev_addr = -1

        # Pre-filled with zeros. Fill in addresses that m5meta claims to
        # contain data by converting the address to an int (a dictionary
        # is used to represent address space holes implicitly).
        for addr in sorted(space.data.keys()):
            self.ucode_contents[int(addr)] = space.data[addr]

        # For a future, more elegant approach.
        assert(len(self.ucode_contents) == 256)

    def create_field_enums_and_signals(self, space):
        sig_list = []

        for fd in space.fields.values():
            if fd.enum:
                self.fields[fd.name] = enum.Enum(fd.name, fd.enum)
            sig_list.append(fd)

        # Sort from LSB offset to MSB offset. space.fields already does this I
        # believe but this is a precaution. The name param is to avoid names
        # like \$signal.
        for s in sorted(sig_list, key=attrgetter("origin")):
            self.signals[s.name] = Signal(s.width, name=s.name) # , reset=s.default)
