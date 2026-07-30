# -*- coding: utf-8 -*-
"""
菲比桌宠素材抠图脚本
关键点 1：人物(帽子/裙子)与背景都是白色，不能按颜色全局抠白。
  方案：找"近背景色"像素 -> 连通域分析 -> 只有与图像边缘连通的区域才是背景。
  人物内部的白色被深色描边包裹，不与边缘连通，因此会被完整保留。
关键点 2：素材背景并非纯白(视频背景 229~247 有压缩噪声，look_up 是 213~254 的渐变)。
  方案：从图像边缘种子做"逐像素容差泛洪"(相邻差<=8 即继续淹没)，
  渐变和噪声都能平滑爬过；人物有深色描边阻挡，洪水进不去。
关键点 3：视频与静态图人物大小/亮度不一致。
  方案：所有素材按人物站立高度归一化缩放，贴到等高画布底部对齐；
  按背景亮度做曝光增益，把视频帧提亮到与静态图一致(背景=255)。
"""
import os
import glob
import shutil

import cv2
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(BASE, "菲比-素材")
OUT_DIR = os.path.join(BASE, "assets")

FLOOD_TOL = 8        # 泛洪相邻像素容差(逐通道)
SEED_MIN = 180       # 种子必须足够亮(排除边框上恰好是人物的位置)
SEED_DIFF = 18       # 种子通道差上限(必须接近灰白)
FRAME_STEP = 2       # 视频抽帧间隔(每 N 帧取 1 帧)

CHAR_H = 440         # 归一化后人物"站立高度"(像素)
CANVAS_H = 480       # 输出画布高(含帽子/跳动余量)
BASELINE = 6         # 人物脚底距画布底部的距离
MARGIN_W = 12        # 画布左右余量合计


def bg_level(bgr: np.ndarray, t: int = 6) -> int:
    """采样图像边框，返回背景亮度(min 通道中位数)"""
    b = np.concatenate([
        bgr[:t].reshape(-1, 3), bgr[-t:].reshape(-1, 3),
        bgr[:, :t].reshape(-1, 3), bgr[:, -t:].reshape(-1, 3)])
    return int(np.median(b.min(axis=1)))


def build_alpha(bgr: np.ndarray) -> np.ndarray:
    """返回 0~255 的 alpha 通道：从边缘种子容差泛洪，淹到的区域视为背景"""
    h, w = bgr.shape[:2]
    mn = bgr.min(axis=2).astype(np.int16)
    mx = bgr.max(axis=2).astype(np.int16)
    mask = np.zeros((h + 2, w + 2), np.uint8)
    # 彩色屏障：通道差明显的像素(头发高光/彩色部件)禁止被淹没
    barrier = (mx - mn) > 22
    mask[1:-1, 1:-1][barrier] = 1
    seed_ok = (mn >= SEED_MIN) & ((mx - mn) <= SEED_DIFF)
    flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8)
    lo = up = (FLOOD_TOL,) * 3
    seeds = [(x, y) for x in range(0, w, 24) for y in (0, h - 1)]
    seeds += [(x, y) for y in range(0, h, 24) for x in (0, w - 1)]
    for x, y in seeds:
        if seed_ok[y, x] and mask[y + 1, x + 1] == 0:
            cv2.floodFill(bgr, mask, (x, y), (255, 255, 255), lo, up, flags)
    bg_mask = mask[1:-1, 1:-1] == 255

    alpha = np.where(bg_mask, 0, 255).astype(np.uint8)
    # 除噪：人物是唯一的大连通块，删除面积不足最大块 1% 的孤立区块
    # (背景残留小点/压缩噪声/角落的半透明水印都远小于该比例)
    n2, lab2, stats, _ = cv2.connectedComponentsWithStats(alpha, connectivity=8)
    if n2 > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        thresh = max(int(areas.max() * 0.01), 16)
        for i in range(1, n2):
            if stats[i, cv2.CC_STAT_AREA] < thresh:
                alpha[lab2 == i] = 0
    # 收 1px 边缘去掉亮色镶边，再轻微羽化消除锯齿
    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=1)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    return alpha


def matte(bgr: np.ndarray) -> np.ndarray:
    """BGR -> BGRA(已去背景，并按背景亮度做曝光归一，视频帧提亮到与静态图一致)"""
    alpha = build_alpha(bgr)
    gain = 255.0 / max(bg_level(bgr), 1)
    bgr2 = np.clip(bgr.astype(np.float32) * gain, 0, 255).astype(np.uint8)
    bgra = cv2.cvtColor(bgr2, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = alpha
    return bgra


def char_bbox(bgra: np.ndarray):
    ys, xs = np.where(bgra[:, :, 3] > 10)
    if len(xs) == 0:
        return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def to_canvas(bgra: np.ndarray, k: float) -> np.ndarray:
    """按比例 k 缩放后贴到等高画布，底部对齐(脚底在 CANVAS_H-BASELINE)"""
    h, w = bgra.shape[:2]
    nw, nh = max(int(round(w * k)), 1), max(int(round(h * k)), 1)
    interp = cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC
    img = cv2.resize(bgra, (nw, nh), interpolation=interp)
    if nh > CANVAS_H - BASELINE:  # 兜底：过高则再压缩
        k2 = (CANVAS_H - BASELINE) / nh
        img = cv2.resize(img, (max(int(nw * k2), 1), CANVAS_H - BASELINE),
                         interpolation=cv2.INTER_AREA)
        nh, nw = img.shape[:2]
    canvas = np.zeros((CANVAS_H, nw + MARGIN_W, 4), np.uint8)
    y0 = CANVAS_H - BASELINE - nh
    x0 = MARGIN_W // 2
    canvas[y0:y0 + nh, x0:x0 + nw] = img
    return canvas


def imread_unicode(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path: str, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("PNG 编码失败: " + path)
    buf.tofile(path)


# 静态姿势图：源文件名 -> 输出英文名
POSE_MAP = {
    "菲比-正面.png": "front.png",
    "菲比-叉腰.png": "hands_on_hips.png",
    "菲比-正面-坐下.png": "sit.png",
    "菲比-的左面.png": "side_left.png",
    "菲比-的右面.png": "side_right.png",
    "菲比-背面.png": "back.png",
    "菲比抬头-俯视.png": "look_up.png",
    "菲比-举右手.png": "raise_right.png",
    "菲比-举双手.png": "raise_both.png",
    # 无帽版（打飞帽子功能用；其他朝向/姿势的素材缺失，后续完善）
    "没礼帽菲比-正面.png": "front_hatless.png",
    "没礼帽菲比-正面-坐下.png": "sit_hatless.png",
    "菲比-帽子.png": "hat.png",
}

# 动画视频：源文件名 -> 输出目录名
ANIM_MAP = {
    "菲比-向左走.mp4": "walk_left",
    "菲比-向右走.mp4": "walk_right",
    "菲比-360°旋转.mp4": "spin",
    "菲比-原地小跳.mp4": "hop",
    "菲比-向左跑.mp4": "run_left",
    "菲比-向右跑.mp4": "run_right",
    "菲比-悠闲坐.mp4": "lounge",
}

# 视频掐头帧数(源帧计)：行走视频开头 0~11 帧是站立/转身过渡，表现为纯平移，剪掉
TRIM_START = {
    "菲比-向左走.mp4": 12,
    "菲比-向右走.mp4": 12,
}


def process_poses():
    pose_dir = os.path.join(OUT_DIR, "poses")
    os.makedirs(pose_dir, exist_ok=True)
    # 以"正面"站立高度为基准，所有姿势用同一比例，保留坐下等姿势的天然高差
    front = matte(imread_unicode(os.path.join(SRC_DIR, "菲比-正面.png")))
    fx0, fy0, fx1, fy1 = char_bbox(front)
    k = CHAR_H / (fy1 - fy0 + 1)
    for src_name, out_name in POSE_MAP.items():
        src = os.path.join(SRC_DIR, src_name)
        if not os.path.exists(src):
            print("[skip] missing", out_name)
            continue
        bgra = matte(imread_unicode(src))
        x0, y0, x1, y1 = char_bbox(bgra)
        canvas = to_canvas(bgra[y0:y1 + 1, x0:x1 + 1], k)
        imwrite_unicode(os.path.join(pose_dir, out_name), canvas)
        print(f"[pose] poses/{out_name}  {canvas.shape[1]}x{canvas.shape[0]}")


def process_videos():
    for src_name, anim_name in ANIM_MAP.items():
        src = os.path.join(SRC_DIR, src_name)
        if not os.path.exists(src):
            print("[skip] missing", anim_name)
            continue
        out_dir = os.path.join(OUT_DIR, "anim", anim_name)
        os.makedirs(out_dir, exist_ok=True)
        # 清掉旧帧，避免帧数变化后残留
        for old in glob.glob(os.path.join(out_dir, "*.png")):
            os.remove(old)
        cap = cv2.VideoCapture(src)
        trim = TRIM_START.get(src_name, 0)
        idx = 0
        frames = []
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx >= trim and (idx - trim) % FRAME_STEP == 0:
                frames.append(matte(frame))
            idx += 1
        cap.release()
        if not frames:
            continue
        # 全部帧的统一包围盒(保留帧间自然位移)，人物高度取各帧中位数做归一
        x0 = y0 = 10 ** 9
        x1 = y1 = -1
        heights = []
        for f in frames:
            bb = char_bbox(f)
            if bb is None:
                continue
            x0, y0 = min(x0, bb[0]), min(y0, bb[1])
            x1, y1 = max(x1, bb[2]), max(y1, bb[3])
            heights.append(bb[3] - bb[1] + 1)
        k = CHAR_H / float(np.median(heights))
        for i, f in enumerate(frames):
            canvas = to_canvas(f[y0:y1 + 1, x0:x1 + 1], k)
            imwrite_unicode(os.path.join(out_dir, f"{i:03d}.png"), canvas)
        print(f"[anim] anim/{anim_name}/  {len(frames)} frames  "
              f"k={k:.3f} crop=({x0},{y0})-({x1},{y1})")


def process_sounds():
    """整理叫声素材到 assets/sounds(全部复制；"菲八啾比"系列仅作双击彩蛋)"""
    src = os.path.join(SRC_DIR, "声音")
    if not os.path.isdir(src):
        print("[skip] no sound dir")
        return
    out = os.path.join(OUT_DIR, "sounds")
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "*.mp3")):
        os.remove(old)
    n = 0
    for f in sorted(os.listdir(src)):
        if f.endswith(".mp3"):
            shutil.copy2(os.path.join(src, f), os.path.join(out, f))
            n += 1
    print(f"[sound] sounds/  {n} clips")


def make_preview():
    """生成校验图：抠图结果贴在洋红棋盘背景上，便于人工检查是否误抠"""
    paths = sorted(glob.glob(os.path.join(OUT_DIR, "poses", "*.png")))
    for a in ANIM_MAP.values():
        fs = sorted(glob.glob(os.path.join(OUT_DIR, "anim", a, "*.png")))
        paths += fs[::max(len(fs) // 4, 1)]  # 每段动画取几帧
    tiles = []
    for p in paths:
        if not os.path.exists(p):
            continue
        data = np.fromfile(p, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        scale = 240.0 / max(img.shape[:2])
        img = cv2.resize(img, (max(int(img.shape[1] * scale), 1),
                               max(int(img.shape[0] * scale), 1)),
                         interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
        canvas = np.zeros((256, 256, 3), np.uint8)
        canvas[:] = (200, 60, 200)
        canvas[0:256:32, :] = (150, 30, 150)
        y0, x0 = (256 - h) // 2, (256 - w) // 2
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        roi = canvas[y0:y0 + h, x0:x0 + w].astype(np.float32)
        canvas[y0:y0 + h, x0:x0 + w] = (img[:, :, :3] * a + roi * (1 - a)).astype(np.uint8)
        tiles.append(canvas)
    if not tiles:
        return
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    grid = np.zeros((rows * 256, cols * 256, 3), np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        grid[r * 256:(r + 1) * 256, c * 256:(c + 1) * 256] = t
    imwrite_unicode(os.path.join(OUT_DIR, "_preview.png"), grid)
    print("[preview] assets/_preview.png")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    process_poses()
    process_videos()
    process_sounds()
    make_preview()
    print("done")
