#!/usr/bin/env python3
"""离线核对 SR1010 cspd 的 UpgradeCtl 数据流；不连接设备。"""
import argparse
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile


def symbol(elf, prefix):
    table = elf.get_section_by_name(".symtab")
    for item in table.iter_symbols():
        if item.name.startswith(prefix):
            return item
    raise SystemExit(f"缺少符号: {prefix}")


def instructions(elf, blob, sym):
    text = elf.get_section_by_name(".text")
    addr, size = sym["st_value"], sym["st_size"]
    start = text["sh_offset"] + addr - text["sh_addr"]
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    return list(md.disasm(blob[start:start + size], addr))


def has(items, mnemonic, operand):
    return any(i.mnemonic == mnemonic and operand in i.op_str for i in items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cspd", type=Path)
    args = ap.parse_args()
    blob = args.cspd.read_bytes()
    with args.cspd.open("rb") as stream:
        elf = ELFFile(stream)
        push = instructions(elf, blob, symbol(elf, "UpgradeProcPushEvent"))
        done = instructions(elf, blob, symbol(elf, "upgradeProcCheckSuccessEvent"))

    checks = {
        "payload_ctl_read": has(push, "ldr", "[r5, #0x2d8]"),
        "state_ctl_write": has(push, "str", "[r4, #0x370]"),
        "state_ctl_read": has(done, "ldr", "[r5, #0x370]"),
        "download_only_call": any(i.mnemonic == "bl" and "#0x14d62c" in i.op_str for i in done),
    }
    for key, value in checks.items():
        print(f"{key}={'yes' if value else 'no'}")
    if not all(checks.values()):
        raise SystemExit(2)
    print("event=0x2605")
    print("UpgradeCtl: 0=flash, 1=delayed/notify, other=finish_without_flash")


if __name__ == "__main__":
    main()
