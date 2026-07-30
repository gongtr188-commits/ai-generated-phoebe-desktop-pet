# -*- coding: utf-8 -*-
"""列出/结束 phoebe_pet 相关 python 进程"""
import subprocess
import sys

out = subprocess.check_output(
    ["powershell", "-NoProfile", "-Command",
     "Get-CimInstance Win32_Process | "
     "Where-Object { $_.CommandLine -like '*phoebe_pet*' -and $_.Name -like 'python*' } | "
     "ForEach-Object { Write-Output ($_.ProcessId.ToString() + ' ' + $_.CommandLine) }"],
    text=True, errors="ignore")

kill = "--kill" in sys.argv
for line in out.splitlines():
    line = line.strip()
    if not line:
        continue
    pid = line.split()[0]
    print("found pet pid:", pid)
    if kill:
        subprocess.run(["taskkill", "/PID", pid, "/F"])
