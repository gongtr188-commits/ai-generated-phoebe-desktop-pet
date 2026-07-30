# -*- coding: utf-8 -*-
"""分析向左走视频：找出开头"纯平移"的帧(姿势不变只挪位置)，确定需要掐掉多少帧"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matting import matte, SRC_DIR


def bbox_crop(bgra):
    ys, xs = np.where(bgra[:, :, 3] > 10)
    return bgra[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def analyze(name):
    cap = cv2.VideoCapture(os.path.join(SRC_DIR, name))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(matte(f))
    cap.release()
    print(name, "total", len(frames))
    prev = None
    for i, f in enumerate(frames):
        c = bbox_crop(f)
        c = cv2.resize(c, (128, 128))
        if prev is not None:
            diff = np.abs(c[:, :, :3].astype(np.int16) - prev[:, :, :3].astype(np.int16)).mean()
            print(f"frame {i:3d} pose-diff {diff:6.2f}")
        prev = c


if __name__ == "__main__":
    analyze("菲比-向左走.mp4")
