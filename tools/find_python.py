# -*- coding: utf-8 -*-
"""探测本机各 Python 解释器的 cv2/PyQt5 可用性，输出可用解释器路径"""
import glob
import json
import os
import subprocess
import sys

cands = []
cands += glob.glob("D:/*/python/python.exe")
cands += glob.glob(os.path.expanduser("~/AppData/Roaming/uv/python/*/python.exe"))
cands.append(os.path.expanduser("~/.local/bin/python3.11.exe"))

result = []
for p in cands:
    if not os.path.exists(p):
        continue
    def has(mod):
        r = subprocess.run([p, "-c", "import " + mod], capture_output=True)
        return r.returncode == 0
    ver = subprocess.run([p, "-c", "import sys;print(sys.version.split()[0])"],
                         capture_output=True, text=True).stdout.strip()
    info = dict(path=p, ver=ver, cv2=has("cv2"), qt=has("PyQt5"), np=has("numpy"))
    result.append(info)
    print(json.dumps(info))

best = [r for r in result if r["cv2"] and r["qt"]]
print("BEST:", json.dumps(best))
