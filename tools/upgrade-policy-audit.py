#!/usr/bin/env python3
"""离线确认 SR1010 固件 board/version 前缀与 boot upgrade-key 策略。"""
import argparse
import json
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile


def function_instructions(path, name):
    blob = path.read_bytes()
    with path.open("rb") as fh:
        elf = ELFFile(fh); table = elf.get_section_by_name(".symtab")
        if table is None: raise ValueError(f"{path.name} 不含 .symtab")
        sym = next((s for s in table.iter_symbols() if s.name == name), None)
        if sym is None: raise ValueError(f"缺少符号: {name}")
        addr, size = int(sym["st_value"]), int(sym["st_size"])
        for seg in elf.iter_segments():
            va, length = int(seg["p_vaddr"]), int(seg["p_filesz"])
            if seg["p_type"] == "PT_LOAD" and va <= addr and addr + size <= va + length:
                start = int(seg["p_offset"]) + addr - va; break
        else: raise ValueError("函数不在 LOAD 段")
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    return addr, size, list(md.disasm(blob[start:start + size], addr))


def has_seq(items, seq, window=6):
    for i in range(len(items)):
        pos = i
        for mnemonic, operand in seq:
            while pos < len(items) and pos - i <= window and not (items[pos].mnemonic == mnemonic and operand in items[pos].op_str): pos += 1
            if pos >= len(items) or pos - i > window: break
            pos += 1
        else: return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fw_flashing", type=Path)
    ap.add_argument("boot_flashing", type=Path)
    a = ap.parse_args()
    fa, fs, fw = function_instructions(a.fw_flashing, "check_ver_board")
    ba, bs, boot = function_instructions(a.boot_flashing, "CSPBootCheck")
    checks = {
        "board_prefix_4": has_seq(fw, [("mov", "r2, #4"), ("bl", "#")], 8),
        "software_prefix_6": has_seq(fw, [("mov", "r2, #6"), ("bl", "#")], 8),
        "vid_bitmap_24_bytes": any(i.mnemonic == "cmp" and i.op_str == "r6, #0x18" for i in fw),
        "package_key1_ffff_or_zero_bypass": has_seq(boot, [("movw", "r1, #0xffff"), ("cmp", "r2, r1"), ("cmpne", "r2, #0")], 5),
        "device_key1_ffff_or_zero_bypass": has_seq(boot, [("ldr", "r3, [r7]"), ("cmp", "r3, r1"), ("cmpne", "r3, #0")], 5),
        "key1_key2_exact_otherwise": has_seq(boot, [("cmp", "r2, r3"), ("bne", "#"), ("ldr", "r2, [r4, #0xc]"), ("ldr", "r3, [r7, #4]"), ("cmp", "r2, r3")], 10),
        "boot_crc_always_checked": any(i.mnemonic == "bl" and "#0x10f78" in i.op_str for i in boot),
    }
    report = {
        "fw_check": {"function": "check_ver_board", "address": fa, "size": fs},
        "boot_check": {"function": "CSPBootCheck", "address": ba, "size": bs},
        "checks": checks,
        "policy": {
            "board": "upgrade board id must match first 4 bytes",
            "software": "upgrade software version must match running first 6 bytes; no ordering comparison found",
            "vid": "upgrade VID must be enabled in 192-bit capability bitmap",
            "upgrade_key": "key check bypasses if package key1 or device key1 is 0/0xffff; otherwise key1 and key2 must both match",
            "boot_crc": "always verified after key decision",
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 2


if __name__ == "__main__": raise SystemExit(main())
