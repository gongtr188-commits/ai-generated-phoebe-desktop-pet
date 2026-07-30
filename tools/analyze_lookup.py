# -*- coding: utf-8 -*-
"""分析 look_up 源图顶部残留区域"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matting import matte, imread_unicode, bg_level, char_bbox

base = sys.argv[1]
f = imread_unicode(os.path.join(base, "菲比-素材", "菲比抬头-俯视.png"))
print("size", f.shape, "bg_level", bg_level(f))

bgra = matte(f)
a = bgra[:, :, 3]
n, lab, stats, cent = cv2.connectedComponentsWithStats((a > 10).astype(np.uint8), connectivity=8)
print("components:", n - 1)
for i in range(1, n):
    x, y, w, h, area = stats[i]
    print(f"  comp{i}: xywh=({x},{y},{w},{h}) area={area} centroid=({cent[i][0]:.0f},{cent[i][1]:.0f})")

# 对最上面的连通块采样颜色
tops = [i for i in range(1, n) if stats[i, 1] < f.shape[0] * 0.2 and stats[i, cv2.CC_STAT_AREA] < 200000]
for i in tops:
    m = lab == i
    px = f[m]
    mn = px.min(axis=1).astype(np.int16)
    mx = px.max(axis=1).astype(np.int16)
    print(f"comp{i} color: min_p5={np.percentile(mn,5):.0f} p50={np.percentile(mn,50):.0f} "
          f"p95={np.percentile(mn,95):.0f} diff_p50={np.percentile(mx-mn,50):.0f} p95={np.percentile(mx-mn,95):.0f}")

# 边框各边的背景亮度差异(渐变程度)
for name, sl in [("top", f[:6]), ("bottom", f[-6:]), ("left", f[:, :6]), ("right", f[:, -6:])]:
    v = sl.reshape(-1, 3).min(axis=1)
    print(f"border {name}: p5={np.percentile(v,5):.0f} p50={np.percentile(v,50):.0f} p95={np.percentile(v,95):.0f}")
