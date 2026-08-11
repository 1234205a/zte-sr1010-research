#!/usr/bin/env python3
"""SR1010 Type-4 配置文件的只读检查、解包、重打包与往返验证工具。"""
import argparse
import hashlib
import json
import re
import struct
import sys
import tempfile
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

try:
    from Cryptodome.Cipher import AES
except ImportError as exc:
    raise SystemExit("需要 pycryptodomex: python -m pip install pycryptodomex") from exc

MAGIC = 0x01020304
TYPE = 4
OUTER_SIZE = 0x48
INNER_SIZE = 0x3C
BLOCK = 0x10000
AUDIT_FIELDS = {
    "TelnetCfg": ["TS_Enable", "Lan_Enable", "Wan_Enable", "SecurityEnable", "TimeoutEnable"],
    "DiagCfg": ["RemoteDiag"], "SysdiagCfg": ["Enable", "EnableEncryption"],
    "FTPServerCfg": ["FtpEnable", "WanIfEnable", "FtpAnon"],
    "Log": ["LogEnable", "SecLogEnable", "ServiceEnable", "SerialEnable"],
    "LogSerialCfg": ["SerialEnable", "PrintfEnable", "PrintkEnable"],
    "SyslogCfg": ["Enable", "LocalEnable", "RemoteEnable", "PrintEnable"],
    "DevAuthInfo": ["Enable", "Level", "ChgPwd"],
    "SecProtect": ["EnableProtectAdminPass", "EnableProtectWifiPass"],
    "Upgrade": ["UpgradeUserCfgEn"],
}
ALLOWED_SWITCHES = {
    ("TelnetCfg", "TS_Enable"), ("TelnetCfg", "Lan_Enable"),
    ("TelnetCfg", "Wan_Enable"), ("TelnetCfg", "SecurityEnable"),
    ("DiagCfg", "RemoteDiag"), ("SysdiagCfg", "Enable"),
    ("FTPServerCfg", "FtpEnable"), ("FTPServerCfg", "WanIfEnable"),
    ("Log", "SerialEnable"), ("LogSerialCfg", "SerialEnable"),
    ("LogSerialCfg", "PrintfEnable"), ("LogSerialCfg", "PrintkEnable"),
    ("SyslogCfg", "RemoteEnable"),
}
SECRET_NAME = re.compile(r"pass|pwd|user|key|token|secret|url|server|host|addr|ip", re.I)


def u32(data, off):
    if off < 0 or off + 4 > len(data):
        raise ValueError(f"读取越界: 0x{off:x}")
    return struct.unpack_from(">I", data, off)[0]


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def derive(model, product="0510", variant="0001"):
    model = "".join(model.split())
    suffix = product.removeprefix("0x") + variant.removeprefix("0x")
    return (
        hashlib.sha256(f"{model}Key{suffix}".encode()).digest(),
        hashlib.sha256(f"{model}Iv{suffix}".encode()).digest()[:16],
    )


def decrypt(blob, model="SR1010", product="0510", variant="0001"):
    if len(blob) < OUTER_SIZE or u32(blob, 0) != MAGIC or u32(blob, 4) != TYPE:
        raise ValueError("不是已识别的 SR1010 Type-4 配置")
    used, encrypted = u32(blob, 0x3C), u32(blob, 0x40)
    if used < INNER_SIZE or encrypted == 0 or encrypted % 16:
        raise ValueError("外层长度字段异常")
    if OUTER_SIZE + encrypted != len(blob):
        raise ValueError("外层密文长度与文件大小不一致")
    key, iv = derive(model, product, variant)
    padded = AES.new(key, AES.MODE_CBC, iv).decrypt(blob[OUTER_SIZE:])
    if used > len(padded) or any(padded[used:]):
        raise ValueError("CBC 填充或已用长度异常")
    inner = padded[:used]
    if u32(inner, 0) != MAGIC:
        raise ValueError("内层 magic 不匹配；请检查 model/product/variant")

    total, last, block_size = u32(inner, 8), u32(inner, 0x0C), u32(inner, 0x10)
    stored_data_crc, stored_header_crc = u32(inner, 0x14), u32(inner, 0x18)
    if block_size == 0 or block_size > 16 * 1024 * 1024:
        raise ValueError("块大小异常")
    header_crc = zlib.crc32(inner[:0x18]) & 0xFFFFFFFF
    pos, index, chunks, packed_chunks, seen = 0x3C, 0, [], [], set()
    while True:
        if pos in seen:
            raise ValueError("块链产生回环")
        seen.add(pos)
        if pos + 12 > len(inner):
            raise ValueError(f"块 {index} 头越界")
        raw_len, packed_len, next_pos = struct.unpack_from(">III", inner, pos)
        start, end = pos + 12, pos + 12 + packed_len
        if end > len(inner):
            raise ValueError(f"块 {index} 数据越界")
        packed = inner[start:end]
        try:
            chunk = zlib.decompress(packed)
        except zlib.error as exc:
            raise ValueError(f"块 {index} zlib 解压失败: {exc}") from exc
        if len(chunk) != raw_len or raw_len > block_size:
            raise ValueError(f"块 {index} 解压长度异常")
        if next_pos and next_pos != end:
            raise ValueError(f"块 {index} 的 next 指针不连续")
        chunks.append(chunk); packed_chunks.append(packed)
        if not next_pos:
            if pos != last:
                raise ValueError("最后块位置字段不匹配")
            break
        pos, index = next_pos, index + 1
    plain = b"".join(chunks)
    if len(plain) != total:
        raise ValueError("明文总长度不匹配")
    data_crc = 0
    for packed in packed_chunks:
        data_crc = zlib.crc32(packed, data_crc)
    meta = {
        "format": "SR1010-Type-4", "file_bytes": len(blob),
        "inner_bytes": used, "encrypted_bytes": encrypted,
        "plain_bytes": len(plain), "blocks": len(chunks), "block_size": block_size,
        "header_crc32": f"{stored_header_crc:08x}",
        "header_crc_valid": stored_header_crc == header_crc,
        "data_crc32": f"{stored_data_crc:08x}",
        "data_crc_valid": stored_data_crc == data_crc,
        "plain_sha256": sha256(plain),
    }
    return plain, meta


def pack(plain, model="SR1010", product="0510", variant="0001"):
    chunks = [plain[i:i + BLOCK] for i in range(0, len(plain), BLOCK)] or [b""]
    packed = [zlib.compress(chunk, 9) for chunk in chunks]
    positions, pos = [], INNER_SIZE
    for item in packed:
        positions.append(pos); pos += 12 + len(item)
    records, data_crc = bytearray(), 0
    for i, (chunk, item) in enumerate(zip(chunks, packed)):
        nxt = positions[i + 1] if i + 1 < len(positions) else 0
        records += struct.pack(">III", len(chunk), len(item), nxt) + item
        data_crc = zlib.crc32(item, data_crc)
    header = bytearray(INNER_SIZE)
    struct.pack_into(">IIIII", header, 0, MAGIC, 0, len(plain), positions[-1], BLOCK)
    struct.pack_into(">I", header, 0x14, data_crc & 0xFFFFFFFF)
    struct.pack_into(">I", header, 0x18, zlib.crc32(header[:0x18]) & 0xFFFFFFFF)
    inner = bytes(header + records)
    padded = inner + bytes(16 - len(inner) % 16)
    key, iv = derive(model, product, variant)
    encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(padded)
    outer = bytearray(OUTER_SIZE)
    struct.pack_into(">II", outer, 0, MAGIC, TYPE)
    struct.pack_into(">II", outer, 0x3C, len(inner), len(encrypted))
    return bytes(outer) + encrypted


def validate_xml(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"XML 解析失败: {exc}") from exc
    return root.tag


def xml_rows(data):
    """返回以 (表名, 行号, 字段名) 为键的值；只用于本地比较。"""
    root = ET.fromstring(data)
    result = {}
    for table in root.findall(".//Tbl"):
        name = table.get("name", "")
        for row_no, row in enumerate(table.findall("./Row")):
            for dm in row.findall("./DM"):
                result[(name, row_no, dm.get("name", ""))] = dm.get("val", "")
    return result


def audit_xml(data):
    values = xml_rows(data)
    switches, sensitive = {}, {}
    for (table, row, field), value in values.items():
        if table in AUDIT_FIELDS and field in AUDIT_FIELDS[table]:
            switches.setdefault(table, {}).setdefault(str(row), {})[field] = value
        if value and SECRET_NAME.search(field):
            sensitive.setdefault(table, []).append({"row": row, "field": field, "present": True, "length": len(value)})
    return {"switches": switches, "sensitive_fields": sensitive,
            "summary": {"switch_tables": len(switches), "sensitive_tables": len(sensitive)}}


def diff_xml(before, after, reveal=False):
    left, right = xml_rows(before), xml_rows(after)
    changes = []
    for key in sorted(set(left) | set(right)):
        old, new = left.get(key), right.get(key)
        if old == new: continue
        table, row, field = key
        secret = bool(SECRET_NAME.search(field))
        item = {"table": table, "row": row, "field": field, "sensitive": secret}
        if secret and not reveal:
            item.update({"old_present": old is not None and old != "", "old_length": len(old or ""),
                         "new_present": new is not None and new != "", "new_length": len(new or "")})
        else:
            item.update({"old": old, "new": new})
        changes.append(item)
    return {"change_count": len(changes), "changes": changes}


def edit_switch(data, table, row_no, field, value):
    if (table, field) not in ALLOWED_SWITCHES or value not in ("0", "1"):
        raise ValueError(f"不在布尔开关白名单: {table}.{field}={value}")
    table_re = re.compile(rb'(<Tbl\s+name="' + re.escape(table.encode()) + rb'"[^>]*>)(.*?)(</Tbl>)', re.S)
    match = table_re.search(data)
    if not match: raise ValueError(f"找不到表: {table}")
    rows = list(re.finditer(rb'<Row\b[^>]*>.*?</Row>', match.group(2), re.S))
    if row_no < 0 or row_no >= len(rows): raise ValueError(f"{table} 不存在第 {row_no} 行")
    row = rows[row_no].group()
    dm_re = re.compile(rb'(<DM\s+name="' + re.escape(field.encode()) + rb'"\s+val=")([^"]*)("\s*/>)')
    dm = dm_re.search(row)
    if not dm: raise ValueError(f"找不到字段: {table}[{row_no}].{field}")
    old = dm.group(2).decode("utf-8", "replace")
    new_row = row[:dm.start()] + dm.group(1) + value.encode() + dm.group(3) + row[dm.end():]
    start = match.start(2) + rows[row_no].start(); end = match.start(2) + rows[row_no].end()
    return data[:start] + new_row + data[end:], old


def args_common(parser):
    parser.add_argument("--model", default="SR1010")
    parser.add_argument("--product", default="0510")
    parser.add_argument("--variant", default="0001")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("inspect", "unpack", "verify", "roundtrip", "audit"):
        p = sub.add_parser(name); p.add_argument("input", type=Path); args_common(p)
        if name == "unpack": p.add_argument("output", type=Path)
    p = sub.add_parser("pack"); p.add_argument("input", type=Path); p.add_argument("output", type=Path); args_common(p)
    p = sub.add_parser("diff"); p.add_argument("before", type=Path); p.add_argument("after", type=Path); p.add_argument("--reveal", action="store_true"); args_common(p)
    p = sub.add_parser("edit"); p.add_argument("input", type=Path); p.add_argument("output", type=Path); p.add_argument("--set", action="append", required=True, metavar="TABLE:ROW:FIELD=0|1"); args_common(p)
    a = ap.parse_args()
    kw = {"model": a.model, "product": a.product, "variant": a.variant}
    if a.command == "pack":
        plain = a.input.read_bytes(); validate_xml(plain)
        blob = pack(plain, **kw); a.output.write_bytes(blob)
        check, meta = decrypt(blob, **kw)
        if check != plain: raise RuntimeError("内部往返校验失败")
        print(json.dumps({"output": str(a.output), "sha256": sha256(blob), **meta}, ensure_ascii=False, indent=2)); return
    if a.command == "diff":
        before, _ = decrypt(a.before.read_bytes(), **kw); after, _ = decrypt(a.after.read_bytes(), **kw)
        print(json.dumps(diff_xml(before, after, a.reveal), ensure_ascii=False, indent=2)); return
    blob = a.input.read_bytes(); plain, meta = decrypt(blob, **kw)
    meta["xml_root"] = validate_xml(plain)
    if a.command == "unpack":
        a.output.write_bytes(plain); meta["output"] = str(a.output)
    elif a.command == "roundtrip":
        rebuilt = pack(plain, **kw); plain2, meta2 = decrypt(rebuilt, **kw)
        meta["plaintext_roundtrip"] = plain2 == plain
        meta["binary_reproducible"] = rebuilt == blob
        meta["rebuilt_sha256"] = sha256(rebuilt)
        if plain2 != plain: raise RuntimeError("明文往返校验失败")
    elif a.command == "audit":
        meta["audit"] = audit_xml(plain)
    elif a.command == "edit":
        changes = []
        for item in a.set:
            left, value = item.rsplit("=", 1); table, row, field = left.split(":", 2)
            plain, old = edit_switch(plain, table, int(row), field, value)
            changes.append({"table": table, "row": int(row), "field": field, "old": old, "new": value})
        rebuilt = pack(plain, **kw); check, _ = decrypt(rebuilt, **kw)
        if check != plain: raise RuntimeError("修改后的内部往返校验失败")
        a.output.write_bytes(rebuilt); meta["output"] = str(a.output); meta["changes"] = changes
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try: main()
    except (OSError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr); raise SystemExit(2)
