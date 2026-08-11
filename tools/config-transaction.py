#!/usr/bin/env python3
"""围绕 config-bin-tool.py 提供备份、修改、差异和回滚事务。"""
import argparse, hashlib, importlib.util, json, shutil
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("cbt",HERE/"config-bin-tool.py"); cbt=importlib.util.module_from_spec(spec);spec.loader.exec_module(cbt)
def sha(b):return hashlib.sha256(b).hexdigest()
def meta(path):
    b=path.read_bytes();p,m=cbt.decrypt(b);cbt.validate_xml(p);return b,p,m
def main():
    ap=argparse.ArgumentParser();sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("prepare");p.add_argument("config",type=Path);p.add_argument("workspace",type=Path)
    p=sub.add_parser("build");p.add_argument("workspace",type=Path);p.add_argument("output",type=Path);p.add_argument("--set",action="append",default=[])
    p=sub.add_parser("rollback");p.add_argument("workspace",type=Path);p.add_argument("output",type=Path)
    a=ap.parse_args()
    if a.cmd=="prepare":
        a.workspace.mkdir(parents=True,exist_ok=False);blob,plain,m=meta(a.config)
        (a.workspace/"original-config.bin").write_bytes(blob);(a.workspace/"working.xml").write_bytes(plain)
        doc={"format":"sr1010-config-transaction-v1","created":datetime.now().isoformat(),"original_sha256":sha(blob),"plain_sha256":sha(plain),"metadata":m}
        (a.workspace/"transaction.json").write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"result":"PASS","workspace":str(a.workspace),"binary_reproducible":cbt.pack(plain)==blob},ensure_ascii=False));return 0
    original=a.workspace/"original-config.bin";working=a.workspace/"working.xml";doc=json.loads((a.workspace/"transaction.json").read_text(encoding="utf-8"))
    if sha(original.read_bytes())!=doc["original_sha256"]:raise SystemExit("原始配置哈希不匹配")
    if a.cmd=="rollback": shutil.copyfile(original,a.output);print(f"result=PASS output={a.output}");return 0
    before,_=cbt.decrypt(original.read_bytes());plain=working.read_bytes();cbt.validate_xml(plain)
    for item in a.set:
        left,value=item.rsplit("=",1);table,row,field=left.split(":",2);plain,_=cbt.edit_switch(plain,table,int(row),field,value)
    blob=cbt.pack(plain);check,m=cbt.decrypt(blob)
    if check!=plain:raise SystemExit("生成后复验失败")
    a.output.write_bytes(blob);report=cbt.diff_xml(before,plain)
    (a.workspace/"last-diff.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"result":"PASS","output":str(a.output),"sha256":sha(blob),"changes":report["change_count"],"crc":m["header_crc_valid"] and m["data_crc_valid"]},ensure_ascii=False,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
