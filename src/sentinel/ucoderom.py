"""Microcode ROM assembly and Component."""

from io import IOBase
from pathlib import Path
from itertools import tee, zip_longest

from amaranth import unsigned, Module
from amaranth.lib.data import StructLayout
from amaranth.lib.memory import Memory
from amaranth.lib.wiring import In, Out, Component
from amaranth.utils import ceil_log2
from m5pre import M5Pre
from m5meta import M5Meta

from .ucodefields import OpType, CondTest, JmpType, PcAction, ASrc, BSrc, \
    ALUIMod, ALUOMod, RegRSel, RegWSel, MemSel, MemExtend, ExceptCtl, \
    CSROp, CSRSel


class UCodeROM(Component):
    """Microcode ROM assembly and Component.

    :class:`UCodeROM` takes a microcode assembly file as input, parses
    the assembly file, and dynamically creates a
    :class:`~amaranth:amaranth.lib.wiring.Signature` which splits out all
    microcode fields.

    Parameters
    ----------
    main_file: Path, optional
        Path to microcode file to assemble into ROM. If not supplied, use
        :func:`main_microcode_file`.
    field_defs: Path, optional
        Path to write field definitions extracted from assembly file.
    hex: Path, optional
        Path to write contents of microcode ROM in hex output.
    enum_map: dict, optional
        Alternate :attr:`enum_map` to use to generate a
        :class:`~amaranth:amaranth.lib.wiring.Signature`. By default, use an
        :attr:`enum_map` corresponding to :func:`main_microcode_file`.

    Attributes
    ----------
    enum_map: dict
        Map of strings to :class:`~amaranth:amaranth.lib.enum.Enum`, which are
        verified against the supplied microcode assembly file.

        Each :class:`~amaranth:amaranth.lib.enum.Enum` class should have
        values in ``UPPER_CASE`` corresponding to an equivalent
        `m5meta <https://github.com/brouhaha/m5meta>`_ ``enum`` whose values
        are `lower_case`.
    addr : Out(ceil_log2(self.depth))
        Address bus. Width is determined by microcode assembly file.
    fields : In(StructLayout)
        Microcode field data output.
        :class:`~amaranth:amaranth.lib.data.StructLayout` is determined by
        microcode assembly file.
    """

    enum_map = {
        "alu_op": OpType,
        "cond_test": CondTest,
        "jmp_type": JmpType,
        "pc_action": PcAction,
        "alu_i_mod": ALUIMod,
        "alu_o_mod": ALUOMod,
        "a_src": ASrc,
        "b_src": BSrc,
        "reg_r_sel": RegRSel,
        "reg_w_sel": RegWSel,
        "csr_op": CSROp,
        "csr_sel": CSRSel,
        "mem_sel": MemSel,
        "mem_extend": MemExtend,
        "except_ctl": ExceptCtl
    }

    @staticmethod
    def main_microcode_file():
        """Return the default microcode file path.

        The default microcode is supplied with Sentinel's source code.

        Returns
        -------
        ~pathlib.Path
            Absolute path to microcode file supplied with Sentinel.
        """
        return (Path(__file__).parent / "microcode.asm").resolve()

    def __init__(self, *, main_file=None, field_defs=None, hex=None,
                 enum_map=None):
        if not main_file:
            self.main_file = UCodeROM.main_microcode_file()
        else:
            self.main_file = main_file
        self.field_defs = field_defs
        self.hex = hex

        if enum_map:
            self.enum_map = enum_map

        self.assemble()
        self.ucode_mem = Memory(shape=self.width, depth=self.depth,
                                init=self.ucode_contents)
        super().__init__({
            "addr": Out(ceil_log2(self.depth)),
            "fields": In(self.field_layout)
        })

    def elaborate(self, platform):  # noqa: D102
        m = Module()
        m.submodules.ucode_mem = self.ucode_mem

        r_port = self.ucode_mem.read_port()

        m.d.comb += [
            r_port.addr.eq(self.addr),
            self.fields.as_value().eq(r_port.data)
        ]

        return m

    # Like M5Meta.assemble(), but pass3 is more flexible and tailored to my
    # needs.
    def assemble(self):
        r"""Verify and assemble the associated microcode source file.

        Internally calls `m5meta's <https://github.com/brouhaha/m5meta>`_
        ``assemble`` function and verifies that the assembly file matches
        ``enum_map``.

        Raises
        ------
        ValueError
            If the assembly file uses multiple address spaces or its ``enum``\s
            cannot be mapped to ``enum_map``.
        """
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

        self._create_mem_init(space)
        self._create_field_layout(space)

        if self.hex:
            space.write_hex_file(self.hex)

        if self.field_defs:
            with open(self.field_defs, 'w') as f:
                space.write_fdef(f)

    def _create_mem_init(self, space):
        self.width = space.width
        self.depth = space.size
        self.ucode_contents = [0] * self.depth

        # Pre-filled with zeros. Fill in addresses that m5meta claims to
        # contain data by converting the address to an int (a dictionary
        # is used to represent address space holes implicitly).
        for addr in sorted(space.data.keys()):
            self.ucode_contents[int(addr)] = space.data[addr]

    def _create_field_layout(self, space):
        layout = dict()
        padding_id = 0

        c, n = tee(space.fields.items())
        next(n, None)
        curr_next_pairs = zip_longest(c, n, fillvalue=(None, None))

        for (curr_n, curr_f), (_, next_f) in curr_next_pairs:
            # bools in m5meta are internally enums, but we'll do just fine with
            # unsigned(1).
            if curr_f.enum and curr_f.enum != {"false": 0, "true": 1}:
                layout[curr_n] = self._check_and_convert_dynamic_enum(curr_f)
            else:
                layout[curr_n] = unsigned(curr_f.width)

            if next_f and curr_f.origin + curr_f.width != next_f.origin:
                layout[f"_padding_{padding_id}"] = \
                    unsigned(next_f.origin - (curr_f.origin + curr_f.width))

        self.field_layout = StructLayout(layout)

    def _check_and_convert_dynamic_enum(self, field):
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
