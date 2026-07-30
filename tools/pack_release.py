# -*- coding: utf-8 -*-
"""
打包发布脚本：把桌面项目整理成可直接使用的压缩包(历次版本回档用)。
只保留运行必需文件：phoebe_pet.py / README.md / 启动菲比.bat / assets / tools，
排除源素材(菲比-素材)、__pycache__、抠图校验图(_preview.png)。

用法: python pack_release.py <项目目录> <输出目录> <版本名>
例:   python pack_release.py "C:\\...\\Qoder菲比桌宠" "D:\\...\\历次版本" v2
"""
import os
import sys
import zipfile

EXCLUDE_DIRS = {"菲比-素材", "__pycache__", "assets"}
EXCLUDE_FILES = {"_preview.png"}

# 打包时自动生成给最终用户看的说明(记事本可直接打开)
USER_GUIDE = """\
【菲比桌面宠物】使用说明
================================

一、这是什么
    一只住在你桌面上的菲比(鸣潮 Q 版)。她会自己在屏幕上散步、
    转身、转圈、坐下、叉腰、抬头发呆，偶尔还会"啾"地叫一声，
    也可以被你随意摆布。

二、运行前准备(只需一次)
    1. 安装 Python 3.8 或更高版本(https://www.python.org/downloads/)
       安装时务必勾选 "Add Python to PATH"。
    2. 打开命令提示符(cmd)，执行：
       pip install PyQt5

三、怎么启动
    双击文件夹里的「启动菲比.bat」即可，没有黑框，菲比直接出现在屏幕上。
    (也可以用命令 python phoebe_pet.py 启动)

四、怎么玩
    左键拖拽    抓起菲比随意摆放，松手后她原地站好
    双击        让她随机叫一声(小概率触发"菲八啾比"彩蛋)
    右键        打开菜单：
                走动 -> 散步 / 向左走 / 向右走 / 向左旋转90° / 向右旋转90° / 停止走动
                动作 -> 抬头 / 坐下 / 叉腰 / 站好 / 随机声音
                设置 -> 变大 / 变小 / 拖动缩放条精细调节 / 总在最前
                        / 安静一点(叫声更少更小声)
                        / 叫声频率条(往左更安静、往右更活泼)
                退出 -> 关闭桌宠
    放着不管    她会自己随机漫游、换姿势、转圈、坐下休息；
                刚出场会打招呼，走路/旋转发短促音，
                静止时隔段时间说一次话(有冷却，不会吵)，
                正面站立说话还会举手或原地小跳着连叫几声

五、退出方法
    右键菲比 -> 退出。

六、常见问题
    Q: 双击 bat 没反应？
    A: 多半是 Python 没装或没加入 PATH，重装 Python 并勾选
       "Add Python to PATH"，再执行 pip install PyQt5。
    Q: 想让她开机自动出现？
    A: 给「启动菲比.bat」创建快捷方式，放进
       C:\\Users\\你的用户名\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup
"""


def main():
    proj, out_dir, ver = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    name = "菲比桌面宠物_" + ver          # 历次版本统一命名：菲比桌面宠物_vN
    zip_path = os.path.join(out_dir, name + ".zip")
    top = name  # 解压后带一层同名目录
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(proj):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if f in EXCLUDE_FILES:
                    continue
                full = os.path.join(root, f)
                rel = os.path.relpath(full, proj)
                zf.write(full, os.path.join(top, rel))
                count += 1
        # 说明文本带 BOM，保证老版记事本也不乱码
        zf.writestr(os.path.join(top, "使用说明.txt"),
                    "\ufeff" + USER_GUIDE.replace("\n", "\r\n"))
        count += 1
    mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"packed {count} files -> {zip_path}  ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
