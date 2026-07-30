# -*- coding: utf-8 -*-
"""
菲比桌面宠物 (Wuthering Waves - Phoebe Desktop Pet)

功能：
- 逐像素透明、无边框、置顶的小窗口
- 朝向状态机(正面/左/背面/右)，方向切换播放旋转动画(取自 360° 旋转视频帧)
- 随机漫游：走向屏幕上随机目标点，行走沿斜线自然改变高度(非周期晃动)
- 双击 -> 随机叫一声(小概率"菲八啾比"彩蛋)；左键拖拽 -> 正面站立随鼠标移动
- 三连击正面/坐着的菲比 -> 帽子被打飞(抛物线掉落) -> 拖帽子回去可戴回
- 右键菜单：走动(含原地转90°) / 动作(含随机声音) / 设置(变大、变小、总在最前、安静一点、叫声频率) / 退出
- 转身/转圈中途收到新指令都从当前角度就近改道，立即响应
- 接近 180° 的转身随机从左/右侧绕，不固定一边
- 叫声：出场问好；走路/旋转发短促音；静止(站/坐/抬头/叉腰)隔段时间说话；
  正面站立说话时配举右手/举双手动作，或原地小跳并连叫几声；
  每声播完后小概率隔一小段时间补叫一声；全局冷却不吵人，"安静一点"减频降音量；
  无帽状态(帽子被打飞后)使用全声音素材且菲八啾比占比更高
- 帽子打飞后约 38 秒自动消失恢复；玩家可拖帽子回菲比头上提前戴回
- TODO: 无帽版素材目前仅正面/坐下，侧/背/举手/叉腰/小跳等姿势待补充
"""
import os
import random
import sys
import time
import ctypes
from ctypes import wintypes

# 部分 Python 环境下 PyQt5 找不到自带的 Qt 插件(平台插件报 Could not find the Qt
# platform plugin "windows"、多媒体报 does not have a valid service)，导致窗口
# 无法创建或声音无法播放。这里显式指到 PyQt5 自带插件目录。
import PyQt5
_qt_plugins = os.path.join(os.path.dirname(PyQt5.__file__), "Qt5", "plugins")
if os.path.isdir(_qt_plugins):
    os.environ.setdefault("QT_PLUGIN_PATH", _qt_plugins)
    os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH",
                          os.path.join(_qt_plugins, "platforms"))

from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QPixmap, QIcon, QCursor
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QMenu, QAction,
                             QSlider, QWidgetAction)

# PyInstaller --onefile 打包后在临时目录解压素材，frozen 时用 sys._MEIPASS
if getattr(sys, 'frozen', False):
    BASE = sys._MEIPASS
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")

# 如果存在 data.pak，自动解压到临时目录（隐藏素材，避免 GitHub 上直接被浏览）
_PAK = os.path.join(BASE, "data.pak")
if os.path.isfile(_PAK):
    import tempfile, zipfile, shutil as _shutil
    _PAK_TEMP = os.path.join(tempfile.gettempdir(), "phoebe_pet_assets")
    if not os.path.isdir(_PAK_TEMP) or not os.path.isdir(os.path.join(_PAK_TEMP, "poses")):
        if os.path.isdir(_PAK_TEMP):
            _shutil.rmtree(_PAK_TEMP)
        os.makedirs(_PAK_TEMP)
        with zipfile.ZipFile(_PAK, "r") as _zf:
            _zf.extractall(_PAK_TEMP)
    ASSETS = _PAK_TEMP

FPS_MS = 80              # 动画帧间隔(素材 24fps 抽 1/2 帧 => 12fps)
WALK_SPEED = 3           # 行走像素/帧
RUN_SPEED = 7            # 跑步像素/帧
SIZE_MIN, SIZE_MAX = 70, 430                                 # 缩放条范围
SIZE_STEPS = [80, 100, 125, 155, 190, 230, 275, 330, 400]    # 变大/变小档位
DEFAULT_H = 125          # 启动默认高度(小巧)

# 右键菜单样式：白底圆角卡片 + 菲比紫主题色(呼应她的紫色瞳孔)
MENU_QSS = """
QMenu {
    background-color: rgba(255, 255, 255, 248);
    border: 1px solid #e8e2f7;
    border-radius: 14px;
    padding: 8px 6px;
    font-size: 13px;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
}
QMenu::item {
    background: transparent;
    color: #4b4560;
    padding: 9px 30px 9px 10px;
    margin: 1px 4px;
    border-radius: 9px;
}
QMenu::item:selected {
    background-color: #f0ebff;
    color: #6b4fd8;
}
QMenu::item:disabled {
    color: #c5bfd6;
}
QMenu::separator {
    height: 1px;
    background: #ece7f8;
    margin: 8px 18px;
}
QMenu::indicator {
    width: 14px;
    height: 14px;
    margin-left: 0px;
    margin-right: 4px;
}
QSlider {
    background: transparent;
    min-height: 22px;
}
QSlider::groove:horizontal {
    height: 4px;
    border-radius: 2px;
    background: #e8e2f7;
}
QSlider::sub-page:horizontal {
    height: 4px;
    border-radius: 2px;
    background: #a98ff0;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: #8b6fe8;
    border: 2px solid #ffffff;
}
QSlider::handle:horizontal:hover {
    background: #6b4fd8;
}
"""

# 朝向(四分位)：0 正面 / 1 左侧 / 2 背面 / 3 右侧
FACE_POSE = ["front", "side_left", "back", "side_right"]
# 旋转视频实际转向：正面(0)->右侧(20)->背面(50)->左侧(76)->正面(108)
SPIN_KEY = [0, 76, 50, 20]
SPIN_CYCLE = 108
TURN_STEP = 2            # 转身动画抽帧步长(越大转得越快)

# 打飞帽子：抛物线物理参数
HAT_GRAVITY = 2.0        # 每帧下落加速度(px) — 模拟重力感
HAT_FADE_AFTER = 35.0    # 多少秒后帽子开始消失

# 悠闲坐窗
SNAP_RANGE = 200         # 拖到窗口上边缘多少 px 内就吸附
LOUNGE_MIN_S = 30.0      # 最少悠闲坐多久（秒）
LOUNGE_MAX_S = 90.0      # 最多坐多久再自己跳下来
LOUNGE_FRAMES = 24       # 只用悠闲坐动画前 ~2 秒

# 各素材显示高度微调倍率（部分素材内容偏大/偏小）
POSE_K = {"front_hatless": 0.92, "sit_hatless": 0.80, "hat": 0.80, "sit": 1.05}


class HatWidget(QWidget):
    """帽子的独立透明窗口：被打飞后沿抛物线飞行，可被拖回菲比头上"""
    def __init__(self, pet: "PhoebePet"):
        super().__init__()
        self.pet = pet
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.SubWindow | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)

        self.pm = None           # QPixmap(由 pet 缩放后传入)
        self.fx = self.fy = 0.0  # 浮点坐标
        self.vx = self.vy = 0.0
        self.flying = False
        self.fading = False
        self.fade_start = 0.0
        self.drag_offset = None
        self._dragged = False       # 本次按下后是否真的拖动了

        self.phys_timer = QTimer(self)
        self.phys_timer.timeout.connect(self.tick)

    def set_hat_pixmap(self, pm: QPixmap):
        self.pm = pm
        self.setFixedSize(pm.width() + 4, pm.height() + 4)
        self.label.setGeometry(0, 0, self.width(), self.height())
        self.label.setPixmap(pm)

    def launch(self, start_x: int, start_y: int, target_x: int = None, target_y: int = None):
        """帽子沿重力抛物线飞向屏幕随机落点（X 全屏，Y 在角色附近合理范围）"""
        self.fx, self.fy = float(start_x), float(start_y)
        geo = QApplication.primaryScreen().availableGeometry()
        margin = 50
        if target_x is None:
            target_x = random.randint(geo.left() + margin,
                                      geo.right() - margin - self.width())
        if target_y is None:
            # 落点 Y 全屏任意位置
            lo = geo.top() + margin
            hi = geo.bottom() - margin - self.height()
            target_y = random.randint(lo, hi)

        dx = target_x - self.fx
        dy = target_y - self.fy
        # 避免帽子直直落在人物正上方/正下方：水平偏移至少 150px
        if abs(dx) < 150:
            if dx >= 0:
                target_x = int(self.fx) + 150 + random.randint(0, 80)
            else:
                target_x = int(self.fx) - 150 - random.randint(0, 80)
            target_x = max(geo.left() + margin,
                           min(geo.right() - margin - self.width(), target_x))
            dx = target_x - self.fx
        g = HAT_GRAVITY

        # 飞行帧数：按水平距离估，最少 6 帧
        total_frames = max(6, min(22, int(abs(dx) / 12.0)))

        self.vx = dx / total_frames
        self.vy = (dy - 0.5 * g * total_frames * total_frames) / total_frames
        # 弧线太平（vy 接近 0 甚至向下）→ 延长飞行时间换取可见上抛
        while self.vy > -3.0 and total_frames < 45:
            total_frames += 4
            self.vx = dx / total_frames
            self.vy = (dy - 0.5 * g * total_frames * total_frames) / total_frames

        self._flight_frame = 0
        self._total_frames = total_frames
        self._target_xy = (float(target_x), float(target_y))

        self.flying = True
        self.fading = False
        self.move(int(self.fx), int(self.fy))
        self.show()
        self.phys_timer.start(FPS_MS)
        # 用 child timer 避免 widget 销毁后悬空回调
        QTimer(self, interval=int(HAT_FADE_AFTER * 1000),
               singleShot=True, timeout=self.start_fade).start()

    def tick(self):
        # 淡出在飞行结束后仍需运行 → 不能随 flying=False 提前 return
        if self.flying:
            self._flight_frame += 1
            # 重力抛物线：每帧加速
            self.fx += self.vx
            self.fy += self.vy
            self.vy += HAT_GRAVITY

            # 到达目标帧数 → 精确停在落点
            if self._flight_frame >= self._total_frames:
                self.fx, self.fy = self._target_xy
                self.vy = 0.0
                self.vx = 0.0
                self.flying = False
            self.move(int(self.fx), int(self.fy))

        # 淡出中（飞行结束后 fade timer 会调用 start_fade，需在此处理）
        if self.fading:
            elapsed = time.monotonic() - self.fade_start
            alpha = max(0.0, 1.0 - elapsed / 3.0)
            self.setWindowOpacity(alpha)
            if alpha <= 0.01:
                self.hide()
                self.fading = False
                self.phys_timer.stop()   # 淡出完成后停定时器

    def start_fade(self):
        if self.fading or not self.isVisible():
            return
        self.fading = True
        self.fade_start = time.monotonic()
        # 飞行结束后 phys_timer 已停，淡出需要重新启动
        if not self.phys_timer.isActive():
            self.phys_timer.start(FPS_MS)

    # ---------- 帽子拖拽 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_offset = e.globalPos() - self.frameGeometry().topLeft()
            self._dragged = False
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self.drag_offset is not None:
            self._dragged = True
            self.flying = False
            self.phys_timer.stop()
            self.fading = False
            self.setWindowOpacity(1.0)
            self.move(e.globalPos() - self.drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_offset = None
            # 只有真的拖动了帽子才检查是否戴回（避免单击误触）
            if self._dragged and self.pet._try_reattach_hat(self):
                self._dragged = False
                return
            self._dragged = False
            e.accept()


class PhoebePet(QWidget):
    def __init__(self):
        super().__init__()
        self.pet_h = DEFAULT_H
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint |
            Qt.SubWindow | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle("菲比桌宠")

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)

        self.load_assets()

        # 状态机: idle / walk / turn / spin / sit / drag
        self.state = "idle"
        self.facing = 0
        self.frame_i = 0
        self.idle_pose = "front"
        self.turn_seq = []
        self.turn_i = 0
        self.turn_target = 0
        self.turn_done = None
        self.spin_dir = 1        # 转圈方向：1 顺放 / -1 倒放
        self.hop_loops = 1       # 原地小跳的循环圈数
        self.hold_until = 0.0    # 该时刻前不触发随机行为(让指定姿势多停留)

        # 叫声分组：全素材(普通) + 菲八啾比系列(彩蛋)；不再区分 soft/short
        self.sounds_all = []
        self.sounds_egg = []
        snd_dir = os.path.join(ASSETS, "sounds")
        if os.path.isdir(snd_dir):
            for f in sorted(os.listdir(snd_dir)):
                if not f.endswith(".mp3"):
                    continue
                p = os.path.join(snd_dir, f)
                if f.startswith("菲八啾比"):
                    self.sounds_egg.append(p)
                else:
                    self.sounds_all.append(p)
        self.player = QMediaPlayer(self)
        self.player.mediaStatusChanged.connect(self._on_sound_end)
        self.allow_echo = True   # 本次叫声结束后是否允许小概率补叫一声
        self.quiet = False       # "安静一点"：叫得更少、更小声
        self.sound_freq = 1.0    # 叫声频率倍率(设置里的缩放条，1.0 为默认)
        self.last_sound = 0.0
        # 刚出场打个招呼
        greet = os.path.join(snd_dir, "菲比啾比.mp3")
        if os.path.isfile(greet):
            QTimer(self, interval=800, singleShot=True, timeout=lambda: self._play(greet)).start()
        self.walk_target = (0, 0)
        self.walk_stroll = False
        self.run_target = (0, 0)   # 跑步目标
        self.fx = self.fy = 0.0
        self.vx = self.vy = 0.0
        self.drag_offset = None
        self.dragging = False
        self.follow_mouse = False  # 跟随鼠标模式

        # 打飞帽子系统
        self.hatless = False     # 当前是否无帽(被打飞或素材缺失阶段)
        self.hat_widget = None   # HatWidget 实例(帽子飞出时创建)
        self._restore_timer = None  # 自动恢复帽子的定时器引用
        self._lounge_until = 0.0   # 悠闲坐结束时刻（秒）
        self._lounge_hwnd = 0        # 坐着的目标窗口 HWND
        self._lounge_x_off = 0       # 菲比 X 相对窗口左沿的偏移
        # 连击检测：在 mousePressEvent 内计时计次，不依赖 mouseDoubleClickEvent
        self._click_count = 0
        self._last_click_time = 0.0

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.tick)
        self.anim_timer.start(FPS_MS)

        # 随机行为定时器
        self.behavior_timer = QTimer(self)
        self.behavior_timer.timeout.connect(self.random_behavior)
        self.behavior_timer.start(5000)

        # 跟随鼠标定时器（默认关闭）
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(200)
        self._follow_timer.timeout.connect(self._follow_tick)

        # 悠闲坐窗追踪定时器（窗口移动/最大化/消失时退坐）
        self._lounge_timer = QTimer(self)
        self._lounge_timer.setInterval(50)
        self._lounge_timer.timeout.connect(self._lounge_track)

        # 缩放条防抖：拖动时快速跟手重绘(按需缩放当前帧，开销极小)
        self._size_target = self.pet_h
        self.size_timer = QTimer(self)
        self.size_timer.setSingleShot(True)
        self.size_timer.setInterval(30)
        self.size_timer.timeout.connect(lambda: self.set_size(self._size_target))

        self.show_pose("front")
        self.resize_to_pet()
        # 初始位置：屏幕右下
        geo = QApplication.primaryScreen().availableGeometry()
        self.move(geo.right() - self.width() - 120,
                  geo.bottom() - self.height() + 1)
        self.show()

    # ---------- 资源 ----------
    def load_assets(self):
        # 原始尺寸素材只读一次盘；显示尺寸的缩放按需逐帧进行(见 pose_pix/frame_pix)
        if not hasattr(self, "_raw_poses"):
            self._raw_poses = {}
            pose_dir = os.path.join(ASSETS, "poses")
            for name in os.listdir(pose_dir):
                if not name.endswith(".png"):
                    continue
                key = os.path.splitext(name)[0]
                pm = QPixmap(os.path.join(pose_dir, name))
                if pm.isNull():
                    raise FileNotFoundError(name)
                self._raw_poses[key] = pm
            self._raw_anims = {}
            anim_dir = os.path.join(ASSETS, "anim")
            for anim in os.listdir(anim_dir):
                d = os.path.join(anim_dir, anim)
                self._raw_anims[anim] = [QPixmap(os.path.join(d, f))
                                         for f in sorted(os.listdir(d)) if f.endswith(".png")]
        self._pose_cache = {}
        self._frame_cache = {}

    def pose_pix(self, key: str) -> QPixmap:
        pm = self._pose_cache.get(key)
        if pm is None:
            h = int(self.pet_h * POSE_K.get(key, 1.0))
            pm = self._raw_poses[key].scaledToHeight(h, Qt.SmoothTransformation)
            self._pose_cache[key] = pm
        return pm

    def frame_pix(self, anim: str, i: int) -> QPixmap:
        pm = self._frame_cache.get((anim, i))
        if pm is None:
            pm = self._raw_anims[anim][i].scaledToHeight(self.pet_h, Qt.SmoothTransformation)
            self._frame_cache[(anim, i)] = pm
        return pm

    def anim_len(self, anim: str) -> int:
        return len(self._raw_anims[anim])

    def set_size(self, h: int):
        """直接设置显示高度(缩放条/档位共用)；只清缓存并重绘当前帧，瞬时完成"""
        h = max(SIZE_MIN, min(SIZE_MAX, int(h)))
        if h == self.pet_h:
            return
        self.pet_h = h
        self._pose_cache = {}
        self._frame_cache = {}
        self.resize_to_pet()
        self.apply_state_frame()

    def queue_size(self, h: int):
        """拖缩放条时防抖：停顿片刻才真正重缩放素材"""
        self._size_target = h
        self.size_timer.start()

    def step_size(self, delta: int):
        """变大/变小：跳到相邻档位"""
        if delta > 0:
            cands = [s for s in SIZE_STEPS if s > self.pet_h]
            if cands:
                self.set_size(cands[0])
        else:
            cands = [s for s in SIZE_STEPS if s < self.pet_h]
            if cands:
                self.set_size(cands[-1])

    def resize_to_pet(self):
        # 由原始素材宽高比推算当前显示宽度，无需真正缩放图片
        # 排除帽子素材(hat.png 570px 比角色宽，但帽子单独飞出不用参与窗口宽度)
        ws = []
        for k, pm in self._raw_poses.items():
            if k == "hat":
                continue
            h = int(self.pet_h * POSE_K.get(k, 1.0))
            ws.append(pm.width() * h // pm.height())
        for v in self._raw_anims.values():
            if v:
                ws.append(v[0].width() * self.pet_h // v[0].height())
        self.setFixedSize(max(ws) + 8, self.pet_h + 8)
        self.label.setGeometry(0, 0, self.width(), self.height())

    # ---------- 显示 ----------
    def show_pose(self, key: str):
        # 无帽状态下正面/坐下用无帽版素材
        # TODO: 其他朝向(侧/背)和动作(叉腰/抬头/举手)的无帽版素材缺失，等后续补充后再扩展
        if self.hatless:
            if key == "front" and "front_hatless" in self._raw_poses:
                key = "front_hatless"
            elif key == "sit" and "sit_hatless" in self._raw_poses:
                key = "sit_hatless"
        self.label.setPixmap(self.pose_pix(key))

    def show_frame(self, anim: str, i: int):
        self.label.setPixmap(self.frame_pix(anim, i % self.anim_len(anim)))

    def apply_state_frame(self):
        if self.state == "walk":
            self.show_frame("walk_left" if self.vx < 0 else "walk_right", self.frame_i)
        elif self.state == "run":
            self.show_frame("run_left" if self.vx < 0 else "run_right", self.frame_i)
        elif self.state == "turn":
            if self.turn_seq:
                self.show_frame("spin", self.turn_seq[min(self.turn_i, len(self.turn_seq) - 1)])
        elif self.state == "spin":
            self.show_frame("spin", self.spin_frame_idx())
        elif self.state == "hop":
            self.show_frame("hop", self.frame_i)
        elif self.state == "sit":
            self.show_pose("sit")
        elif self.state == "lounge":
            self.show_frame("lounge", self.frame_i)
        elif self.state == "drag":
            self.show_pose("front")
        else:
            self.show_pose(self.idle_pose)

    # ---------- 状态机 ----------
    def set_state(self, state: str):
        self.state = state
        self.frame_i = 0
        self.apply_state_frame()

    def face_idle(self):
        """按当前朝向站好"""
        self.idle_pose = FACE_POSE[self.facing]
        self.set_state("idle")

    def current_rot_pos(self) -> int:
        """当前在旋转视频圆周上的角度位置(帧号)；转身/转圈中途取正在显示的帧"""
        if self.state == "turn" and self.turn_seq:
            return self.turn_seq[min(self.turn_i, len(self.turn_seq) - 1)]
        if self.state == "spin":
            return self.spin_frame_idx() % SPIN_CYCLE
        return SPIN_KEY[self.facing]

    def turn_to(self, q_to: int, done=None):
        """从当前角度(含转身中途)就近转到目标朝向；done 为转完后的回调"""
        pos = self.current_rot_pos()
        b = SPIN_KEY[q_to]
        fwd = (b - pos) % SPIN_CYCLE
        back = (pos - b) % SPIN_CYCLE
        if fwd == 0:
            self.facing = q_to
            self.turn_done = None
            if done:
                done()
            else:
                self.face_idle()
            return
        if abs(fwd - back) <= 12:
            go_fwd = random.random() < 0.5   # 接近180°时两边都顺路，随机挑一边
        else:
            go_fwd = fwd < back              # 其余走视频帧距离最短的一侧
        if go_fwd:
            seq = range(pos, pos + fwd + 1, TURN_STEP)
        else:
            seq = range(pos, pos - back - 1, -TURN_STEP)
        self.turn_seq = [i % SPIN_CYCLE for i in seq]
        self.turn_i = 0
        self.turn_target = q_to
        self.turn_done = done
        self.set_state("turn")

    def facing_then(self, q: int, done):
        """先转到朝向 q(必要时播转身动画)，再执行 done"""
        self.turn_to(q, done=done)

    def start_spin(self):
        """转圈：顺时针/逆时针随机"""
        self.spin_dir = random.choice([1, -1])
        self.play_sound(chance=0.9)
        self.set_state("spin")

    def spin_frame_idx(self) -> int:
        n = self.anim_len("spin")
        i = self.frame_i if self.spin_dir > 0 else n - 1 - self.frame_i
        return max(0, min(i, n - 1))

    def request(self, action):
        """用户指令入口：转身/转圈中途 turn_to 会从当前角度就近改道，立即响应"""
        action()

    # ---------- 叫声 ----------
    def _play(self, path, echo=True):
        """echo=True 时播完后有小概率隔一小段时间再补叫一声(仅连锁一次)"""
        self.allow_echo = echo
        self.last_sound = time.monotonic()
        # 先停掉当前播放 → 延迟到下一事件循环再设媒体，避免 stop() 异步竞争
        if self.player.state() != QMediaPlayer.StoppedState:
            self.player.stop()
        QTimer.singleShot(0, lambda p=path: self._do_play(p))

    def _do_play(self, path):
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
        self.player.setVolume(32 if self.quiet else 85)
        self.player.play()

    def _on_sound_end(self, status):
        if status != QMediaPlayer.EndOfMedia:
            return
        if self.state == "hop":
            # 小跳期间连续叫：每声播完隔一小会儿就接着叫，直到跳完
            QTimer(self, interval=random.randint(250, 600), singleShot=True,
                   timeout=self._hop_bark).start()
            return
        if not self.allow_echo:
            return
        self.allow_echo = False
        if self.sounds_all and random.random() < 0.22:
            QTimer(self, interval=random.randint(700, 1800), singleShot=True,
                   timeout=lambda: self._play(random.choice(self.sounds_all), echo=False)).start()

    def play_sound(self, chance=1.0, force=False):
        """带全局冷却的叫声；安静模式下频率减半、音量更低；force 立即叫(菜单点播)
        返回是否真的叫出了声(供发声动作判断要不要配动作)"""
        if self.hatless and self.sounds_all:
            pool = self.sounds_egg if (self.sounds_egg and random.random() < 0.40) \
                else self.sounds_all
        else:
            pool = self.sounds_all
        if not pool:
            return False
        if not force:
            if time.monotonic() - self.last_sound < \
                    (26.0 if self.quiet else 8.0) / self.sound_freq:
                return False
            if random.random() >= chance * self.sound_freq * (0.4 if self.quiet else 1.0):
                return False
        self._play(random.choice(pool))
        return True

    def double_bark(self):
        """双击：立即随机叫一声；只有无帽状态才可能出"菲八啾比"彩蛋"""
        if self.hatless:
            pool = self.sounds_egg if (self.sounds_egg and random.random() < 0.40) \
                else (self.sounds_all + self.sounds_egg)
        else:
            pool = self.sounds_all
        if pool:
            self._play(random.choice(pool))

    def vocal_gesture(self, chance=1.0):
        """正面站立时的发声动作：叫出声才配动作——举右手/举双手，或原地小跳连叫
        返回是否触发了动作(触发时调用方应跳过本轮行为切换，别把动作盖掉)"""
        if not self.play_sound(chance=chance):
            return False
        if random.random() < 0.35 and self._raw_anims.get("hop"):
            self.start_hop()
        else:
            self.idle_pose = random.choice(["raise_right", "raise_both"])
            self.apply_state_frame()
            self.hold_until = time.monotonic() + 4.0   # 让动作完整展示
            QTimer(self, interval=2800, singleShot=True, timeout=self._gesture_reset).start()
        return True

    def _gesture_reset(self):
        if self.state == "idle" and self.idle_pose in ("raise_right", "raise_both"):
            self.idle_pose = "front"
            self.apply_state_frame()

    def start_hop(self):
        """原地小跳(一段约5秒，偶尔两段)；起跳那声叫完后由 _on_sound_end 链式连叫"""
        self.hop_loops = random.choice((1, 1, 1, 2))
        self.set_state("hop")
        if self.player.state() != QMediaPlayer.PlayingState:
            self._hop_bark()     # 兜底：进跳时没声音在播就立刻开叫

    def _hop_bark(self):
        if self.state == "hop" and self.sounds_all:
            self._play(random.choice(self.sounds_all), echo=False)

    # ---------- 行走 ----------
    def start_walk(self, direction: str):
        """向左走/向右走：走到屏幕边缘，保持当前高度"""
        geo = QApplication.primaryScreen().availableGeometry()
        tx = geo.left() if direction == "walk_left" else geo.right() - self.width()
        self.begin_travel(tx, self.y(), stroll=False)

    def start_stroll(self):
        """散步：在屏幕上随机漫游(目标点随机，高度也随机变化)"""
        self.pick_waypoint()

    def pick_waypoint(self):
        geo = QApplication.primaryScreen().availableGeometry()
        x, y = self.x(), self.y()
        tx = x
        for _ in range(20):
            tx = random.randint(geo.left(), geo.right() - self.width())
            if abs(tx - x) >= 160:
                break
        # 高度沿行走斜线渐变，坡度不超过 0.3，看起来像走上/下坡
        max_dy = max(int(abs(tx - x) * 0.3), 1)
        ty = y + random.randint(-max_dy, max_dy)
        ty = min(max(ty, geo.top()), geo.bottom() - self.height())
        self.begin_travel(tx, ty, stroll=True)

    def begin_travel(self, tx: int, ty: int, stroll: bool):
        self.walk_target = (tx, ty)
        self.walk_stroll = stroll
        self.play_sound(chance=0.58)
        q = 1 if tx < self.x() else 3
        self.facing_then(q, self._launch_walk)

    def _launch_walk(self):
        tx, ty = self.walk_target
        self.fx, self.fy = float(self.x()), float(self.y())
        dist = max(abs(tx - self.fx), 1.0)
        self.vx = WALK_SPEED if tx > self.fx else -WALK_SPEED
        raw_vy = (ty - self.fy) * WALK_SPEED / dist
        max_vy = WALK_SPEED * 0.6
        self.vy = max(-max_vy, min(raw_vy, max_vy))
        self.facing = 1 if self.vx < 0 else 3
        self.set_state("walk")

    def finish_walk(self):
        """停下：转回正面站好"""
        self.turn_to(0, done=self.face_idle)

    # ---------- 跑步 ----------
    def start_run(self, direction: str = None):
        """跑步到屏幕上随机一点（方向指定时跑到那一侧边缘）"""
        geo = QApplication.primaryScreen().availableGeometry()
        if direction in ("run_left", "run_right"):
            tx = geo.left() if direction == "run_left" else geo.right() - self.width()
            ty = self.y()
        else:
            # 随机目标点，水平和散步类似但有更大偏移
            x, y = self.x(), self.y()
            for _ in range(20):
                tx = random.randint(geo.left(), geo.right() - self.width())
                if abs(tx - x) >= 200:
                    break
            max_dy = max(int(abs(tx - x) * 0.3), 1)
            ty = y + random.randint(-max_dy, max_dy)
            ty = min(max(ty, geo.top()), geo.bottom() - self.height())
        self.run_target = (tx, ty)
        self.fx, self.fy = float(self.x()), float(self.y())
        dist = max(abs(tx - self.fx), 1.0)
        self.vx = RUN_SPEED if tx > self.fx else -RUN_SPEED
        raw_vy = (ty - self.fy) * RUN_SPEED / dist
        max_vy = RUN_SPEED * 0.6
        self.vy = max(-max_vy, min(raw_vy, max_vy))
        self.facing = 1 if self.vx < 0 else 3
        self.play_sound(chance=0.7)
        self.set_state("run")

    def finish_run(self):
        """跑完：转回正面站好"""
        self.turn_to(0, done=self.face_idle)

    def stop_walk(self):
        """菜单"停止运动"：行走/跑步中或正转身准备走时都能停；跟随模式也关掉"""
        self.follow_mouse = False
        self._follow_timer.stop()
        if self.state == "walk":
            self.finish_walk()
        elif self.state == "run":
            self.finish_run()
        elif self.state == "turn" and self.turn_done == self._launch_walk:
            self.turn_done = None
            self.turn_to(0)

    # ---------- 悠闲坐窗 ----------
    def _try_snap_to_window(self):
        """枚举所有可见窗口，找上沿最接近菲比脚底的目标；全部物理坐标，DPI 无关"""
        # 1) 菲比自身物理矩形
        my = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(int(self.winId()), ctypes.byref(my)):
            return False
        phy_bottom = my.bottom
        phy_cx = (my.left + my.right) // 2
        phy_h = max(my.bottom - my.top, 1)

        self_id = int(self.winId())

        # 2) 物理 ↔ 逻辑 映射参数
        s = self.height() / phy_h            # 缩放比
        ox = self.x() - s * my.left          # X 偏移
        oy = self.y() - s * my.top           # Y 偏移

        def phy_to_log_x(px):
            return int(px * s + ox)
        def phy_to_log_y(py):
            return int(py * s + oy)

        # 3) 枚举所有窗口，找最佳候选
        best_dist = SNAP_RANGE + 1
        best_rect = None   # (left, top, right, bottom) 均为物理像素
        best_hwnd = 0

        def cb(hwnd, _):
            nonlocal best_dist, best_rect, best_hwnd
            if int(hwnd) == self_id:                    # 跳过自己
                return True
            if not ctypes.windll.user32.IsWindowVisible(hwnd):
                return True
            r = wintypes.RECT()
            if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r)):
                return True
            w, h = r.right - r.left, r.bottom - r.top
            if w < 80 or h < 40:                         # 太小忽略
                return True
            d = abs(phy_bottom - r.top)
            if d >= best_dist:                           # 不是更好的候选
                return True
            if phy_cx < r.left - 200 or phy_cx > r.right + 200:  # 横向不对齐
                return True
            best_dist = d
            best_rect = (r.left, r.top, r.right, r.bottom)
            best_hwnd = int(hwnd)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(cb), 0)

        if best_rect is None:
            return False

        r_left, r_top, r_right, r_bottom = best_rect

        # 4) 全屏/最大化 → 不坐
        log_w = phy_to_log_x(r_right) - phy_to_log_x(r_left)
        log_h = phy_to_log_y(r_bottom) - phy_to_log_y(r_top)
        geo = QApplication.primaryScreen().availableGeometry()
        if log_w * log_h >= geo.width() * geo.height() * 0.95:
            return False

        # 5) 贴边吸附 + 记录目标窗口以便跟随
        new_y = phy_to_log_y(r_top) - self.height() + 25
        self.move(self.x(), new_y)
        self._lounge_hwnd = best_hwnd
        self._lounge_x_off = self.x() - phy_to_log_x(r_left)   # X 相对窗口左沿偏移
        self._enter_lounge()
        self._lounge_timer.start(50)                            # 每 50ms 追踪窗口
        return True

    def _enter_lounge(self):
        self.facing = 0                # lounge 动画是正面坐姿
        self.set_state("lounge")
        self.frame_i = 0
        self._lounge_until = time.monotonic() + random.uniform(LOUNGE_MIN_S, LOUNGE_MAX_S)
        self.play_sound(chance=0.70)
        # 重置发声冷却，避免 lounge 期间周期性叫声被 8s 冷却全部吃掉
        self.last_sound = time.monotonic() - 10.0

    def _exit_lounge(self):
        """从窗口上沿滑下来，回到屏幕可用区域内"""
        self._lounge_timer.stop()
        self._lounge_hwnd = 0
        geo = QApplication.primaryScreen().availableGeometry()
        y = min(self.y() + 30, geo.bottom() - self.height())
        self.move(self.x(), y)
        self.facing = 0
        self.face_idle()

    def _lounge_track(self):
        """定时追踪目标窗口：窗口移动 → 跟着动；窗口消失/最大化 → 退坐"""
        hwnd = self._lounge_hwnd
        if not hwnd:
            self._exit_lounge()
            return
        # 窗口是否还在
        if not ctypes.windll.user32.IsWindow(hwnd):
            self._exit_lounge()
            return
        # 取目标物理矩形
        r = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r)):
            self._exit_lounge()
            return
        # 菲比自身物理矩形（做 DPI 映射）
        my = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(int(self.winId()), ctypes.byref(my)):
            self._exit_lounge()
            return
        phy_h = max(my.bottom - my.top, 1)
        s = self.height() / phy_h
        ox = self.x() - s * my.left
        oy = self.y() - s * my.top

        def px(phy_x):
            return int(phy_x * s + ox)
        def py(phy_y):
            return int(phy_y * s + oy)

        log_w = px(r.right) - px(r.left)
        log_h = py(r.bottom) - py(r.top)
        geo = QApplication.primaryScreen().availableGeometry()
        # 全屏/最大化 → 退坐
        if log_w * log_h >= geo.width() * geo.height() * 0.95:
            self._exit_lounge()
            return

        new_x = px(r.left) + self._lounge_x_off
        new_y = py(r.top) - self.height() + 25
        self.move(new_x, new_y)

    # ---------- 跟随鼠标 ----------
    def _toggle_follow_mouse(self, checked: bool):
        self.follow_mouse = checked
        if checked:
            # 无帽状态先恢复帽子，再开始跟随
            if self.hatless:
                self.restore_hat()
            self._follow_timer.start()
            # 立即朝鼠标走
            self._follow_tick()
        else:
            self._follow_timer.stop()
            if self.state == "walk":
                self.finish_walk()
            elif self.state == "run":
                self.finish_run()

    def _follow_tick(self):
        """每 200ms：远跑近走，到了停；接近时比例降速防过冲"""
        if not self.follow_mouse or self.dragging:
            return
        if self.state in ("turn", "spin", "hop", "sit", "lounge"):
            return
        self.play_sound(chance=0.04)
        cursor = QCursor.pos()
        tx = cursor.x() - self.width() // 2
        ty = cursor.y() - self.height() // 2
        dx = tx - self.x()
        dy = ty - self.y()
        dist = (dx * dx + dy * dy) ** 0.5
        # 足够近 → 停下转身
        if dist < 45:
            if self.state in ("walk", "run"):
                self._follow_finish_turn()
            return
        # 横轴很接近时只做纯纵向移动，杜绝横向抖动引发 vy 反复重算
        if abs(dx) < 30:
            tx = self.x()
            dx = 0
            dist = abs(dy)
        want_state = "run" if dist > 200 else "walk"
        speed = RUN_SPEED if want_state == "run" else WALK_SPEED
        # 比例降速：越近越慢，避免过冲
        if dist < 120:
            speed *= max(0.35, dist / 120)
        self.walk_target = (tx, ty)
        self.run_target = (tx, ty)
        # 计算速度：有横向偏移时 vx/vy 联动(保持移动方向与目标一致)；
        # dx==0(纯纵向)时 vx=0，vy 由 speed 直接给出，避免浮点取整导致方向乱拐
        if dx != 0:
            self.vx = speed if tx > self.fx else -speed
            nd = max(abs(tx - self.fx), 1.0)
            raw_vy = (ty - self.fy) * abs(self.vx) / nd
            max_vy = speed * 0.55
            self.vy = max(-max_vy, min(raw_vy, max_vy))
        else:
            self.vx = 0
            self.vy = speed * 0.55 * (1 if ty > self.fy else -1)
        if self.state == "idle":
            self.walk_stroll = True
            # 跟随模式不从 _launch_walk 走（它会用 WALK_SPEED 覆盖比例降速后的 vx/vy）
            self.fx, self.fy = float(self.x()), float(self.y())
            self.facing = 1 if self.vx < 0 else 3
            self.set_state("walk")
            if want_state == "run":
                self.set_state("run")
        elif self.state != want_state:
            self.set_state(want_state)

    def _follow_finish_turn(self):
        """跟随模式追到鼠标后转身回正面——用 vx 修正 facing 兜底"""
        # 确保 facing 和实际行走方向一致，避免偶尔方向错
        if self.vx > 0:
            self.facing = 3
        elif self.vx < 0:
            self.facing = 1
        # vx == 0 保持当前 facing，直接站好
        if self.facing != 0:
            self.turn_to(0, done=self.face_idle)
        else:
            self.face_idle()

    # ---------- 帧循环 ----------
    def tick(self):
        if self.state == "walk":
            self.frame_i += 1
            anim = "walk_left" if self.vx < 0 else "walk_right"
            self.show_frame(anim, self.frame_i)
            geo = QApplication.primaryScreen().availableGeometry()
            self.fx += self.vx
            self.fy += self.vy
            self.fy = min(max(self.fy, geo.top()), geo.bottom() - self.height())
            self.move(int(self.fx), int(self.fy))
            tx, _ = self.walk_target
            arrived = (self.vx > 0 and self.fx >= tx) or (self.vx < 0 and self.fx <= tx)
            if arrived:
                if self.follow_mouse:
                    pass   # 跟随鼠标：由 _follow_tick 持续刷新目标，这里不干预
                elif self.walk_stroll and random.random() < 0.6:
                    self.pick_waypoint()      # 换个目标继续溜达(必要时带转身)
                elif not self.walk_stroll:
                    # 走到边缘：转身沿原高度往回走
                    ntx = geo.left() if self.vx > 0 else geo.right() - self.width()
                    self.begin_travel(ntx, int(self.fy), stroll=False)
                else:
                    self.finish_walk()
            elif not self.follow_mouse and self.frame_i % self.anim_len(anim) == 0 and random.random() < 0.25:
                self.finish_walk()
        elif self.state == "run":
            self.frame_i += 1
            anim = "run_left" if self.vx < 0 else "run_right"
            self.show_frame(anim, self.frame_i)
            geo = QApplication.primaryScreen().availableGeometry()
            self.fx += self.vx
            self.fy += self.vy
            self.fy = min(max(self.fy, geo.top()), geo.bottom() - self.height())
            self.move(int(self.fx), int(self.fy))
            tx, _ = self.run_target
            arrived = (self.vx > 0 and self.fx >= tx) or (self.vx < 0 and self.fx <= tx)
            if arrived:
                if self.follow_mouse:
                    pass   # 跟随鼠标继续刷新
                else:
                    self.finish_run()
        elif self.state == "turn":
            if self.turn_i < len(self.turn_seq):
                self.show_frame("spin", self.turn_seq[self.turn_i])
                self.turn_i += 1
            else:
                self.facing = self.turn_target
                cb, self.turn_done = self.turn_done, None
                if cb:
                    cb()
                else:
                    self.face_idle()
        elif self.state == "spin":
            self.frame_i += 1
            if self.frame_i >= self.anim_len("spin"):
                self.facing = 0
                self.face_idle()
            else:
                self.show_frame("spin", self.spin_frame_idx())
        elif self.state == "hop":
            self.frame_i += 1
            if self.frame_i >= self.anim_len("hop") * self.hop_loops:
                self.facing = 0
                self.face_idle()
            else:
                self.show_frame("hop", self.frame_i)
        elif self.state == "lounge":
            n = min(self.anim_len("lounge"), LOUNGE_FRAMES)
            self.frame_i = (self.frame_i + 1) % n
            self.show_frame("lounge", self.frame_i)
            # 到时间了自己跳下来
            if time.monotonic() >= self._lounge_until:
                self._exit_lounge()

    # ---------- 随机行为 ----------
    def random_behavior(self):
        if self.dragging or self.follow_mouse or self.state in ("spin", "turn", "drag", "hop", "run"):
            return
        # 悠闲坐窗时只发声，不切换行为
        if self.state == "lounge":
            self.play_sound(chance=0.50)
            return
        # 走路/跑步时短促地叫；静止时隔段时间说一次话，正面站立还会配举手/小跳动作
        if self.state == "walk":
            self.play_sound(chance=0.23)
        elif self.state == "idle" and self.idle_pose == "front":
            if self.hatless:
                self.play_sound(chance=0.45)  # 无帽时只叫，不做动作(缺素材)
            elif self.vocal_gesture(chance=0.5):
                return       # 正在举手/小跳，本轮不再切换行为
        else:
            self.play_sound(chance=0.33)
        if time.monotonic() < self.hold_until:
            return
        r = random.random()
        if self.state == "walk":
            if r < 0.25:
                self.finish_walk()
            return
        if r < 0.22:
            self.start_stroll()
        elif r < 0.30:
            self.request(self.start_run)
        elif r < 0.41:
            self.facing_then(0, self.start_spin)
        elif r < 0.56:
            self.facing_then(0, self._pose_sit)
        elif r < 0.80:
            # 随机换姿势，跨朝向时播转身动画；背对用户的姿势压低概率
            pose = random.choices(
                ["front", "hands_on_hips", "look_up", "side_left", "side_right", "back"],
                weights=[30, 18, 18, 13, 13, 8])[0]
            q = FACE_POSE.index(pose) if pose in FACE_POSE else 0
            def show():
                self.idle_pose = pose
                self.set_state("idle")
            self.facing_then(q, show)
        else:
            self.facing_then(0, self.face_idle)

    # ---------- 交互 ----------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            # 连击计时计次：0.5s 窗口内累加 → 2 次双击叫声 / 3 次打飞帽子
            now = time.monotonic()
            if now - self._last_click_time < 0.5:
                self._click_count += 1
            else:
                self._click_count = 1
            self._last_click_time = now

            if self._click_count == 2:
                self.double_bark()                     # 双击：立即叫

            if self._click_count >= 3 and self._can_knock_hat():
                self._click_count = 0                  # 三连击：打飞帽子
                self.knock_hat_off()
                e.accept()
                return

            # 只有首次点击才准备拖拽；双击/三击期间不拖
            if self._click_count == 1:
                self.drag_offset = e.globalPos() - self.frameGeometry().topLeft()
                if self.state == "lounge":
                    self._exit_lounge()                   # 拖走：从窗边下来
            e.accept()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton and self.drag_offset is not None:
            if not self.dragging:
                self.dragging = True
                self.turn_done = None     # 拖拽优先，取消未完成的行程
                self.facing = 0
                self.set_state("drag")
            self.move(e.globalPos() - self.drag_offset)
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.drag_offset = None
            if self.dragging:
                self.dragging = False
                # 松手时检测是否拖到了窗口上边缘 → 悠闲坐
                if self._try_snap_to_window():
                    e.accept()
                    return
                self.face_idle()
            e.accept()


    def _style_menu(self, menu: QMenu):
        """无边框+透明底，让 QSS 圆角真正生效(否则圆角外会露出方形黑底)"""
        menu.setWindowFlags(menu.windowFlags()
                            | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        menu.setAttribute(Qt.WA_TranslucentBackground)

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_QSS)   # 子菜单自动继承样式
        self._style_menu(menu)

        # --- 运动 ---
        move_menu = menu.addMenu("🏃  运动")
        self._style_menu(move_menu)
        move_menu.addAction("散步", lambda: self.request(self.start_stroll))
        move_menu.addAction("向左走", lambda: self.request(lambda: self.start_walk("walk_left")))
        move_menu.addAction("向右走", lambda: self.request(lambda: self.start_walk("walk_right")))
        move_menu.addSeparator()
        move_menu.addAction("跑步", lambda: self.request(self.start_run))
        move_menu.addAction("向左跑", lambda: self.request(lambda: self.start_run("run_left")))
        move_menu.addAction("向右跑", lambda: self.request(lambda: self.start_run("run_right")))
        move_menu.addSeparator()
        move_menu.addAction("停止运动", self.stop_walk)

        # --- 动作 ---
        act_menu = menu.addMenu("✨  动作")
        self._style_menu(act_menu)
        act_menu.addAction("抬头", lambda: self.request(
            lambda: self.facing_then(0, self._pose_lookup)))
        act_menu.addAction("坐下", lambda: self.request(
            lambda: self.facing_then(0, self._pose_sit)))
        act_menu.addAction("叉腰", lambda: self.request(
            lambda: self.facing_then(0, self._pose_hands)))
        act_menu.addAction("站好", lambda: self.request(
            lambda: self.facing_then(0, self.face_idle)))
        act_menu.addAction("随机声音", lambda: self.play_sound(force=True))

        # --- 方向 ---
        dir_menu = menu.addMenu("🧭  方向")
        self._style_menu(dir_menu)
        dir_menu.addAction("向左旋转90°", lambda: self.request(
            lambda: self.turn_to((self.facing + 1) % 4)))
        dir_menu.addAction("向右旋转90°", lambda: self.request(
            lambda: self.turn_to((self.facing + 3) % 4)))

        # 跟随鼠标
        menu.addSeparator()
        follow = QAction("🖱️  跟随鼠标", menu, checkable=True)
        follow.setChecked(self.follow_mouse)
        follow.triggered.connect(self._toggle_follow_mouse)
        menu.addAction(follow)

        # 帽子切换：有帽 → 没礼帽打飞 / 无帽 → 有礼帽戴回
        menu.addSeparator()
        if self.hatless:
            menu.addAction("🎩  有礼帽", self.restore_hat)
        else:
            knock = menu.addAction("🎩  没礼帽", self.knock_hat_off)
            knock.setEnabled(not self.follow_mouse)   # 跟随中禁无帽

        # 设置
        menu.addSeparator()
        opt_menu = menu.addMenu("⚙️  设置")
        self._style_menu(opt_menu)
        bigger = QAction("变大", opt_menu)
        bigger.setEnabled(self.pet_h < SIZE_STEPS[-1])
        bigger.triggered.connect(lambda: self.step_size(+1))
        opt_menu.addAction(bigger)
        smaller = QAction("变小", opt_menu)
        smaller.setEnabled(self.pet_h > SIZE_STEPS[0])
        smaller.triggered.connect(lambda: self.step_size(-1))
        opt_menu.addAction(smaller)
        # 直接拖拽的缩放条
        slider = QSlider(Qt.Horizontal, opt_menu)
        slider.setRange(SIZE_MIN, SIZE_MAX)
        slider.setValue(self.pet_h)
        slider.setFixedWidth(160)
        slider.valueChanged.connect(self.queue_size)
        size_act = QWidgetAction(opt_menu)
        size_act.setDefaultWidget(slider)
        opt_menu.addAction(size_act)
        top = QAction("总在最前", opt_menu, checkable=True)
        top.setChecked(bool(self.windowFlags() & Qt.WindowStaysOnTopHint))
        top.triggered.connect(self.toggle_topmost)
        opt_menu.addAction(top)
        quiet = QAction("安静一点", opt_menu, checkable=True)
        quiet.setChecked(self.quiet)
        quiet.triggered.connect(lambda c: setattr(self, "quiet", c))
        opt_menu.addAction(quiet)
        # 叫声频率缩放条：0.2x ~ 2x，默认 1x(即当前状态)
        freq_label = QAction("叫声频率", opt_menu)
        freq_label.setEnabled(False)
        opt_menu.addAction(freq_label)
        fslider = QSlider(Qt.Horizontal, opt_menu)
        fslider.setRange(20, 200)
        fslider.setValue(int(self.sound_freq * 100))
        fslider.setFixedWidth(160)
        fslider.valueChanged.connect(lambda v: setattr(self, "sound_freq", v / 100.0))
        freq_act = QWidgetAction(opt_menu)
        freq_act.setDefaultWidget(fslider)
        opt_menu.addAction(freq_act)

        menu.addSeparator()
        menu.addAction("👋  退出", QApplication.quit)
        menu.exec_(e.globalPos())

    def _pose_hands(self):
        self.idle_pose = "hands_on_hips"
        self.hold_until = time.monotonic() + 8.0   # 叉腰多停留一会儿
        self.play_sound(chance=0.8)
        self.set_state("idle")

    def _pose_lookup(self):
        self.idle_pose = "look_up"
        self.play_sound(chance=0.8)
        self.set_state("idle")

    def _pose_sit(self):
        self.play_sound(chance=0.8)
        self.set_state("sit")
        # 坐得久一些，并且坐一会儿后(还坐着的话)再叫一声
        self.hold_until = time.monotonic() + random.uniform(10.0, 16.0)
        QTimer(self, interval=random.randint(6000, 10000), singleShot=True,
               timeout=self._sit_bark).start()

    def _sit_bark(self):
        if self.state == "sit":
            self.play_sound(chance=0.9)

    # ---------- 打飞帽子 ----------
    def _can_knock_hat(self) -> bool:
        """三连击仅对正面站立/坐着的有帽菲比生效；跟随模式下禁止"""
        if self.hatless or self.dragging or self.follow_mouse:
            return False
        if self.state == "idle" and self.idle_pose == "front":
            return True
        if self.state == "sit":
            return True
        return False

    def knock_hat_off(self):
        """帽子被打飞：切换无帽素材 + 帽子飞出抛物线 + 叫声放开"""
        if "hat" not in self._raw_poses:
            return
        # 跟随模式下不允许无帽（无帽走路/跑步素材缺失）
        if self.follow_mouse:
            return
        # 清理旧帽子窗口（如果存在）
        if self.hat_widget:
            self.hat_widget.close()
            self.hat_widget = None
        self.hatless = True
        # 长时间锁住，帽子消失后自动恢复(帽子飞行期 + 淡出期 3s)
        self.hold_until = time.monotonic() + HAT_FADE_AFTER + 3.0
        # 先停旧定时器，再创建新的
        if self._restore_timer:
            self._restore_timer.stop()
            self._restore_timer = None
        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self._auto_restore_hat)
        self._restore_timer.start(int((HAT_FADE_AFTER + 3.0) * 1000))

        # 切换无帽显示
        if self.state == "sit":
            self.set_state("sit")
        else:
            self.facing = 0
            self.idle_pose = "front"
            self.set_state("idle")
            # TODO: 如果未来有无帽举手/叉腰/小跳等素材，这里不需要锁朝向
            #       目前只有正面和坐下的无帽版，所以锁正面站立

        # 创建帽子窗口并发射
        # 抠图脚本底部对齐，帽子在画布底部；扫描实际内容区域后裁剪
        hat_full = self.pose_pix("hat")
        hat_img = hat_full.toImage()
        content_top = hat_full.height()
        for y in range(hat_full.height()):
            for x in range(0, hat_full.width(), 2):  # 隔列采样
                if hat_img.pixelColor(x, y).alpha() > 10:
                    content_top = y
                    break
            if content_top < hat_full.height():
                break
        content_bottom = 0
        for y in range(hat_full.height() - 1, -1, -1):
            for x in range(0, hat_full.width(), 2):
                if hat_img.pixelColor(x, y).alpha() > 10:
                    content_bottom = y
                    break
            if content_bottom > 0:
                break
        if content_top < hat_full.height():
            hat_h = content_bottom - content_top + 1
            hat_pm = hat_full.copy(0, content_top, hat_full.width(), hat_h)
        else:
            hat_pm = hat_full
        self.hat_widget = HatWidget(self)
        self.hat_widget.set_hat_pixmap(hat_pm)
        # 帽子起始位置：菲比头顶中心(屏幕坐标)
        hat_x = self.x() + self.width() // 2 - hat_pm.width() // 2
        hat_y = self.y() + int(self.pet_h * 0.02)  # 头顶偏上一点
        self.hat_widget.launch(hat_x, hat_y)
        # 打飞瞬间叫一声(用菲八啾比)
        self._play_special("egg")

    def _auto_restore_hat(self):
        """定时器回调：帽子自己消失了且玩家没拖回 → 恢复有帽"""
        if self.hatless:
            self.restore_hat()

    def closeEvent(self, e):
        if self.hat_widget:
            self.hat_widget.close()
        # 清理 .pak 解压出来的临时素材目录
        try:
            import tempfile, shutil
            _PT = os.path.join(tempfile.gettempdir(), "phoebe_pet_assets")
            if os.path.isdir(_PT):
                shutil.rmtree(_PT)
        except:
            pass
        super().closeEvent(e)

    def _try_reattach_hat(self, hat: HatWidget) -> bool:
        """检查帽子是否被拖到菲比头上(距离<宠物体高的40%)，是则戴回"""
        if not self.hatless:
            return False
        hcx = hat.x() + hat.width() // 2
        hcy = hat.y() + hat.height() // 2
        pcx = self.x() + self.width() // 2
        pcy = self.y() + int(self.pet_h * 0.2)  # 头部区域中心
        dist = ((hcx - pcx) ** 2 + (hcy - pcy) ** 2) ** 0.5
        if dist < self.pet_h * 0.55:
            self.restore_hat()
            return True
        return False

    def restore_hat(self):
        """帽子戴回：恢复有帽状态，帽子窗口消失"""
        self.hatless = False
        self.hold_until = 0.0
        if self._restore_timer:
            self._restore_timer.stop()
            self._restore_timer = None
        if self.hat_widget:
            self.hat_widget.close()
            self.hat_widget = None
        # 刷新显示
        if self.state == "sit":
            self.set_state("sit")
        else:
            self.facing = 0
            self.idle_pose = "front"
            self.set_state("idle")

    def _play_special(self, group: str):
        """特殊叫声：不受全局冷却/概率限制，直接播放"""
        pool = {"egg": self.sounds_egg,
                "all": self.sounds_all + self.sounds_egg}.get(group)
        if pool:
            self._play(random.choice(pool), echo=True)

    def toggle_topmost(self, checked):
        flags = self.windowFlags()
        if checked:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    icon_path = os.path.join(ASSETS, "poses", "front.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    pet = PhoebePet()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
