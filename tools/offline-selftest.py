#!/usr/bin/env python3
"""对 SR1010 当前恢复资产执行一次无设备、无秘密输出的统一自检。"""
import argparse, base64, hashlib, importlib.util, io, json, struct, tarfile, zlib, zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
def load(filename,name):
 spec=importlib.util.spec_from_file_location(name,HERE/filename);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
layout=load("firmware-layout.py","layout");cfg=load("config-bin-tool.py","cfg");recovery=load("recovery-kit.py","recovery")
MAGIC=(0x99999999,0x44444444,0x55555555,0xAAAAAAAA)
def sha(path):
 h=hashlib.sha256();size=0
 with path.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b);size+=len(b)
 return {"size":size,"sha256":h.hexdigest()}
def web_check(path):
 d=path.read_bytes();errors=[]
 if len(d)<0x108 or struct.unpack_from("<4I",d,0)!=MAGIC:return False,["magic_or_length"]
 skip=struct.unpack_from("<I",d,0x10)[0];at=0x14+skip;c=d[at:at+0xf4]
 if len(c)!=0xf4:return False,["common_header"]
 if zlib.crc32(c[:0xa4])&0xffffffff!=struct.unpack_from("<I",c,0xa4)[0]:errors.append("common_crc")
 for name,lo,oo,co in (("kernel",0x34,0x38,0x3c),("rootfs",0x40,0x44,0x48)):
  n,o,x=(struct.unpack_from("<I",c,q)[0] for q in (lo,oo,co))
  if o+n>len(d) or zlib.crc32(d[o:o+n])&0xffffffff!=x:errors.append(name+"_crc")
 boot=at+0xf4
 if boot+0x180000>len(d) or zlib.crc32(d[boot:boot+0x180000])&0xffffffff!=struct.unpack_from("<I",c,0x98)[0]:errors.append("boot_crc")
 return not errors,errors
def ipk_check(path):
 try:
  with tarfile.open(path,"r:gz") as outer:
   control=outer.extractfile("control.tar.gz").read();data=outer.extractfile("data.tar.gz").read()
  with tarfile.open(fileobj=io.BytesIO(control),mode="r:gz") as t: ctl=t.extractfile("control").read().decode("utf-8","replace")
  fields=dict(line.split(":",1) for line in ctl.splitlines() if ":" in line);start=fields.get("StartCMD","").strip().lstrip("/");stop=fields.get("StopCMD","").strip().lstrip("/")
  with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as t:names=set(t.getnames())
  return bool(fields.get("Package") and fields.get("Version") and start in names and stop in names),{"package":fields.get("Package","").strip(),"version":fields.get("Version","").strip()}
 except Exception as e:return False,{"error":type(e).__name__}
def main():
 ap=argparse.ArgumentParser()
 for n in ("flash","config","web_candidate","recovery_zip","net_ipk","ddns_ipk"):ap.add_argument("--"+n.replace("_","-"),type=Path,required=True)
 ap.add_argument("--output",type=Path);a=ap.parse_args();checks={};artifacts={}
 for n in ("flash","config","web_candidate","recovery_zip","net_ipk","ddns_ipk"):artifacts[n]=sha(getattr(a,n))
 fr=layout.analyze(a.flash.read_bytes());checks["flash_layout"]={"pass":fr["valid"] and all(s["header_crc_valid"] and s["common_crc_valid"] and s["boot_prefix_crc_valid"] for s in fr["slots"]),"slots":fr["slot_count"]}
 plain,cm=cfg.decrypt(a.config.read_bytes());checks["config_roundtrip"]={"pass":cfg.pack(plain)==a.config.read_bytes() and cm["header_crc_valid"] and cm["data_crc_valid"],"blocks":cm["blocks"]}
 ok,errors=web_check(a.web_candidate);checks["web_candidate"]={"pass":ok,"errors":errors}
 rm,bad=recovery.verify_zip(a.recovery_zip);checks["recovery_zip"]={"pass":not bad,"files":len(rm["files"]),"bad":bad}
 for n in ("net_ipk","ddns_ipk"):
  ok,info=ipk_check(getattr(a,n));checks[n]={"pass":ok,**info}
 plugin_start=0x05800000;checks["plugin_boundary"]={"pass":fr["valid"] and all(s["slot_bounds"][1]<=plugin_start for s in fr["slots"]),"plugin_start":plugin_start}
 result={"result":"PASS" if all(x["pass"] for x in checks.values()) else "FAIL","checks":checks,"artifacts":artifacts}
 text=json.dumps(result,ensure_ascii=False,indent=2)+"\n";print(text,end="")
 if a.output:a.output.write_text(text,encoding="utf-8")
 return 0 if result["result"]=="PASS" else 2
if __name__=="__main__":raise SystemExit(main())
