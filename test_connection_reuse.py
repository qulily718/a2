"""
测试 BaoStock 连接复用优化
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data.data_fetcher import ShortTermDataFetcher
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("="*80)
print("测试 BaoStock 连接复用优化")
print("="*80)

fetcher = ShortTermDataFetcher(use_cache=False, rate_limit=0.3)

# 测试多只股票（应该只 login 一次）
test_stocks = ['000001.SZ', '600519.SS', '000858.SZ']

print("\n批量获取多只股票数据（应该只看到一次 login）...")
for symbol in test_stocks:
    print(f"\n获取 {symbol}...")
    try:
        data = fetcher.get_stock_history(symbol, period='1mo')
        if not data.empty:
            print(f"  [OK] 成功: {len(data)} 条数据")
        else:
            print(f"  [FAIL] 返回空数据")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")

# 关闭连接
print("\n关闭连接...")
fetcher.close()

print("\n" + "="*80)
print("测试完成")
print("="*80)
print("\n说明：如果看到多次 'login success!'，说明连接没有复用")
print("      如果只看到一次 'login success!'，说明连接复用成功")
