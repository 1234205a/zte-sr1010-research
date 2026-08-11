#!/usr/bin/env python3
"""解密SR1010配置并输出脱敏的管理面审计报告。"""
import argparse
import importlib.util
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def load_sibling(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CHECKS = {
    "TelnetCfg": ["TS_Enable", "Lan_Enable", "Wan_Enable", "SecurityEnable", "TimeoutEnable"],
    "Log": ["LogEnable", "SecLogEnable", "ServiceEnable", "SerialEnable"],
    "LogSerialCfg": ["SerialEnable", "PrintfEnable", "PrintkEnable"],
    "DiagCfg": ["RemoteDiag"],
    "SysdiagCfg": ["Enable", "EnableEncryption"],
    "FTPServerCfg": ["FtpEnable", "WanIfEnable", "FtpAnon"],
    "DevAuthInfo": ["Enable", "Level", "ChgPwd"],
    "SyslogCfg": ["Enable", "LocalEnable", "RemoteEnable", "PrintEnable"],
    "SecProtect": ["EnableProtectAdminPass", "EnableProtectWifiPass"],
    "Upgrade": ["UpgradeUserCfgEn"],
}
SECRET = re.compile(r"pass|pwd|user|key|token|url|server|host|addr|ip", re.I)


def audit(plain):
    root = ET.fromstring(plain)
    report = {"switches": {}, "sensitive_fields": {}}
    for table in root.findall(".//Tbl"):
        name = table.get("name", "")
        rows = table.findall("./Row")
        if name in CHECKS:
            report["switches"][name] = []
            for row in rows:
                values = {d.get("name"): d.get("val", "") for d in row.findall("./DM")}
                report["switches"][name].append({k: values.get(k) for k in CHECKS[name] if k in values})
        metadata = []
        for dm in table.findall(".//DM"):
            field, value = dm.get("name", ""), dm.get("val", "")
            if SECRET.search(field) and value:
                metadata.append({"field": field, "present": True, "length": len(value)})
        if metadata:
            report["sensitive_fields"][name] = metadata
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--model", default="SR1010")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()
    dec = load_sibling("config-bin-decrypt.py", "sr1010_config_decrypt")
    plain, blocks = dec.decrypt_type4(args.input.read_bytes(), args.model)
    report = audit(plain)
    report["blocks"] = blocks
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json:
        args.json.write_text(text, encoding="utf-8")
        print(f"已写入脱敏报告: {args.json}")
    else:
        print(text)


if __name__ == "__main__":
    main()
