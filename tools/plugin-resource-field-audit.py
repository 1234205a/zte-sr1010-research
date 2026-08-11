#!/usr/bin/env python3
"""Verify how PluginCmapiInstall consumes flash/ram ctype values."""

import argparse
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from capstone.arm import ARM_OP_MEM
from elftools.elf.elffile import ELFFile


def function_bytes(elf, name):
    symbols = elf.get_section_by_name(".symtab")
    if symbols is None:
        raise ValueError("ELF has no .symtab")
    symbol = next((s for s in symbols.iter_symbols() if s.name == name), None)
    if symbol is None:
        raise ValueError(f"missing symbol: {name}")
    address = symbol["st_value"] & ~1
    section = elf.get_section(symbol["st_shndx"])
    offset = address - section["sh_addr"]
    return address, section.data()[offset : offset + symbol["st_size"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pluginmgr", type=Path)
    args = ap.parse_args()

    with args.pluginmgr.open("rb") as handle:
        elf = ELFFile(handle)
        address, code = function_bytes(elf, "PluginCmapiInstall")

    dis = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    dis.detail = True
    hits = {0x7DC: [], 0x7FC: []}
    for insn in dis.disasm(code, address):
        for operand in insn.operands:
            if operand.type == ARM_OP_MEM and operand.mem.disp in hits:
                hits[operand.mem.disp].append(
                    (insn.address, insn.mnemonic, insn.op_str)
                )

    print("PluginCmapiInstall resource ctype references")
    for offset, label in ((0x7DC, "flash.value"), (0x7FC, "ram.value")):
        print(f"{label} +0x{offset:x}: {len(hits[offset])} reference(s)")
        for item in hits[offset]:
            print(f"  0x{item[0]:08x} {item[1]:8} {item[2]}")

    expected = (
        [x[0] for x in hits[0x7DC]] == [0x13254, 0x13338, 0x136D8]
        and [x[0] for x in hits[0x7FC]] == [0x13260]
    )
    print("result=" + ("PASS" if expected else "REVIEW"))
    raise SystemExit(0 if expected else 1)


if __name__ == "__main__":
    main()

