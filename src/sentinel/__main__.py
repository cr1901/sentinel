import argparse

from .ucoderom import UCodeROM


def main_parser(parser=None):
    if parser is None:
        parser = argparse.ArgumentParser()

    p_action = parser.add_subparsers(dest="action")
    p_ucode = p_action.add_parser("microcode",
                                  help="Run the microcode assembler")
    p_ucode.add_argument("-f", "--field-defs", metavar="FDEFS-FILE",
                         help="emit field defines to FDEFS-FILE")
    p_ucode.add_argument("-x", "--hex", metavar="HEX-FILE",
                         help="emit a hex file")

    return parser


def main_runner(parser, args):
    if args.action == "microcode":
        ucode = UCodeROM(field_defs=args.field_defs, hex=args.hex)
        ucode._MustUse__used = True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    main_p = main_parser(parser)
    args = parser.parse_args()

    main_runner(parser, args)
