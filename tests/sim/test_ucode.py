from io import StringIO

from sentinel.ucoderom import UCodeROM


M5META_TEST_FILE = StringIO("""
space block_ram: width 32, size 256;

space block_ram;
origin 0;

fields block_ram: {
  foo: width 8, origin 0, default 0;
  bar: enum { a = 0; b = 0; c = 1; }, default a;
  baz: bool, origin 12, default 0;
};
""")


# This is a test by itself because creating the signature from the microcode
# assembly file can be tricky.
def test_ucode_layout_gen():
    ucode = UCodeROM(main_file=M5META_TEST_FILE)
    ucode.elaborate(None)
