# -*- coding: utf-8 -*-
"""生成向左走前 N 帧接触表 + 打印每帧人物 bbox 中心 x 坐标，定位纯平移段"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matting import matte, SRC_DIR, OUT_DIR


def main(name="菲比-向左走.mp4", n=36):
    cap = cv2.VideoCapture(os.path.join(SRC_DIR, name))
    frames = []
    while len(frames) < n:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(matte(f))
    cap.release()

    tiles = []
    for i, f in enumerate(frames):
        ys, xs = np.where(f[:, :, 3] > 10)
        cx = (xs.min() + xs.max()) / 2
        print(f"frame {i:3d} cx={cx:6.1f} bbox_w={xs.max()-xs.min()} bbox_h={ys.max()-ys.min()}")
        t = cv2.resize(f, (180, 180))
        bg = np.full((200, 180, 3), (200, 60, 200), np.uint8)
        a = t[:, :, 3:4].astype(np.float32) / 255
        bg[20:, :] = (t[:, :, :3] * a + bg[20:, :] * (1 - a)).astype(np.uint8)
        cv2.putText(bg, str(i), (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        tiles.append(bg)
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    grid = np.zeros((rows * 200, cols * 180, 3), np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        grid[r * 200:(r + 1) * 200, c * 180:(c + 1) * 180] = t
    ok, buf = cv2.imencode(".png", grid)
    buf.tofile(os.path.join(OUT_DIR, "_walk_sheet.png"))
    print("saved assets/_walk_sheet.png")


if __name__ == "__main__":
    main()
