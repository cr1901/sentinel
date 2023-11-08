import os
import re
import shutil
import subprocess
import shlex
import logging
import random
import string
from string import Template
import sys
from pathlib import Path
from sentinel.top import Top
from amaranth.sim import Simulator, Passive
from enum import Enum, auto


import riscof.utils as utils
import riscof.constants as constants
from riscof.pluginTemplate import pluginTemplate

logger = logging.getLogger()

class sentinel(pluginTemplate):
    __model__ = "sentinel"

    __version__ = "0.1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        config = kwargs.get('config')

        # If the config node for this DUT is missing or empty. Raise an error. At minimum we need
        # the paths to the ispec and pspec files
        if config is None:
            print("Please enter input file paths in configuration.")
            raise SystemExit(1)

        # In case of an RTL based DUT, this would be point to the final binary executable of your
        # test-bench produced by a simulator (like verilator, vcs, incisive, etc). In case of an iss or
        # emulator, this variable could point to where the iss binary is located. If 'PATH variable
        # is missing in the config.ini we can hardcode the alternate here.
        self.dut_exe = os.path.join(config['PATH'] if 'PATH' in config else "","sentinel")

        # Number of parallel jobs that can be spawned off by RISCOF
        # for various actions performed in later functions, specifically to run the tests in
        # parallel on the DUT executable. Can also be used in the build function if required.
        self.num_jobs = str(config['jobs'] if 'jobs' in config else 1)

        # Path to the directory where this python file is located. Collect it from the config.ini
        self.pluginpath=os.path.abspath(config['pluginpath'])

        # Collect the paths to the  riscv-config absed ISA and platform yaml files. One can choose
        # to hardcode these here itself instead of picking it from the config.ini file.
        self.isa_spec = os.path.abspath(config['ispec'])
        self.platform_spec = os.path.abspath(config['pspec'])

        #We capture if the user would like the run the tests on the target or
        #not. If you are interested in just compiling the tests and not running
        #them on the target, then following variable should be set to False
        if 'target_run' in config and config['target_run']=='0':
            self.target_run = False
        else:
            self.target_run = True

    def initialise(self, suite, work_dir, archtest_env):

       # capture the working directory. Any artifacts that the DUT creates should be placed in this
       # directory. Other artifacts from the framework and the Reference plugin will also be placed
       # here itself.
       self.work_dir = work_dir

       # capture the architectural test-suite directory.
       self.suite_dir = suite

       # Note the march is not hardwired here, because it will change for each
       # test. Similarly the output elf name and compile macros will be assigned later in the
       # runTests function
       self.compile_cmd = 'riscv64-unknown-elf-gcc -march={0} \
         -static -mcmodel=medany -fvisibility=hidden -nostdlib -nostartfiles -g\
         -T '+self.pluginpath+'/env/link.ld\
         -I '+self.pluginpath+'/env/\
         -I ' + archtest_env + ' {1} -o {2} {3}'

       # add more utility snippets here

    def build(self, isa_yaml, platform_yaml):

      # load the isa yaml as a dictionary in python.
      ispec = utils.load_yaml(isa_yaml)['hart0']

      # capture the XLEN value by picking the max value in 'supported_xlen' field of isa yaml. This
      # will be useful in setting integer value in the compiler string (if not already hardcoded);
      self.xlen = ('64' if 64 in ispec['supported_xlen'] else '32')

      # for sentinel start building the '--isa' argument. the self.isa is dutnmae specific and may not be
      # useful for all DUTs
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

      #TODO: The following assumes you are using the riscv-gcc toolchain. If
      #      not please change appropriately
      self.compile_cmd = self.compile_cmd+' -mabi='+('lp64 ' if 64 in ispec['supported_xlen'] else 'ilp32 ')

#The following is an alternate template that can be used instead of the above.
#The following template only uses shell commands to compile and run the tests.

    def runTests(self, testList):

      # we will iterate over each entry in the testList. Each entry node will be referred to by the
      # variable testname.
      for testname in testList:
          top = Top()

          logger.debug('Running Test: {0} on DUT'.format(testname))
          # for each testname we get all its fields (as described by the testList format)
          testentry = testList[testname]

          # we capture the path to the assembly file of this test
          test = Path(testentry['test_path'])

          # capture the directory where the artifacts of this test will be dumped/created.
          test_dir = Path(testentry['work_dir'])

          # name of the elf file after compilation of the test
          elf = Path(test.stem).with_suffix(".elf")

          # name of the signature file as per requirement of RISCOF. RISCOF expects the signature to
          # be named as DUT-<dut-name>.signature. The below variable creates an absolute path of
          # signature file.
          sig_file = os.path.join(test_dir, self.name[:-1] + ".signature")

          # for each test there are specific compile macros that need to be enabled. The macros in
          # the testList node only contain the macros/values. For the gcc toolchain we need to
          # prefix with "-D". The following does precisely that.
          compile_macros= ' -D' + " -D".join(testentry['macros'])

          # collect the march string required for the compiler
          marchstr = testentry['isa'].lower()

          # substitute all variables in the compile command that we created in the initialize
          # function
          cmd = self.compile_cmd.format(marchstr, test, elf, compile_macros)

          # just a simple logger statement that shows up on the terminal
          logger.debug('Compiling test: ' + str(test))

          # the following command spawns a process to run the compile command. Note here, we are
          # changing the directory for this command to that pointed by test_dir. If you would like
          # the artifacts to be dumped else where change the test_dir variable to the path of your
          # choice.
          utils.shellCommand(cmd).run(cwd=test_dir)

          bin = Path(elf.stem).with_suffix(".bin")
          objcopy_run = f'riscv64-unknown-elf-objcopy -O binary {elf} {bin}'
          utils.shellCommand(objcopy_run).run(cwd=test_dir)

          objdump_run = f'riscv64-unknown-elf-objdump -D {elf} > {test.stem}.disass;'
          utils.shellCommand(objdump_run).run(cwd=test_dir)

          # for debug purposes if you would like stop the DUT plugin after compilation, you can
          # comment out the lines below and raise a SystemExit
          if self.target_run:
            # TODO: Convert into SoC module (use wishbone.Decoder and friends)?
            with open(test_dir / bin, "rb") as fp:
                bin_ = bytearray(fp.read())

            class HOST_STATE(Enum):
                WAITING_FIRST = auto()
                FIRST_ACCESS_ACK = auto()
                WAITING_SECOND = auto()
                SECOND_ACCESS_ACK = auto()
                DONE = auto()
                TIMEOUT = auto()

            def wait_for_host_write():
                i = 0
                state = HOST_STATE.WAITING_FIRST

                while True:
                    match state:
                        case HOST_STATE.WAITING_FIRST:
                            if ((yield top.bus.adr) == 0x4000000 >> 2) and \
                                    (yield top.bus.sel == 0b1111) and \
                                    (yield top.bus.cyc) and (yield top.bus.stb):
                                # yield top.bus.ack.eq(1)
                                state = HOST_STATE.FIRST_ACCESS_ACK
                        case HOST_STATE.FIRST_ACCESS_ACK:
                            begin_sig = (yield top.bus.dat_w)
                            # yield top.bus.ack.eq(0)
                            state = HOST_STATE.WAITING_SECOND
                        case HOST_STATE.WAITING_SECOND:
                            if (yield top.bus.adr) == ((0x4000000 + 4) >> 2) and \
                                    (yield top.bus.sel == 0b1111) and \
                                    (yield top.bus.cyc) and (yield top.bus.stb):
                                # yield top.bus.ack.eq(1)
                                state = HOST_STATE.SECOND_ACCESS_ACK
                        case HOST_STATE.SECOND_ACCESS_ACK:
                            end_sig = (yield top.bus.dat_w)
                            # yield top.bus.ack.eq(0)
                            state = HOST_STATE.DONE
                        case HOST_STATE.DONE:
                            break
                        case HOST_STATE.TIMEOUT:
                            raise AssertionError("CPU (but not microcode) probably "
                                                "stuck in infinite loop")

                    yield
                    i += 1
                    if i > 65535:
                        state = HOST_STATE.TIMEOUT

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

            def read_write_mem():
                yield Passive()

                ios = (0x4000000 >> 2, 0x4000000 + 4 >> 2)
                while True:
                    yield top.bus.dat_r.eq(0)
                    yield top.bus.ack.eq(0)

                    if ((yield top.bus.cyc) and (yield top.bus.stb)):
                        if not (yield top.bus.ack):
                            yield top.bus.ack.eq(1)

                        if ((yield top.bus.we) and (yield top.bus.ack) and
                           ((yield top.bus.adr) not in ios)):
                            data_word = (yield top.bus.dat_w)
                            sel = (yield top.bus.sel)
                            word_adr = (yield top.bus.adr) << 2

                            if sel & 0b0001:
                                bin_[word_adr] = data_word & 0xff
                            if sel & 0b0010:
                                bin_[word_adr + 1] = (data_word >> 8) & 0xff
                            if sel & 0b0100:
                                bin_[word_adr + 2] = (data_word >> 16) & 0xff
                            if sel & 0b1000:
                                bin_[word_adr + 3] = (data_word >> 24) & 0xff

                        elif ((not (yield top.bus.ack)) and
                             ((yield top.bus.adr) not in ios)):
                            data_word = 0
                            sel = (yield top.bus.sel)
                            word_adr = (yield top.bus.adr) << 2

                            if sel & 0b0001:
                                data_word |= bin_[word_adr]
                            if sel & 0b0010:
                                data_word |= bin_[word_adr + 1] << 8
                            if sel & 0b0100:
                                data_word |= bin_[word_adr + 2] << 16
                            if sel & 0b1000:
                                data_word |= bin_[word_adr + 3] << 24

                            yield top.bus.dat_r.eq(data_word)
                    yield

            logger.debug("Executing in Amaranth simulator")
            sim = Simulator(top)
            sim.add_clock(1/(12e6))
            sim.add_sync_process(wait_for_host_write)
            sim.add_sync_process(read_write_mem)

            vcd = test_dir / Path(test.stem).with_suffix(".vcd")
            gtkw = test_dir / Path(test.stem).with_suffix(".gtkw")
            with sim.write_vcd(vcd_file=str(vcd),
                               gtkw_file=str(gtkw)):
                sim.run()

          # post-processing steps can be added here in the template below
          #postprocess = 'mv {0} temp.sig'.format(sig_file)'
          #utils.shellCommand(postprocess).run(cwd=test_dir)

      # if target runs are not required then we simply exit as this point after running all
      # the makefile targets.
      if not self.target_run:
          raise SystemExit
