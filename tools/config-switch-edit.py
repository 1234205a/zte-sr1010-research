#!/usr/bin/env python3
"""只修改审核过的布尔开关，并重新生成Type-4配置。"""
import argparse
import importlib.util
import re
from pathlib import Path


ALLOWED = {
    ("TelnetCfg", "TS_Enable"), ("TelnetCfg", "Lan_Enable"),
    ("TelnetCfg", "Wan_Enable"), ("TelnetCfg", "SecurityEnable"),
    ("DiagCfg", "RemoteDiag"), ("SysdiagCfg", "Enable"),
    ("FTPServerCfg", "FtpEnable"), ("FTPServerCfg", "WanIfEnable"),
    ("Log", "SerialEnable"), ("LogSerialCfg", "SerialEnable"),
    ("LogSerialCfg", "PrintfEnable"), ("LogSerialCfg", "PrintkEnable"),
    ("SyslogCfg", "RemoteEnable"),
}


def load_sibling(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def edit_switch(xml, table, row_index, field, value):
    if (table, field) not in ALLOWED or value not in ("0", "1"):
        raise ValueError(f"不在布尔开关白名单: {table}.{field}={value}")
    table_re = re.compile(rb'(<Tbl\s+name="' + re.escape(table.encode()) + rb'"[^>]*>)(.*?)(</Tbl>)', re.S)
    match = table_re.search(xml)
    if not match:
        raise ValueError(f"找不到表: {table}")
    body = match.group(2)
    rows = list(re.finditer(rb'<Row\b[^>]*>.*?</Row>', body, re.S))
    if row_index >= len(rows):
        raise ValueError(f"{table}不存在第{row_index}行")
    row = rows[row_index].group()
    dm_re = re.compile(rb'(<DM\s+name="' + re.escape(field.encode()) + rb'"\s+val=")([^"]*)("\s*/>)')
    dm = dm_re.search(row)
    if not dm:
        raise ValueError(f"找不到字段: {table}[{row_index}].{field}")
    old = dm.group(2).decode("ascii", "replace")
    new_row = row[:dm.start()] + dm.group(1) + value.encode() + dm.group(3) + row[dm.end():]
    start = match.start(2) + rows[row_index].start()
    end = match.start(2) + rows[row_index].end()
    return xml[:start] + new_row + xml[end:], old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    ap.add_argument("--model", default="SR1010")
    ap.add_argument("--set", action="append", required=True, metavar="TABLE:ROW:FIELD=0|1")
    args = ap.parse_args()
    dec = load_sibling("config-bin-decrypt.py", "sr1010_config_decrypt")
    enc = load_sibling("config-bin-pack.py", "sr1010_config_pack")
    plain, _ = dec.decrypt_type4(args.input.read_bytes(), args.model)
    changes = []
    for item in args.set:
        left, value = item.rsplit("=", 1)
        table, row, field = left.split(":", 2)
        plain, old = edit_switch(plain, table, int(row), field, value)
        changes.append((table, int(row), field, old, value))
    blob = enc.pack_type4(plain, args.model)
    # 生成后立即反向验证，避免输出结构损坏的配置。
    check, _ = dec.decrypt_type4(blob, args.model)
    if check != plain:
        raise SystemExit("重打包自检失败")
    args.output.write_bytes(blob)
    for table, row, field, old, new in changes:
        print(f"{table}[{row}].{field}: {old} -> {new}")
    print(f"已生成并通过解密自检: {args.output}")


if __name__ == "__main__":
    main()
