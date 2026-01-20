# test_known_stocks.py
"""
测试已知有效的股票数据
"""
import akshare as ak
import pandas as pd
from datetime import datetime
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_akshare_direct():
    """直接测试akshare接口"""
    print("=== 直接测试akshare接口 ===")
    
    # 测试几个已知的股票
    test_cases = [
        ("000001", "000001.SZ", "平安银行"),
        ("600519", "600519.SS", "贵州茅台"),
        ("000858", "000858.SZ", "五粮液"),
        ("600036", "600036.SS", "招商银行"),
        ("002415", "002415.SZ", "海康威视"),
    ]
    
    for code, symbol, name in test_cases:
        print(f"\n测试股票: {symbol} ({name})")
        
        # 获取最近一个月的数据
        end_date = datetime.now()
        # 如果是周末，调整到上一个交易日
        while end_date.weekday() >= 5:
            end_date = end_date - pd.Timedelta(days=1)
        
        start_date = end_date - pd.Timedelta(days=30)
        
        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                adjust="qfq"
            )
            
            if df is not None and not df.empty:
                print(f"  成功获取 {len(df)} 条数据")
                
                # 查看列名
                print(f"  列名: {list(df.columns)}")
                
                # 查看最近3天
                if len(df) >= 3:
                    print(f"  最近3天数据:")
                    for i in range(min(3, len(df))):
                        row = df.iloc[-1-i]
                        # 尝试找到日期和收盘价列
                        date_val = row.iloc[0] if len(row) > 0 else 'N/A'
                        close_val = None
                        for j, col in enumerate(df.columns):
                            if '收盘' in str(col) or 'close' in str(col).lower():
                                close_val = row.iloc[j] if j < len(row) else 'N/A'
                                break
                        if close_val is None and len(row) > 2:
                            close_val = row.iloc[2]
                        print(f"    {date_val}: 收盘价={close_val}")
            else:
                print(f"  获取失败或数据为空")
                
        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()

def test_our_fetcher():
    """测试我们的数据获取器"""
    print("\n\n=== 测试我们的数据获取器 ===")
    
    # 导入我们的fetcher
    from src.data.data_fetcher import ShortTermDataFetcher
    
    # 初始化日志
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    fetcher = ShortTermDataFetcher(use_cache=False, rate_limit=0.3)
    
    # 测试几个主板股票
    test_stocks = [
        "000001.SZ",  # 平安银行
        "600519.SS",  # 贵州茅台
        "000858.SZ",  # 五粮液
    ]
    
    for symbol in test_stocks:
        print(f"\n测试股票: {symbol}")
        try:
            history = fetcher.get_stock_history(symbol, period="1mo")
            
            if not history.empty:
                print(f"  获取到 {len(history)} 条数据")
                if 'close' in history.columns:
                    valid_close = history['close'].dropna()
                    if len(valid_close) > 0:
                        print(f"  最新收盘价: {valid_close.iloc[-1]}")
                        print(f"  最近日期: {history.index[-1].date()}")
                        print(f"  最早日期: {history.index[0].date()}")
                        
                        # 显示最近3天数据
                        print(f"  最近3天数据:")
                        recent = history[['close']].tail(3)
                        for date, row in recent.iterrows():
                            print(f"    {date.date()}: {row['close']:.2f}")
                    else:
                        print(f"  收盘价数据全为NaN")
            else:
                print(f"  获取失败或数据为空")
        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_akshare_direct()
    test_our_fetcher()
