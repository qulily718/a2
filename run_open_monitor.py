"""
自动运行开盘监控脚本

用途：可放入 Windows 任务计划，在 9:28-9:50 定时触发。
该脚本会判断是否处于监控窗口，满足则执行 monitor_open_market.py。
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime


def run_open_monitor() -> bool:
    now = datetime.now()

    # 只在工作日运行（简单判断；节假日不在此处理）
    if now.weekday() >= 5:
        print(f"非交易日（周末）：{now.strftime('%Y-%m-%d %H:%M:%S')}，跳过")
        return False

    # 建议 9:28-9:50 之间触发
    if not (now.hour == 9 and 28 <= now.minute <= 50):
        print(f"非建议触发时间：{now.strftime('%H:%M')}，跳过")
        return False

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "monitor_open_market.py")
    print(f"开始执行: {script_path}")

    try:
        result = subprocess.run(
            [sys.executable, script_path, "--force"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        print("=" * 90)
        print("输出:")
        print(result.stdout)
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"执行失败: {e}")
        return False


if __name__ == "__main__":
    print("开盘监控自动运行脚本")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    ok = run_open_monitor()
    print("执行结果:", "成功" if ok else "失败/跳过")

