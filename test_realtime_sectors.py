"""
测试实时板块分析
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_fetcher import ShortTermDataFetcher
from src.core.dynamic_sector_analyzer_v2 import OptimizedDynamicSectorAnalyzer

def test_realtime_sectors():
    """测试实时板块分析"""
    print("🧪 测试实时板块分析...")
    print("=" * 80)
    
    # 初始化
    data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.5)
    analyzer = OptimizedDynamicSectorAnalyzer(data_fetcher)
    
    # 1. 获取实时数据
    print("1. 获取实时板块数据...")
    sector_data = analyzer.get_real_time_sector_data()
    
    if sector_data.empty:
        print("❌ 获取失败")
        return
    
    print(f"✅ 获取到 {len(sector_data)} 个板块")
    print(f"列名: {list(sector_data.columns)}")
    
    # 显示前10个板块
       # 显示前10个板块
    print("\n前10个板块:")
    for i, (_, row) in enumerate(sector_data.head(10).iterrows(), 1):
       change = row.get('change_pct', 0)
       change_str = f"+{change:.2f}%" if change > 0 else f"{change:.2f}%"
       stock_count = row.get('total_count', 'N/A')
       print(f"{i:2d}. {row['sector_name']}: {change_str} (股票数: {stock_count})")
    
    # 2. 计算得分
    print("\n2. 计算板块得分...")
    scored_data = analyzer.calculate_sector_scores(sector_data)
    
    if not scored_data.empty:
        print(f"✅ 计算完成，显示得分最高的5个板块:")
        top_scored = scored_data.nlargest(5, 'total_score')
        for i, (_, row) in enumerate(top_scored.iterrows(), 1):
            print(f"{i}. {row['sector_name']}")
            print(f"   得分: {row['total_score']} | 涨跌: {row.get('change_pct', 0):.2f}%")
            print(f"   风险: {row['risk_level']} | 类别: {row.get('sector_category', 'unknown')}")
    
    # 3. 获取最强板块
    print("\n3. 获取最强板块推荐...")
    top_sectors = analyzer.get_top_sectors(sector_data, top_n=5)
    
    if top_sectors:
        print(f"✅ 推荐 {len(top_sectors)} 个最强板块:")
        for i, sector in enumerate(top_sectors, 1):
            print(f"{i}. {sector['sector_name']}")
            print(f"   得分: {sector['score']} | 强度: {sector['strength']}")
            print(f"   风险: {sector['risk_level']} | 推荐: {sector['recommendation']}")
            print(f"   理由: {sector['reason']}")
    else:
        print("❌ 无推荐板块")
    
    # 4. 生成报告
    print("\n4. 生成分析报告...")
    report = analyzer.generate_sector_report(sector_data, top_sectors)
    print(report[:2000] + "..." if len(report) > 2000 else report)  # 只显示前2000字符
    
    print("\n" + "="*80)
    print("✅ 测试完成")

if __name__ == "__main__":
    test_realtime_sectors()