#!/usr/bin/env python3
"""构建并验证只保存在本地的 SR1010 完整恢复包。"""
import argparse, hashlib, json, shutil, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROLES = ("full_flash", "web_candidate", "config", "net_runtime_ipk", "ddns_ipk")

def digest(path):
    h=hashlib.sha256(); size=0
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b); size+=len(b)
    return size,h.hexdigest()

def verify_zip(path):
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read("manifest.json"))
        bad=[]
        for item in manifest["files"]:
            data=z.read(item["archive_name"])
            if len(data)!=item["size"] or hashlib.sha256(data).hexdigest()!=item["sha256"]: bad.append(item["archive_name"])
    return manifest,bad

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    b=sub.add_parser("build"); b.add_argument("output",type=Path)
    for role in ROLES: b.add_argument("--"+role.replace("_","-"),type=Path)
    v=sub.add_parser("verify"); v.add_argument("archive",type=Path)
    a=ap.parse_args()
    if a.cmd=="verify":
        m,bad=verify_zip(a.archive); print(json.dumps({"result":"PASS" if not bad else "FAIL","files":len(m["files"]),"bad":bad},ensure_ascii=False,indent=2)); return 1 if bad else 0
    files=[]
    for role in ROLES:
        p=getattr(a,role)
        if p:
            if not p.is_file(): raise SystemExit(f"文件不存在: {p}")
            size,sha=digest(p); files.append({"role":role,"source_name":p.name,"archive_name":"artifacts/"+role+"-"+p.name,"size":size,"sha256":sha,"path":p})
    if not any(x["role"]=="full_flash" for x in files): raise SystemExit("必须提供 --full-flash")
    manifest={"format":"sr1010-recovery-kit-v1","created_utc":datetime.now(timezone.utc).isoformat(),"files":[{k:v for k,v in x.items() if k!="path"} for x in files]}
    guide="""SR1010 本地恢复包\n\n恢复优先级：\n1. 先校验 manifest；\n2. 配置问题优先使用原始 config；\n3. 正常网页恢复只使用经过 preflight 的 web candidate；\n4. full flash 只用于底层救援，不在无串口救援条件下写入；\n5. IPK 用于恢复 WireGuard/DDNS。\n\n本包含设备敏感数据，只保存在加密本地存储。\n"""
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.output,"w",compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        z.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
        z.writestr("README.txt",guide)
        for x in files:z.write(x["path"],x["archive_name"])
    _,bad=verify_zip(a.output)
    print(json.dumps({"output":str(a.output),"size":a.output.stat().st_size,"files":len(files),"verified":not bad},ensure_ascii=False,indent=2)); return 1 if bad else 0

if __name__=="__main__": raise SystemExit(main())
