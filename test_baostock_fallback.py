"""
测试 BaoStock 备选数据源
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.data.data_fetcher import ShortTermDataFetcher
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

print("="*80)
print("测试 BaoStock 备选数据源")
print("="*80)

fetcher = ShortTermDataFetcher(use_cache=False, rate_limit=0.5)

# 测试几只股票
test_stocks = ['000001.SZ', '600519.SS', '000858.SZ']

for symbol in test_stocks:
    print(f"\n测试股票: {symbol}")
    try:
        data = fetcher.get_stock_history(symbol, period='1mo')
        if not data.empty:
            print(f"  [OK] 成功: {len(data)} 条数据")
            print(f"  最新收盘价: {data['close'].iloc[-1]:.2f}")
        else:
            print(f"  [FAIL] 返回空数据")
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")

print("\n" + "="*80)
print("测试完成")
print("="*80)
