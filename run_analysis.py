"""
快捷分析脚本 - 一键运行不同时间段的分析
"""
import subprocess
import sys
import os
from datetime import datetime, time
import argparse

def get_current_session():
    """获取当前时间段"""
    now = datetime.now().time()
    
    if time(9, 30) <= now < time(10, 0):
        return "morning_open"
    elif time(10, 0) <= now < time(11, 30):
        return "morning_mid"
    elif time(11, 30) <= now < time(13, 0):
        return "noon_break"
    elif time(13, 0) <= now < time(14, 0):
        return "afternoon_early"
    elif time(14, 0) <= now < time(14, 30):
        return "afternoon_mid"
    elif time(14, 30) <= now < time(15, 0):
        return "closing"
    elif time(15, 0) <= now:
        return "post_market"
    elif time(0, 0) <= now < time(9, 30):
        return "pre_market"
    else:
        return "general"

def run_analysis(session_type=None):
    """
    运行分析
    
    Args:
        session_type: 分析类型（auto, morning, noon, afternoon, closing, post, pre, weekend）
    """
    # 自动检测时间段
    if session_type == "auto" or session_type is None:
        session_type = get_current_session()
    
    print(f"🎯 运行 {session_type} 分析")
    print(f"⏰ 当前时间: {datetime.now().strftime('%H:%M:%S')}")
    
    # 构建命令
    cmd = [sys.executable, "analyze_anytime.py"]
    
    # 运行分析
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        print("\n" + "="*80)
        print("分析输出:")
        print("="*80)
        print(result.stdout)
        
        if result.stderr:
            print("\n错误信息:")
            print(result.stderr)
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='全时段市场分析系统')
    parser.add_argument('--mode', choices=['auto', 'morning', 'noon', 'afternoon', 
                                         'closing', 'post', 'pre', 'weekend', 'general'],
                       default='auto', help='分析模式（默认auto自动检测）')
    
    args = parser.parse_args()
    
    print("="*80)
    print("🚀 启动全时段市场分析")
    print("="*80)
    
    # 运行分析
    success = run_analysis(args.mode)
    
    if success:
        print("\n✅ 分析完成")
    else:
        print("\n❌ 分析失败")
    
    print("="*80)

if __name__ == "__main__":
    main()
