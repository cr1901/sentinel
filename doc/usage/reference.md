# User Reference

The [Quickstart](./quickstart.md) is a good reference for how to use Sentinel
from the source repo. These next three sections discuss usage outside of the
source tree.

(pre-generated)=
## Pre-Generated Verilog

### From Releases

Each [Github Release](https://github.com/cr1901/sentinel/releases) contains a
standalone generated Verilog file of Sentinel CPU. If you opt to download the
Verilog from releases, **you do not need Python installed to use Sentinel**.
You can automate downloading the Verilog with a script like this:

````{tab} sh
```sh
SENTINEL_VER=__SENT_LATEST_TAG_IN_CODEBLOCK__

wget -O sentinel-v-$SENTINEL_VER.zip https://github.com/cr1901/sentinel/releases/download/$SENTINEL_VER/sentinel-v-$SENTINEL_VER.zip
unzip sentinel-v-$SENTINEL_VER.zip
```
````

````{tab} Powershell
```powershell
set SentinelVer __SENT_LATEST_TAG_IN_CODEBLOCK__

wget -OutFile sentinel-v-$SentinelVer.zip https://github.com/cr1901/sentinel/releases/download/$SentinelVer/sentinel-v-$SentinelVer.zip
Expand-Archive -Path sentinel-v-$SentinelVer.zip -DestinationPath .
```
````

(arbitrary)=
### From Arbitrary Commits

Generating Verilog of development versions- or any commit without a release-
requires a bit of extra setup. However, it still has the advantage of not
needing to (directly) interact with a source checkout if all you want is 
some Verilog. To generate the Verilog, you can use a script similar to this,
substituting `refs/heads/next.zip` with any desired branch (`refs/heads/$BRANCH.zip`),
tag (`refs/tags/$TAG.zip`), or commit (`$COMMIT.zip`):

```python
"""Create a script for generating Sentinel Verilog."""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#    "sentinel @ https://github.com/cr1901/sentinel/archive/refs/heads/next.zip",
#    "amaranth[builtin-yosys]>=0.5.8",
# ]
# ///

import sentinel.gen

if __name__ == "__main__":
    sentinel.gen._main()
```

<!-- Keep in sync with imports above! -->

```{testcode}
:hide:

import sys
from unittest.mock import patch

import sentinel.gen

with patch.object(sys, 'argv', sys.argv[0:1] + ["--help"]):
    sentinel.gen._main()
```

```{testoutput}
:hide:

Traceback (most recent call last):
...
SystemExit: 0
```

The above Python script is meant to be run using a tool that understands
[inline script metadata](https://peps.python.org/pep-0723/), such `pipx`, `pdm`,
`hatch`, or `uv`. If you don't have any of these tools installed, see the
"Python-only" tab. Assuming you saved the above script as a file called
`download-sentinel.py`, you can generate Verilog with the sequence of commands:

* First, regardless of which tool you have, you need to set an environment
  variable, due to [how the source code is built](https://backend.pdm-project.org/metadata/#read-from-scm-tag-supporting-git-and-hg):

  ````{tab} sh
  ```sh
  export PDM_BUILD_SCM_VERSION=__SENT_CURRENT_VERSION_IN_CODEBLOCK__
  ```
  ````
  
  ````{tab} Powershell
  ```powershell
  $env:PDM_BUILD_SCM_VERSION='__SENT_CURRENT_VERSION_IN_CODEBLOCK__'
  ```
  ````

* Then, you can run `download-sentinel.py` to generate Verilog:

  ````{tab} pipx
  ```sh
  pipx run download-sentinel.py -o sentinel.v
  ```
  ````
  
  ````{tab} pdm
  ```sh
  pdm run download-sentinel.py -o sentinel.v
  ```
  ````
  
  ````{tab} hatch
  ```sh
  hatch run download-sentinel.py -o sentinel.v
  ```
  ````
  
  ````{tab} uv
  ```sh
  uvx download-sentinel.py -o sentinel.v
  ```
  ````
  
  `````{tab} Python-only
  You can invoke `python` to run `pipx` [without installing](https://pipx.pypa.io/stable/installation/#using-pipx-without-installing-via-zipapp).
  First, ensure that you've downloaded `pipx.pyz`:
  
  ````{tab} sh
  ```sh
  PIPX_VER=1.8.0
  
  wget -O pipx.pyz https://github.com/pypa/pipx/releases/download/$PIPX_VER/pipx.pyz
  ```
  ````
  
  ````{tab} Powershell
  ```powershell
  set PipXVer 1.8.0
  
  wget -OutFile pipx.pyz https://github.com/pypa/pipx/releases/$PipXVer/pipx.pyz
  ```
  ````
  
  Then run:
  
  ```
  python pipx.pyz run download-sentinel.py -o sentinel.v
  ```
  `````

`````{tip}
The `download-sentinel.py` script takes arguments to customize generation! You
can get help by using:

````{tab} pipx
```sh
pipx run download-sentinel.py --help
```
````

````{tab} pdm
```sh
pdm run download-sentinel.py --help
```
````

````{tab} hatch
```sh
hatch run download-sentinel.py --help
```
````

````{tab} uv
```sh
uvx download-sentinel.py --help
```
````

````{tab} Python-only
```sh
python pipx.pyz run download-sentinel.py --help
```
````
`````


<!-- ```{tip}
The above script could possibly be represented as a Heredoc parameterized on
`next` to dynamically choose which version of the Sentinel source code is
checked out!
``` -->

## Generating Verilog From An Installed Package/As A Dependency

If using Sentinel as an installed package in another project, the
[Quickstart](./quickstart.md#generate-a-verilog-core) still applies,
except the command is now:

```
[pdm run] python -m sentinel.gen
```

If you're using `pdm` to handle Python dependencies in e.g. a mixed Python/Verilog
project, and Sentinel is a one of those Python dependencies, you may wish
to use [scripts](https://pdm-project.org/latest/usage/scripts/#pdm-scripts) to
provide a shortcut for Verilog generation in your `pyproject.toml`
(_`call = "python -m sentinel.gen"` does not work!_):

```toml
[tool.pdm.scripts]
gen = { call = "sentinel.gen:generate", help="generate Sentinel Verilog file" }
```

## Use In Amaranth Code

Right now, even from Python, Sentinel consists of rather few tunable knobs.
The only public Sentinel CPU module is the appropriately-named
{py:class}`~sentinel.top.Top`.

`Top` is an [interface object](https://amaranth-lang.org/rfcs/0002-interfaces.html#interface-definition-library-rfc)
whose {py:class}`~amaranth.lib.wiring.Signature` consists of a [Wishbone](https://cdn.opencores.org/downloads/wbspec_b4.pdf)
Classic bus and an Interrupt ReQuest (IRQ) line. All interface members are
synchronous to the `sync` [clock domain](https://amaranth-lang.org/docs/amaranth/latest/guide.html#control-domains).
Explicit `clk` and `rst` lines are generated for the `sync` domain in generated
Verilog code.

I expect most users to only need to `import` from `sentinel.top` to create
their SoC:

```{testcode}
from amaranth import Elaboratable
from sentinel.top import Top

class MySoC(Elaboratable):
    def __init__(self):
        self.cpu = Top()
        ...

    def elaborate(self, plat):
        m = Module()
        m.submodules.cpu = self.cpu
        ...
```

Since the Sentinel top-level is only a CPU, not a full computer system,
_the user must provide some sort of memory, and I/O to effectively run
programs_. One common way to do this is to connect Sentinel's Wishbone bus to
a Wishbone address decoder, behind which memory and I/O live.

See the {class}`~examples.attosoc.AttoSoC` `class`, and the corresponding
[section](./quickstart.md#a-full-example-soc-in-amaranth) in the Quickstart,
for a full working example.

## Public API

```{eval-rst}
.. automodule:: sentinel
```

```{eval-rst}
.. automodule:: sentinel.top
    :members:
```

```{eval-rst}
.. automodule:: sentinel.gen
    :members:
```
