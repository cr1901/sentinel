import pytest

from itertools import product
from sentinel.bench import stats, ScriptType
from sentinel.top import Top
from sentinel.alu import ALU
from sentinel.control import Control
from sentinel.decode import Decode
from sentinel.datapath import DataPath
from sentinel.ucoderom import UCodeROM
from tabulate import tabulate


class ALU32(ALU):
    def __init__(self):
        super().__init__(32)


scripts_and_modules = product((ScriptType.GENERIC, ScriptType.SYNTH,
                               ScriptType.ICE40, ScriptType.GOWIN,
                               ScriptType.XC7, ScriptType.CYCLONE5),
                              (UCodeROM, Control, Top, ALU32, Decode,
                               DataPath))


@pytest.mark.parametrize("script_type, mod", scripts_and_modules)
def test_resource_usage(capsys, script_type, mod):
    m = mod()
    st = stats(m, script_type)["design"]["num_cells_by_type"]

    with capsys.disabled():
        print("\n", str(type(m)), script_type)
        header = ["Cell Type", "Count"]
        print(tabulate(st.items(), headers=header, tablefmt="simple"))
