# -*- coding: utf-8 -*-
"""扫描动画帧中的可疑残留：主体之外的孤立不透明连通块"""
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matting import imwrite_unicode

base = sys.argv[1]      # 项目根目录
out = sys.argv[2]       # 输出目录
os.makedirs(out, exist_ok=True)

bad = []
for anim in ["spin", "walk_left", "walk_right"]:
    for p in sorted(glob.glob(os.path.join(base, "assets", "anim", anim, "*.png"))):
        img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
        a = (img[:, :, 3] > 30).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(a, connectivity=8)
        if n <= 2:
            continue
        areas = sorted(stats[1:, cv2.CC_STAT_AREA], reverse=True)
        extra = [x for x in areas[1:] if x >= 4]
        if extra:
            bad.append((anim, os.path.basename(p), len(extra), extra[:5]))

for b in bad:
    print(b)
print("frames with extra blobs:", len(bad))

# 把最严重的几帧贴洋红底导出
bad.sort(key=lambda x: -sum(x[3]))
for anim, name, cnt, areas in bad[:6]:
    p = os.path.join(base, "assets", "anim", anim, name)
    img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    h, w = img.shape[:2]
    canvas = np.full((h, w, 3), (200, 60, 200), np.uint8)
    al = img[:, :, 3:4].astype(np.float32) / 255.0
    vis = (img[:, :, :3] * al + canvas * (1 - al)).astype(np.uint8)
    imwrite_unicode(os.path.join(out, f"bad_{anim}_{name}"), vis)
    print("saved bad_%s_%s" % (anim, name))
