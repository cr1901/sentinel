"""Microcode ROM assembly and Component."""

from io import IOBase
from pathlib import Path
from itertools import tee, zip_longest

from amaranth import Shape, unsigned, Module
from amaranth.lib.data import StructLayout
from amaranth.lib.memory import Memory
from amaranth.lib.wiring import In, Out, Component
from amaranth.utils import ceil_log2
from m5pre import M5Pre
from m5meta import M5Meta

from .ucodefields import Target, OpType, CondTest, JmpType, InvertTest, \
    PcAction, LatchA, LatchB, ASrc, BSrc, ALUIMod, ALUOMod, RegRead, \
    RegWrite, RegRSel, RegWSel, CSROp, CSRSel, MemReq, MemSel, MemExtend, \
    LatchAdr, LatchData, WriteMem, ExceptCtl, InsnFetch


class UCodeROM(Component):
    """Microcode ROM assembly and Component.

    :class:`UCodeROM` takes a microcode assembly file as input, parses
    the assembly file, and dynamically creates a
    :class:`~amaranth:amaranth.lib.wiring.Signature` which splits out all
    microcode fields.

    .. note::
        I have not personally tried using alternate microcodes. Because
        most of Sentinel uses :mod:`~sentinel.ucodefields` in some capacity, I
        generally expect that alternate microcodes will simply be extensions
        to the main microcode file.

        This can be done, for instance, by copying and extending *both*
        ``microcode.asm`` and the default :attr:`field_map`. I may optimize
        the API for this extension use case after I get a better idea of how
        to support different Sentinel microcodes/profiles.

    Parameters
    ----------
    main_file: Path, optional
        Path to microcode file to assemble into ROM. If not supplied, use
        :func:`main_microcode_file`.
    field_defs: Path, optional
        Path to write field definitions extracted from assembly file.
    hex: Path, optional
        Path to write contents of microcode ROM in hex output.
    field_map: dict, optional
        Alternate :attr:`field_map` to use to generate a
        :class:`~amaranth:amaranth.lib.wiring.Signature`. By default, use a
        :attr:`field_map` corresponding to :func:`main_microcode_file`.

    Attributes
    ----------
    field_map: dict
        Map of strings to :class:`~amaranth.hdl.ShapeLike`, which are
        verified against the ``fields`` supplied microcode assembly file.

        Each :class:`~amaranth:amaranth.lib.enum.Enum` class should have
        values in ``UPPER_CASE`` corresponding to an equivalent
        `m5meta <https://github.com/brouhaha/m5meta>`_ ``enum`` whose values
        are `lower_case`.
    addr : Out(ceil_log2(self.depth))
        Address bus. Width is determined by microcode assembly file, which
        also initializes the otherwise-private self.depth.

        The default microcode file has an address space depth of 256
        (1 byte).
    fields : In(StructLayout)
        Microcode field data output.
        :class:`~amaranth:amaranth.lib.data.StructLayout` is determined by
        microcode assembly file. A default :attr:`fields` layout will look
        like this:

        .. todo::
            Doctest printing default microcode ``StructLayout`` goes here.

        The default microcode file has a data width of 48 bits (6 bytes).
    """

    field_map = {
        "target": Target,
        "alu_op": OpType,
        "cond_test": CondTest,
        "jmp_type": JmpType,
        "invert_test": InvertTest,
        "pc_action": PcAction,
        "latch_a": LatchA,
        "latch_b": LatchB,
        "alu_i_mod": ALUIMod,
        "alu_o_mod": ALUOMod,
        "reg_read": RegRead,
        "reg_write": RegWrite,
        "a_src": ASrc,
        "b_src": BSrc,
        "reg_r_sel": RegRSel,
        "reg_w_sel": RegWSel,
        "csr_op": CSROp,
        "csr_sel": CSRSel,
        "mem_req": MemReq,
        "mem_sel": MemSel,
        "mem_extend": MemExtend,
        "latch_adr": LatchAdr,
        "latch_data": LatchData,
        "write_mem": WriteMem,
        "except_ctl": ExceptCtl,
        "insn_fetch": InsnFetch
    }

    @staticmethod
    def main_microcode_file():
        """Return the default microcode file path.

        The default microcode, titled ``microcode.asm``, is supplied with
        Sentinel's source code/package in the same directory as this file.

        Returns
        -------
        ~pathlib.Path
            Absolute path to microcode file supplied with Sentinel.
        """
        return (Path(__file__).parent / "microcode.asm").resolve()

    def __init__(self, *, main_file=None, field_defs=None, hex=None,
                 field_map=None):
        if not main_file:
            self.main_file = UCodeROM.main_microcode_file()
        else:
            self.main_file = main_file
        self.field_defs = field_defs
        self.hex = hex

        if field_map:
            self.field_map = field_map

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
        ``field_map``.

        Raises
        ------
        ValueError
            If the assembly file uses multiple address spaces or its
            ``enum``\ s cannot be mapped to :attr:`field_map`.
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
                layout[curr_n] = \
                    self._check_and_convert_dynamic_shape(curr_f)

            if next_f and curr_f.origin + curr_f.width != next_f.origin:
                layout[f"_padding_{padding_id}"] = \
                    unsigned(next_f.origin - (curr_f.origin + curr_f.width))

        self.field_layout = StructLayout(layout)

    def _check_and_convert_dynamic_shape(self, field):
        try:
            ss_class = self.field_map[field.name]
        except KeyError as e:
            raise ValueError(f"{e.args[0]} was not in field_map") from e

        ss_width = Shape.cast(ss_class).width
        f_width = field.width
        if ss_width != f_width:
            raise ValueError(f"{ss_class} in Amaranth source and field {field}"
                             " in microcode source do not have compatible "
                             "widths.\n"
                             f"Amaranth source width is {ss_width}, microcode "
                             f"source width is {f_width}.")

        return ss_class

    def _check_and_convert_dynamic_enum(self, field):
        try:
            se_class = self.field_map[field.name]
        except KeyError as e:
            raise ValueError(f"{e.args[0]} was not in field_map") from e

        if not (all(se_class[k.upper()].value == field.enum[k]
                    for k in field.enum) and
                all(field.enum[k.name.lower()] == k.value
                    for k in se_class)):
            raise ValueError(f"{se_class} in Amaranth source and field {field}"
                             " in microcode source do not have compatible "
                             "fields and values.\n"
                             "Amaranth is UPPER_CASE, microcode source is "
                             "lower_case.")

        se_width = Shape.cast(se_class).width
        f_width = field.width
        if se_width != f_width:
            raise ValueError(f"{se_class} in Amaranth source and field {field}"
                             " in microcode source do not have compatible "
                             "widths.\n"
                             f"Amaranth source width is {se_width}, microcode "
                             f"source width is {f_width}.")

        return se_class
