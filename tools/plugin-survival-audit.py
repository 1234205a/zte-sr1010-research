#!/usr/bin/env python3
"""验证双槽固件写入范围与独立 Plugin 分区是否重叠。"""
import argparse,json,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("layout",HERE/"firmware-layout.py");mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
PLUGIN=(0x05800000,0x08000000)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("flash",type=Path);ap.add_argument("--fw-flashing",type=Path);a=ap.parse_args();raw=a.flash.read_bytes();r=mod.analyze(raw);slots=[];overlap=False
 for s in r["slots"]:
  lo,hi=s["slot_bounds"];hit=max(lo,PLUGIN[0])<min(hi,PLUGIN[1]);overlap|=hit;slots.append({"slot_base":s["slot_base"],"write_range":[lo,hi],"overlaps_plugin":hit})
 binary={}
 if a.fw_flashing:
  blob=a.fw_flashing.read_bytes();binary={"uses_whole_mtd":b"/dev/mtd0" in blob,"mentions_mtd9":b"/dev/mtd9" in blob,"mentions_plugin":b"/Plugin" in blob}
 out={"slot_layout_valid":r["valid"],"plugin_range":list(PLUGIN),"slots":slots,"flasher_surface":binary,"normal_upgrade_preserves_plugin":r["valid"] and not overlap and not binary.get("mentions_mtd9",False) and not binary.get("mentions_plugin",False),"whole_flash_restore_preserves_plugin":False}
 print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if out["normal_upgrade_preserves_plugin"] else 2
if __name__=="__main__":raise SystemExit(main())
