"""
个股筛选器测试
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_fetcher import ShortTermDataFetcher
from src.core.stock_filter import StockFilter

def test_stock_filter():
    """测试个股筛选器"""
    print("🧪 测试个股筛选器...")
    
    # 初始化
    data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.5)
    stock_filter = StockFilter(data_fetcher)
    
    # 测试板块
    test_sector = "有色金属"
    
    print(f"测试板块: {test_sector}")
    print("-" * 50)
    
    # 筛选个股
    filtered_stocks = stock_filter.filter_stocks_in_sector(
        test_sector, 
        max_stocks=5,
        strict_mode=False  # 测试时用宽松模式
    )
    
    if filtered_stocks:
        print(f"找到 {len(filtered_stocks)} 只符合条件的股票:")
        for i, stock in enumerate(filtered_stocks, 1):
            print(f"\n{i}. {stock['name']} ({stock['symbol']})")
            print(f"   评分: {stock['total_score']}")
            print(f"   价格: {stock['price']:.2f}")
            print(f"   理由: {', '.join(stock['rank_reasons'])}")
            
            # 显示详细分析（可选）
            if 'analysis_details' in stock:
                details = stock['analysis_details']
                print(f"   趋势分: {details.get('trend', {}).get('score', 0)}")
                print(f"   动量分: {details.get('momentum', {}).get('score', 0)}")
                print(f"   波动率: {details.get('volatility', {}).get('details', {}).get('annual_volatility', 0):.3f}")
    else:
        print("未找到符合条件的股票")
    
    return filtered_stocks

if __name__ == "__main__":
    test_stock_filter()