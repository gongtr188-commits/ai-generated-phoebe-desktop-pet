# -*- coding: utf-8 -*-
"""在桌面生成 GBK 编码的启动 bat(cmd 默认代码页为 936，直接写 UTF-8 中文路径会乱码)"""
import os

desktop = os.path.join(os.path.expanduser("~"), "Desktop")
project = os.path.join(desktop, "Qoder菲比桌宠")
content = (
    f'@start "" /d "{project}" pythonw phoebe_pet.py\r\n'
)
target = os.path.join(desktop, "启动菲比桌宠.bat")
with open(target, "w", encoding="gbk", newline="") as f:
    f.write(content)
print("created:", target)
