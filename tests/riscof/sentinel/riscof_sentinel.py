import os
import logging
from pathlib import Path
from sentinel.top import Top
from amaranth.sim import Simulator, Passive
from enum import Enum, auto

import riscof.utils as utils
from riscof.pluginTemplate import pluginTemplate

import sys

# FIXME: This is unfortunate... but we need some code from the tests :(...
this_dir = Path(os.path.realpath(__file__)).parent
sentinel_root_dir = this_dir.parent.parent.parent
sys.path.insert(0, str(sentinel_root_dir))

from tests.conftest import Memory, mproc_inner  # noqa: E402
from tests.upstream.test_upstream import wfhw_inner  # noqa: E402

logger = logging.getLogger()


def mk_wait_for_host_write(top, sig_file, memory):
    async def wait_for_host_write(ctx):
        val = await wfhw_inner(top, ctx)
        begin_sig = val & 0xffffffff
        end_sig = (val >> 32) & 0xffffffff

        # I don't feel like doing alignment so convert the 32-bit memory
        # list into bytes and index on a byte-basis.
        bin_ = b"".join(b.to_bytes(4, 'little') for b in memory)

        # The end state of the simulation is to print out the locations
        # of the beginning and ending signatures. They can then
        # immediately be inserted into a file.
        with open(sig_file, "w") as fp:
            for i in range(begin_sig, end_sig, 4):
                dat = 0
                dat |= bin_[i]
                dat |= bin_[i + 1] << 8
                dat |= bin_[i + 2] << 16
                dat |= bin_[i + 3] << 24
                fp.write(f"{dat:08x}\n")

    return wait_for_host_write


def mk_read_write_mem(top, memory):
    async def read_write_mem(ctx):
        await mproc_inner(top, ctx, memory)

    return read_write_mem


class sentinel(pluginTemplate):
    __model__ = "sentinel"

    __version__ = "0.1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        config = kwargs.get('config')

        # If the config node for this DUT is missing or empty. Raise an error.
        # At minimum we need the paths to the ispec and pspec files
        if config is None:
            print("Please enter input file paths in configuration.")
            raise SystemExit(1)

        # In case of an RTL based DUT, this would be point to the final binary
        # executable of your test-bench produced by a simulator (like
        # verilator, vcs, incisive, etc). In case of an iss or emulator, this
        # variable could point to where the iss binary is located. If 'PATH
        # variable is missing in the config.ini we can hardcode the alternate
        # here.
        self.dut_exe = os.path.join(config['PATH'] if 'PATH' in config else "",
                                    "sentinel")

        # Number of parallel jobs that can be spawned off by RISCOF for various
        # actions performed in later functions, specifically to run the tests
        # in parallel on the DUT executable. Can also be used in the build
        # function if required.
        self.num_jobs = str(config['jobs'] if 'jobs' in config else 1)

        # Path to the directory where this python file is located. Collect it
        # from the config.ini
        self.pluginpath = os.path.abspath(config['pluginpath'])

        # Collect the paths to the  riscv-config absed ISA and platform yaml
        # files. One can choose to hardcode these here itself instead of
        # picking it from the config.ini file.
        self.isa_spec = os.path.abspath(config['ispec'])
        self.platform_spec = os.path.abspath(config['pspec'])

        # We capture if the user would like the run the tests on the target or
        # not. If you are interested in just compiling the tests and not
        # running them on the target, then following variable should be set to
        # False
        if 'target_run' in config and config['target_run'] == '0':
            self.target_run = False
        else:
            self.target_run = True

    def initialise(self, suite, work_dir, archtest_env):

        # capture the working directory. Any artifacts that the DUT creates
        # should be placed in this directory. Other artifacts from the
        # framework and the Reference plugin will also be placed here itself.
        self.work_dir = work_dir

        # capture the architectural test-suite directory.
        self.suite_dir = suite

        # Note the march is not hardwired here, because it will change for each
        # test. Similarly the output elf name and compile macros will be
        # assigned later in the runTests function
        self.compile_cmd = 'riscv64-unknown-elf-gcc -march={0} \
        -static -mcmodel=medany -fvisibility=hidden -nostdlib -nostartfiles -g\
        -T '+self.pluginpath+'/env/link.ld\
        -I '+self.pluginpath+'/env/\
        -I ' + archtest_env + ' {1} -o {2} {3}'

        # add more utility snippets here

    def build(self, isa_yaml, platform_yaml):

        # load the isa yaml as a dictionary in python.
        ispec = utils.load_yaml(isa_yaml)['hart0']

        # capture the XLEN value by picking the max value in 'supported_xlen'
        # field of isa yaml. This will be useful in setting integer value in
        # the compiler string (if not already hardcoded);
        self.xlen = ('64' if 64 in ispec['supported_xlen'] else '32')

        # for sentinel start building the '--isa' argument. the self.isa is
        # dutname specific and may not be useful for all DUTs
        self.isa = 'rv' + self.xlen
        if "I" in ispec["ISA"]:
            self.isa += 'i'
        if "M" in ispec["ISA"]:
            self.isa += 'm'
        if "F" in ispec["ISA"]:
            self.isa += 'f'
        if "D" in ispec["ISA"]:
            self.isa += 'd'
        if "C" in ispec["ISA"]:
            self.isa += 'c'

        # TODO: The following assumes you are using the riscv-gcc toolchain. If
        #       not please change appropriately
        self.compile_cmd = self.compile_cmd+' -mabi=' + \
            ('lp64 ' if 64 in ispec['supported_xlen'] else 'ilp32 ')

    # Sentinel elects to use the alternate template to avoid a dependency on
    # make.
    def runTests(self, testList):
        # we will iterate over each entry in the testList. Each entry node will
        # be referred to by the variable testname.
        for testname in testList:
            top = Top()

            logger.debug('Running Test: {0} on DUT'.format(testname))
            # for each testname we get all its fields (as described by the
            # testList format)
            testentry = testList[testname]

            # we capture the path to the assembly file of this test
            test = Path(testentry['test_path'])

            # capture the directory where the artifacts of this test will be
            # dumped/created.
            test_dir = Path(testentry['work_dir'])

            # name of the elf file after compilation of the test
            elf = Path(test.stem).with_suffix(".elf")

            # name of the signature file as per requirement of RISCOF. RISCOF
            # expects the signature to be named as DUT-<dut-name>.signature.
            # The below variable creates an absolute path of signature file.
            sig_file = os.path.join(test_dir, self.name[:-1] + ".signature")

            # for each test there are specific compile macros that need to be
            # enabled. The macros in the testList node only contain the
            # macros/values. For the gcc toolchain we need to prefix with "-D".
            # The following does precisely that.
            compile_macros = ' -D' + " -D".join(testentry['macros'])

            # collect the march string required for the compiler
            marchstr = testentry['isa'].lower()

            # substitute all variables in the compile command that we created
            # in the initialize function
            cmd = self.compile_cmd.format(marchstr, test, elf, compile_macros)

            # just a simple logger statement that shows up on the terminal
            logger.debug('Compiling test: ' + str(test))

            # the following command spawns a process to run the compile
            # command. Note here, we are changing the directory for this
            # command to that pointed by test_dir. If you would like the
            # artifacts to be dumped else where change the test_dir variable
            # to the path of your choice.
            utils.shellCommand(cmd).run(cwd=test_dir)

            bin = Path(elf.stem).with_suffix(".bin")
            objcopy_run = f'riscv64-unknown-elf-objcopy -O binary {elf} {bin}'
            utils.shellCommand(objcopy_run).run(cwd=test_dir)

            objdump_run = f'riscv64-unknown-elf-objdump -D {elf} > {test.stem}.disass;'  # noqa: E501
            utils.shellCommand(objdump_run).run(cwd=test_dir)

            # for debug purposes if you would like stop the DUT plugin after
            # compilation, you can comment out the lines below and raise a
            # SystemExit
            if self.target_run:
                # TODO: Convert into SoC module (use wishbone.Decoder and
                # friends)?
                with open(test_dir / bin, "rb") as fp:
                    bin_ = bytearray(fp.read())

                mem = Memory(start=0, size=len(bin_))

                for adr in range(0, len(bin_) // 4):
                    mem[adr] = int.from_bytes(bin_[4 * adr:4 * adr + 4],
                                            byteorder="little")

                logger.debug("Executing in Amaranth simulator")
                sim = Simulator(top)
                sim.add_clock(1/(12e6))
                sim.add_testbench(mk_wait_for_host_write(top, sig_file, mem))
                sim.add_process(mk_read_write_mem(top, mem))

                vcd = test_dir / Path(test.stem).with_suffix(".vcd")
                gtkw = test_dir / Path(test.stem).with_suffix(".gtkw")
                with sim.write_vcd(vcd_file=str(vcd),
                                   gtkw_file=str(gtkw)):
                    sim.run()

            # post-processing steps can be added here in the template below
            # postprocess = 'mv {0} temp.sig'.format(sig_file)'
            # utils.shellCommand(postprocess).run(cwd=test_dir)

        # if target runs are not required then we simply exit as this point
        # after running all the makefile targets.
        if not self.target_run:
            raise SystemExit
