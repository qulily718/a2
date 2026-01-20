"""
调试脚本：获取并显示AKShare支持的所有行业板块名称
用于验证配置文件中的板块名称是否正确
"""
import sys
import os

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from src.data.data_fetcher import ShortTermDataFetcher

def main():
    print("=" * 80)
    print("AKShare 行业板块名称调试工具")
    print("=" * 80)
    print("\n此工具将显示AKShare支持的所有行业板块名称，")
    print("并检查配置文件中的板块名称是否匹配。")
    print("\n按 Enter 继续...")
    input()
    
    # 创建数据获取器实例
    fetcher = ShortTermDataFetcher(use_cache=False)
    
    # 调用调试函数
    fetcher.debug_print_all_sectors()
    
    print("\n" + "=" * 80)
    print("调试完成")
    print("=" * 80)
    print("\n提示：")
    print("1. 如果配置文件中的板块名称显示为 '✗'，请使用上面列表中显示的准确名称")
    print("2. 将准确的板块名称更新到 config/sectors.yaml 文件中")
    print("3. 板块名称必须完全匹配（区分大小写）")

if __name__ == "__main__":
    main()
