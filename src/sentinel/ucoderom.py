from io import IOBase
from pathlib import Path
from itertools import tee, zip_longest

from amaranth import unsigned, Memory, Module
from amaranth.lib.data import StructLayout
from amaranth.lib.wiring import Signature, In, Out, Component
from amaranth.utils import log2_int
from m5pre import M5Pre
from m5meta import M5Meta

from .ucodefields import OpType, CondTest, JmpType, PcAction, ASrc, BSrc, \
    SrcOp, ALUMod, RegSet, RegRSel, RegWSel


def ucoderom_signature(ucoderom):
    return Signature({
        "addr": Out(log2_int(ucoderom.ucode_mem.depth)),
        "fields": In(ucoderom.field_layout)
    })


class UCodeROM(Component):
    enum_map = {
        "alu_op": OpType,
        "cond_test": CondTest,
        "jmp_type": JmpType,
        "pc_action": PcAction,
        "src_op": SrcOp,
        "alu_mod": ALUMod,
        "a_src": ASrc,
        "b_src": BSrc,
        "reg_set": RegSet,
        "reg_r_sel": RegRSel,
        "reg_w_sel": RegWSel
    }

    @property
    def signature(self):
        return ucoderom_signature(self).flip()

    @staticmethod
    def main_microcode_file():
        return (Path(__file__).parent / "microcode.asm").resolve()

    def __init__(self, *, main_file=None, field_defs=None, hex=None):
        if not main_file:
            self.main_file = UCodeROM.main_microcode_file()
        else:
            self.main_file = main_file
        self.field_defs = field_defs
        self.hex = hex

        self.assemble()
        self.ucode_mem = Memory(width=self.width, depth=self.depth,
                                init=self.ucode_contents)
        super().__init__()

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = \
            self.ucode_mem.read_port(transparent=False)

        m.d.comb += [
            rdport.addr.eq(self.addr),
            self.fields.as_value().eq(rdport.data)
        ]

        return m

    # Like M5Meta.assemble(), but pass3 is more flexible and tailored to my
    # needs.
    def assemble(self):
        if isinstance(self.main_file, IOBase):
            self.m5meta = M5Meta(self.main_file, obj_base_fn="anonymous")
            self.m5meta.src = M5Pre(self.main_file).read()
        else:
            with open(self.main_file) as mfp:
                self.m5meta = M5Meta(mfp, obj_base_fn=self.main_file.stem)
                self.m5meta.src = M5Pre(mfp).read()

        passes = [None,
                  self.m5meta.pass12,
                  self.m5meta.pass12]

        for p in range(1, len(passes)):
            self.m5meta.pass_num = p
            passes[p]()

        if len(self.m5meta.spaces) != 1:
            raise ValueError("UCodeROM does not support multiple microcode address spaces")  # noqa: E501

        # pass3- Create enums and signals for amaranth code. Optionally
        # generate extra files for debugging.
        space = next(iter(self.m5meta.spaces.values()))
        # assert(space.name == "block_ram")
        space.generate_object()

        self.create_mem_init(space)
        self.create_field_layout(space)

        if self.hex:
            space.write_hex_file(self.hex)

        if self.field_defs:
            with open(self.field_defs, 'w') as f:
                space.write_fdef(f)

    def create_mem_init(self, space):
        self.width = space.width
        self.depth = space.size
        self.ucode_contents = [0]*self.depth

        # Pre-filled with zeros. Fill in addresses that m5meta claims to
        # contain data by converting the address to an int (a dictionary
        # is used to represent address space holes implicitly).
        for addr in sorted(space.data.keys()):
            self.ucode_contents[int(addr)] = space.data[addr]

    def create_field_layout(self, space):
        layout = dict()
        padding_id = 0

        c, n = tee(space.fields.items())
        next(n, None)
        curr_next_pairs = zip_longest(c, n, fillvalue=(None, None))

        for (curr_n, curr_f), (_, next_f) in curr_next_pairs:
            # bools in m5meta are internally enums, but we'll do just fine with
            # unsigned(1).
            if curr_f.enum and curr_f.enum != {"false": 0, "true": 1}:
                layout[curr_n] = self.check_and_convert_dynamic_enum(curr_f)
            else:
                layout[curr_n] = unsigned(curr_f.width)

            if next_f and curr_f.origin + curr_f.width != next_f.origin:
                layout[f"_padding_{padding_id}"] = \
                    unsigned(next_f.origin - (curr_f.origin + curr_f.width))

        self.field_layout = StructLayout(layout)

    def check_and_convert_dynamic_enum(self, field):
        try:
            se_class = self.enum_map[field.name]
        except KeyError as e:
            raise ValueError(f"{e.args[0]} was not in enum_map") from e

        if not (all(se_class[k.upper()].value == field.enum[k]
                    for k in field.enum) and
                all(field.enum[k.name.lower()] == k.value
                    for k in se_class)):
            raise ValueError(f"{se_class} in Amaranth source and field {field}"
                             " in microcode source do not have compatible "
                             "fields and values.\n"
                             "Amaranth is UPPER_CASE, microcode source is "
                             "lower_case.")

        return se_class
