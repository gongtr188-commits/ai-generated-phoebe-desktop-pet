# -*- coding: utf-8 -*-
"""素材一致性/抠图质量检查：
1. 各姿势图与视频帧的人物包围盒大小 -> 判断大小是否一致
2. 人物像素的亮度/饱和度 -> 判断色调是否一致
3. 全部素材贴洋红底大图 -> 检查抠图残留
4. 旋转视频抽帧接触表 -> 标定 0/90/180/270 度关键帧
用法: python inspect_assets.py <桌面项目路径> <输出目录>
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from matting import matte, POSE_MAP, ANIM_MAP, TRIM_START, FRAME_STEP, imread_unicode, imwrite_unicode


def char_stats(bgra):
    a = bgra[:, :, 3]
    ys, xs = np.where(a > 128)
    if len(xs) == 0:
        return None
    h = ys.max() - ys.min() + 1
    w = xs.max() - xs.min() + 1
    pix = bgra[a > 128][:, :3].astype(np.float32)
    hsv = cv2.cvtColor(pix.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    return dict(h=int(h), w=int(w), y1=int(ys.max()), x_mid=int((xs.min() + xs.max()) / 2),
                mean_v=float(hsv[:, 2].mean()), mean_s=float(hsv[:, 1].mean()))


def on_magenta(bgra):
    h, w = bgra.shape[:2]
    canvas = np.full((h, w, 3), (200, 60, 200), np.uint8)
    a = bgra[:, :, 3:4].astype(np.float32) / 255.0
    return (bgra[:, :, :3] * a + canvas * (1 - a)).astype(np.uint8)


def main():
    base, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    src = os.path.join(base, "菲比-素材")

    print("== 静态姿势 (720x720 源) ==")
    tiles = []
    for name, en in POSE_MAP.items():
        bgr = imread_unicode(os.path.join(src, name))
        bgra = matte(bgr)
        s = char_stats(bgra)
        print(f"{en:16s} h={s['h']:4d} w={s['w']:4d} bottom={s['y1']:3d} "
              f"xmid={s['x_mid']:3d} V={s['mean_v']:.1f} S={s['mean_s']:.1f}")
        tiles.append((en, cv2.resize(on_magenta(bgra), (240, 240))))

    print("== 视频帧 (取样) ==")
    for name, en in ANIM_MAP.items():
        cap = cv2.VideoCapture(os.path.join(src, name))
        trim = TRIM_START.get(name, 0)
        idx, taken = 0, 0
        while True:
            ok, f = cap.read()
            if not ok:
                break
            if idx >= trim and (idx - trim) % FRAME_STEP == 0:
                if taken % 6 == 0:  # 每 6 个输出帧取样 1 帧
                    bgra = matte(f)
                    s = char_stats(bgra)
                    print(f"{en:10s} out#{taken:02d} h={s['h']:4d} w={s['w']:4d} "
                          f"bottom={s['y1']:3d} xmid={s['x_mid']:3d} "
                          f"V={s['mean_v']:.1f} S={s['mean_s']:.1f}")
                    tiles.append((f"{en}#{taken}", cv2.resize(on_magenta(bgra), (240, 240))))
                taken += 1
            idx += 1
        cap.release()

    # 残留检查大图
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    grid = np.zeros((rows * 258, cols * 242, 3), np.uint8)
    for i, (label, t) in enumerate(tiles):
        r, c = divmod(i, cols)
        grid[r * 258:r * 258 + 240, c * 242:c * 242 + 240] = t
        cv2.putText(grid, label, (c * 242 + 4, r * 258 + 254),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
    imwrite_unicode(os.path.join(out, "check_residue.png"), grid)

    # 旋转视频接触表(全部输出帧)
    cap = cv2.VideoCapture(os.path.join(src, "菲比-360°旋转.mp4"))
    idx, taken = 0, 0
    spin_tiles = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if idx % FRAME_STEP == 0:
            bgra = matte(f)
            spin_tiles.append((taken, cv2.resize(on_magenta(bgra), (160, 160))))
            taken += 1
        idx += 1
    cap.release()
    cols = 8
    rows = (len(spin_tiles) + cols - 1) // cols
    grid = np.zeros((rows * 178, cols * 162, 3), np.uint8)
    for i, (n, t) in enumerate(spin_tiles):
        r, c = divmod(i, cols)
        grid[r * 178:r * 178 + 160, c * 162:c * 162 + 160] = t
        cv2.putText(grid, str(n), (c * 162 + 4, r * 178 + 174),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    imwrite_unicode(os.path.join(out, "spin_sheet.png"), grid)
    print("spin frames:", len(spin_tiles))
    print("saved:", out)


if __name__ == "__main__":
    main()
