# -*- coding: utf-8 -*-
"""分析背景纯度与头发/白裙颜色分布，为抠图阈值提供依据"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matting import imread_unicode

base = sys.argv[1]
src = os.path.join(base, "菲比-素材")


def stats(name, bgr, mask, label):
    if mask.sum() == 0:
        print(name, label, "empty")
        return
    px = bgr[mask]
    mn = px.min(axis=1).astype(np.int16)
    mx = px.max(axis=1).astype(np.int16)
    diff = mx - mn
    print(f"{name:24s} {label:10s} n={mask.sum():7d} "
          f"min(BGR)_p5={np.percentile(mn,5):.0f} p50={np.percentile(mn,50):.0f} "
          f"diff_p50={np.percentile(diff,50):.0f} p95={np.percentile(diff,95):.0f} p99={np.percentile(diff,99):.0f}")


def border_mask(shape, t=6):
    m = np.zeros(shape[:2], bool)
    m[:t, :] = m[-t:, :] = m[:, :t] = m[:, -t:] = True
    return m


# 视频：spin 源帧132(输出#66)、walk 帧40
for vid, want in [("菲比-360°旋转.mp4", [0, 132]), ("菲比-向左走.mp4", [40]), ("菲比-向右走.mp4", [40])]:
    cap = cv2.VideoCapture(os.path.join(src, vid))
    idx = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if idx in want:
            stats(f"{vid}#{idx}", f, border_mask(f.shape), "bg-border")
            # 头发区域：黄色调(H 20~35 in OpenCV) 且较亮
            hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
            hair = (hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 35) & (hsv[:, :, 2] >= 180) & (hsv[:, :, 1] >= 25)
            stats(f"{vid}#{idx}", f, hair, "hair")
        idx += 1
    cap.release()

# 静态图
for img in ["菲比-正面.png", "菲比-背面.png"]:
    f = imread_unicode(os.path.join(src, img))
    print(img, "size:", f.shape)
    stats(img, f, border_mask(f.shape), "bg-border")
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    hair = (hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 35) & (hsv[:, :, 2] >= 180) & (hsv[:, :, 1] >= 25)
    stats(img, f, hair, "hair")
