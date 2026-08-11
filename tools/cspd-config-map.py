#!/usr/bin/env python3
"""从带符号 ARM cspd 中提取配置导入/导出函数和直接调用关系。"""
import argparse
import json
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

TARGETS = (
    "dbFileSaveUserCfg", "dbGetUsrCfgFileDeal", "dbcCfgFileEncry",
    "dbcCfgFileComKeyEncry", "dbcCfgFileIsEncry", "dbcCfgFileVersion",
    "dbcCfgFileUnVersion", "_dbCfgFileDecry.constprop.4", "dbcCfgFileDecry",
    "dbcDealCfgFileDecry", "dbFileRestore", "dbCPSaveCfg",
    "dbFileSaveBackupCfg", "dbBackupUsrCfg", "dbBackupUsrCfgNoCheck",
    "dbBackupUsrCfgNoLock", "dbFileCopy", "dbCPLoadCfg",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cspd", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    with a.cspd.open("rb") as fh:
        elf = ELFFile(fh)
        symtab = elf.get_section_by_name(".symtab")
        if symtab is None: raise SystemExit("cspd 不含 .symtab")
        symbols = {s.name: (int(s["st_value"]), int(s["st_size"])) for s in symtab.iter_symbols()}
        by_addr = {addr: name for name, (addr, size) in symbols.items() if addr and size}
        loads = [(int(s["p_vaddr"]), int(s["p_offset"]), int(s["p_filesz"]))
                 for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]

        def read_virtual(addr, size):
            for va, off, length in loads:
                if va <= addr and addr + size <= va + length:
                    fh.seek(off + addr - va); return fh.read(size)
            raise ValueError(f"地址不在 LOAD 段: 0x{addr:x}")

        md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
        report = {"arch": elf.get_machine_arch(), "entry": int(elf.header["e_entry"]), "functions": {}}
        for name in TARGETS:
            if name not in symbols: continue
            addr, size = symbols[name]; calls = []
            for ins in md.disasm(read_virtual(addr, size), addr):
                if ins.mnemonic not in ("bl", "blx") or not ins.op_str.startswith("#0x"): continue
                target = int(ins.op_str[1:], 16)
                calls.append({"site": ins.address, "target": target, "name": by_addr.get(target)})
            report["functions"][name] = {"address": addr, "size": size, "calls": calls}
        target_by_addr = {item["address"]: name for name, item in report["functions"].items()}
        for item in report["functions"].values(): item["callers"] = []
        functions = [(int(s["st_value"]), int(s["st_size"]), s.name) for s in symtab.iter_symbols()
                     if s["st_info"]["type"] == "STT_FUNC" and int(s["st_value"]) and int(s["st_size"])]
        for caller_addr, caller_size, caller_name in functions:
            for ins in md.disasm(read_virtual(caller_addr, caller_size), caller_addr):
                if ins.mnemonic not in ("bl", "blx") or not ins.op_str.startswith("#0x"): continue
                target = int(ins.op_str[1:], 16)
                if target in target_by_addr:
                    report["functions"][target_by_addr[target]]["callers"].append(
                        {"site": ins.address, "address": caller_addr, "name": caller_name})
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if a.json: a.json.write_text(text, encoding="utf-8")
    else: print(text)


if __name__ == "__main__":
    main()
