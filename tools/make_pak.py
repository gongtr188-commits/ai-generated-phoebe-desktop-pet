# -*- coding: utf-8 -*-
"""将 assets/ 打包为 data.pak（zip 格式换后缀），隐藏素材文件结构。
启动时 phoebe_pet.py 自动解压到临时目录使用。"""
import os, sys, zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE, "assets")
OUT = os.path.join(BASE, "data.pak")

if not os.path.isdir(ASSETS):
    print(f"ERROR: {ASSETS} not found")
    sys.exit(1)

count = 0
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(ASSETS):
        for f in sorted(files):
            src = os.path.join(root, f)
            arc = os.path.relpath(src, ASSETS)
            zf.write(src, arc)
            count += 1
            if count % 50 == 0:
                print(f"  {count} files...")

size_mb = os.path.getsize(OUT) / (1024 * 1024)
print(f"\nDone: {OUT}  ({count} files, {size_mb:.1f} MB)")
