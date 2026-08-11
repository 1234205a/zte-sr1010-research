#!/usr/bin/env python3
"""Validate and normalize a WireGuard setconf file without printing secrets."""

import argparse
import base64
import hashlib
import ipaddress
import json
import os
import re
import stat
from pathlib import Path


INTERFACE_KEYS = {"privatekey", "listenport", "fwmark"}
PEER_KEYS = {
    "publickey", "presharedkey", "allowedips", "endpoint", "persistentkeepalive"
}
FORBIDDEN = {"preup", "postup", "predown", "postdown", "address", "dns", "table", "saveconfig"}
KEY_CASE = {
    "privatekey": "PrivateKey", "listenport": "ListenPort", "fwmark": "FwMark",
    "publickey": "PublicKey", "presharedkey": "PresharedKey",
    "allowedips": "AllowedIPs", "endpoint": "Endpoint",
    "persistentkeepalive": "PersistentKeepalive",
}


class ConfigError(ValueError):
    pass


def decode_key(value, label):
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ConfigError(f"{label}: invalid base64") from exc
    if len(raw) != 32:
        raise ConfigError(f"{label}: expected 32 decoded bytes, got {len(raw)}")
    return raw


def parse_endpoint(value):
    if value.startswith("["):
        match = re.fullmatch(r"\[([^]]+)]:(\d+)", value)
    else:
        match = re.fullmatch(r"([^:]+):(\d+)", value)
    if not match:
        raise ConfigError("Endpoint: expected HOST:PORT or [IPv6]:PORT")
    port = int(match.group(2))
    if not 1 <= port <= 65535:
        raise ConfigError("Endpoint: port out of range")


def parse(path):
    sections = []
    current = None
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip().lower()
            if name not in ("interface", "peer"):
                raise ConfigError(f"line {number}: unsupported section [{name}]")
            current = {"name": name, "items": [], "line": number}
            sections.append(current)
            continue
        if current is None or "=" not in line:
            raise ConfigError(f"line {number}: expected section or KEY=VALUE")
        key, value = (x.strip() for x in line.split("=", 1))
        lower = key.lower()
        if lower in FORBIDDEN:
            raise ConfigError(f"line {number}: {key} is forbidden/unsupported")
        allowed = INTERFACE_KEYS if current["name"] == "interface" else PEER_KEYS
        if lower not in allowed:
            raise ConfigError(f"line {number}: unknown {current['name']} key {key}")
        if any(k == lower for k, _, _ in current["items"]):
            raise ConfigError(f"line {number}: duplicate key {key}")
        current["items"].append((lower, value, number))
    if [s["name"] for s in sections].count("interface") != 1:
        raise ConfigError("exactly one [Interface] section is required")
    if sections[0]["name"] != "interface":
        raise ConfigError("[Interface] must be the first section")
    return sections


def validate(sections, protected, allow_protected, require_peer):
    interface = sections[0]
    peers = [s for s in sections if s["name"] == "peer"]
    if require_peer and not peers:
        raise ConfigError("at least one [Peer] is required")
    ivals = {k: v for k, v, _ in interface["items"]}
    if "privatekey" not in ivals:
        raise ConfigError("Interface.PrivateKey is required")
    decode_key(ivals["privatekey"], "Interface.PrivateKey")
    if "listenport" in ivals and not 1 <= int(ivals["listenport"], 0) <= 65535:
        raise ConfigError("Interface.ListenPort out of range")
    summary = {"interface": {"private_key": "present", "listen_port": ivals.get("listenport", "auto")}, "peers": []}
    for index, peer in enumerate(peers, 1):
        vals = {k: v for k, v, _ in peer["items"]}
        if "publickey" not in vals or "allowedips" not in vals:
            raise ConfigError(f"Peer {index}: PublicKey and AllowedIPs are required")
        public = decode_key(vals["publickey"], f"Peer {index}.PublicKey")
        if "presharedkey" in vals:
            decode_key(vals["presharedkey"], f"Peer {index}.PresharedKey")
        if "endpoint" in vals:
            parse_endpoint(vals["endpoint"])
        if "persistentkeepalive" in vals and not 0 <= int(vals["persistentkeepalive"], 0) <= 65535:
            raise ConfigError(f"Peer {index}.PersistentKeepalive out of range")
        networks = []
        for item in vals["allowedips"].split(","):
            try:
                network = ipaddress.ip_network(item.strip(), strict=False)
            except ValueError as exc:
                raise ConfigError(f"Peer {index}.AllowedIPs: {item.strip()}") from exc
            if not allow_protected and any(network.overlaps(p) for p in protected if p.version == network.version):
                raise ConfigError(f"Peer {index}.AllowedIPs {network} overlaps protected route")
            networks.append(str(network))
        summary["peers"].append({
            "public_key_sha256": hashlib.sha256(public).hexdigest()[:16],
            "preshared_key": "present" if "presharedkey" in vals else "absent",
            "endpoint": "present" if "endpoint" in vals else "absent",
            "allowed_ips": networks,
        })
    return summary


def normalize(sections):
    lines = []
    for section in sections:
        lines.append("[Interface]" if section["name"] == "interface" else "[Peer]")
        for key, value, _ in section["items"]:
            lines.append(f"{KEY_CASE[key]} = {value}")
        lines.append("")
    return "\n".join(lines).encode()


def secure_write(path, payload, force):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    fd = os.open(path, flags, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--output", type=Path, help="write normalized secret config with mode 0600")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--require-peer", action="store_true")
    ap.add_argument("--protect-cidr", action="append", default=["192.168.50.0/24", "10.8.0.0/24"])
    ap.add_argument("--allow-protected-route", action="store_true")
    args = ap.parse_args()
    try:
        protected = [ipaddress.ip_network(x, strict=False) for x in args.protect_cidr]
        sections = parse(args.config)
        summary = validate(sections, protected, args.allow_protected_route, args.require_peer)
        if args.output:
            secure_write(args.output, normalize(sections), args.force)
        print(json.dumps({"result": "PASS", **summary}, ensure_ascii=False, indent=2))
        if args.output:
            print(f"normalized_output={args.output}")
    except (ConfigError, OSError, ValueError) as exc:
        print(json.dumps({"result": "FAIL", "error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
