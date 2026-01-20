"""
短线稳健策略执行系统 - 兼容性修复版
"""
import yaml
import logging
import pandas as pd
from datetime import datetime
from src.data.data_fetcher import ShortTermDataFetcher
from src.core.market_analyzer import MarketAnalyzer
from src.core.stock_filter import StockFilter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """加载配置文件"""
    with open('config/sectors.yaml', 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def analyze_stocks_by_sector(stock_filter, recommended_sectors):
    """按推荐板块分析个股"""
    print("\n🔍 板块内个股详细筛选结果：")
    print("-" * 60)
    
    all_recommended_stocks = []
    
    for sector in recommended_sectors:
        print(f"\n📁 板块: {sector['sector_name']} ({sector.get('strength', sector.get('trend', '未知'))})")
        print(f"  风险等级: {sector.get('risk_level', 'medium')} | 推荐: {sector.get('recommendation', '关注')}")
        print(f"  推荐理由: {sector.get('reason', '综合评分较高')}")
        
        # 使用筛选器分析该板块个股
        stocks = stock_filter.filter_stocks_in_sector(
            sector['sector_code'], 
            max_stocks=5,
            strict_mode=False  # 先用宽松模式测试
        )
        
        if not stocks:
            print("  ⚠️  未找到符合条件的个股")
            continue
        
        # 显示该板块的推荐个股
        for i, stock in enumerate(stocks, 1):
            print(f"\n  {i}. {stock['name']} ({stock['symbol']})")
            print(f"     综合评分: {stock['total_score']}/100")
            print(f"     当前价格: {stock['price']:.2f} | 涨跌幅: {stock['change_pct']:.2f}%")
            print(f"     入场信号: {stock['entry_signal']}")
            print(f"     止损位置: {stock['stop_loss']:.2f}")
            print(f"     推荐理由: {', '.join(stock['rank_reasons'][:2])}")
            
            all_recommended_stocks.append(stock)
    
    return all_recommended_stocks

def main():
    """主函数"""
    logger.info("🚀 启动短线稳健策略执行系统")
    
    # 1. 加载配置
    config = load_config()
    focus_sectors = config['focus_sectors']
    scan_params = config.get('scan_params', {})
    
    # 2. 初始化组件
    data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.3)
    market_analyzer = MarketAnalyzer(data_fetcher)
    stock_filter = StockFilter(data_fetcher, config=scan_params)
    
    # 3. 市场环境分析
    logger.info("📊 分析市场环境...")
    sector_strength = market_analyzer.analyze_sector_strength(focus_sectors)
    
    if sector_strength.empty:
        logger.warning("未获取到板块强度数据")
        print("\n⚠️  无法获取板块数据，请检查网络连接或akshare库")
        return
    
    # 4. 获取推荐板块
    recommended_sectors = market_analyzer.get_recommended_sectors(
        sector_strength, max_sectors=3
    )
    
    print("\n" + "="*60)
    print("📈 短线稳健策略 - 今日分析结果")
    print("="*60)
    
    if not recommended_sectors:
        print("\n⚠️  今日无推荐板块，市场整体偏弱")
        return
    
    print("\n🎯 推荐关注板块（按强度排序）：")
    for i, sector in enumerate(recommended_sectors, 1):
        # 安全获取字段，避免KeyError
        sector_name = sector.get('sector_name', '未知板块')
        strength = sector.get('strength', sector.get('trend', '未知'))
        score = sector.get('score', sector.get('total_score', 0))
        risk_level = sector.get('risk_level', 'medium')
        reason = sector.get('reason', sector.get('recommendation', '综合评分较高'))
        
        print(f"  {i}. {sector_name}")
        print(f"     强度: {strength} | 得分: {score:.1f}")
        print(f"     风险等级: {risk_level} | 理由: {reason}")
    
    # 5. 个股筛选
    all_recommended_stocks = analyze_stocks_by_sector(stock_filter, recommended_sectors)
    
    # 6. 输出详细报告
    if all_recommended_stocks:
        report = stock_filter.get_screening_report(all_recommended_stocks)
        print(report)
        
        # 保存结果
        df = pd.DataFrame(all_recommended_stocks)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存完整数据
        df.to_csv(f"results/recommendations_{timestamp}.csv", 
                 index=False, encoding='utf-8-sig')
        
        # 保存简化版
        simple_cols = ['symbol', 'name', 'price', 'change_pct', 
                      'total_score', 'risk_level', 'entry_signal', 
                      'stop_loss', 'rank_reasons']
        
        if all(col in df.columns for col in simple_cols):
            df_simple = df[simple_cols]
            df_simple.to_csv(f"results/simple_recommendations_{timestamp}.csv", 
                           index=False, encoding='utf-8-sig')
        
        logger.info(f"结果已保存至 results/recommendations_{timestamp}.csv")
    else:
        print("\n⚠️  今日未找到符合短线稳健策略的个股")
        print("建议：1. 放宽筛选条件 2. 关注其他板块 3. 保持观望")
    
    print("\n" + "="*60)
    print("✅ 分析完成！")
    print("="*60)

if __name__ == "__main__":
    main()