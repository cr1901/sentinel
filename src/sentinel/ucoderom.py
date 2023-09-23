import os.path
import enum as pyenum
from io import IOBase
from pathlib import Path
from collections import OrderedDict
from operator import attrgetter
from itertools import tee, zip_longest

from amaranth import *
from amaranth.lib.data import StructLayout
from amaranth.lib.wiring import Signature, In, Out, Component
from m5pre import *
from m5meta import *


class UCodeROM(Component):
    @property
    def signature(self):
        return Signature({
            "addr": Out(self.adr.shape()),
            "fields": In(self.field_layout)
        })

    def __init__(self, *, main_file=(Path(__file__).parent / "microcode.asm").resolve(), field_defs=None, hex=None):
        self.main_file = main_file  # (Path(__file__).parent / "microcode.asm").resolve()  # noqa: E501
        self.field_defs = field_defs
        self.hex = hex
        self.ucode_contents = [0]*256
        self.adr = Signal(8)
        self.dat_r = Signal(32)

        self.assemble()
        super().__init__()

        self.ucode_mem = Memory(width=32, depth=256, init=self.ucode_contents)


    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.ucode_mem.read_port(transparent=False)

        m.d.comb += [
            rdport.addr.eq(self.adr),
            self.dat_r.eq(rdport.data),
            self.fields.as_value().eq(self.dat_r)
        ]

        return m

    # Like M5Meta.assemble(), but pass3 is more flexible and tailored to my
    # needs.
    def assemble(self):
        if isinstance(self.main_file, IOBase):
            self.m5meta = M5Meta(self.main_file, obj_base_fn = "microcode.asm")
            self.m5meta.src = M5Pre(self.main_file).read()
        else:
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
            self.create_field_layout(space)

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

    def create_field_layout(self, space):
        layout = dict()
        padding_id = 0

        c, n = tee(space.fields.items())
        next(n, None)
        for (curr_n, curr_f), (_, next_f) in zip_longest(c, n, fillvalue=(None, None)):
            if curr_f.enum:
                layout[curr_n] = pyenum.Enum(curr_n, curr_f.enum)
            else:
                layout[curr_n] = unsigned(curr_f.width)

            if next_f and curr_f.origin + curr_f.width != next_f.origin:
                layout[f"_padding_{padding_id}"] = unsigned(next_f.origin - (curr_f.origin + curr_f.width))

        self.field_layout = StructLayout(layout)
