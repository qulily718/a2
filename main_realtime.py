"""
短线稳健策略执行系统 - 实时动态板块版
基于AKShare实时板块数据，快速分析市场热点
"""
import yaml
import logging
import pandas as pd
from datetime import datetime
from src.data.data_fetcher import ShortTermDataFetcher
from src.core.dynamic_sector_analyzer_v2 import OptimizedDynamicSectorAnalyzer
from src.core.stock_filter import StockFilter
from src.strategy.trading_decision import ShortTermTradingDecision
from src.strategy.position_sizer import PositionManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """加载配置文件"""
    try:
        with open('config/sectors.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # 如果配置文件不存在，使用默认配置
        return {
            'scan_params': {
                'data_period': '6mo',
                'min_trading_days': 60,
                'min_avg_volume': 10000000,
                'max_stocks_per_sector': 20,
                'min_price': 5.0,
                'max_price': 200.0,
                'min_volume': 10000000,
                'ma_periods': [5, 10, 20],
                'price_above_ma': 20,
                'min_5d_change': 2.0,
                'max_5d_change': 15.0,
                'min_20d_change': 5.0,
                'max_volatility': 0.4,
                'volume_ratio_threshold': 1.2,
                'weights': {
                    'trend': 0.25,
                    'momentum': 0.25,
                    'volume': 0.20,
                    'volatility': 0.15,
                    'position': 0.15
                }
            }
        }

def analyze_stocks_in_top_sectors(stock_filter, top_sectors, max_stocks_per_sector=5):
    """
    在最强板块中筛选个股
    
    Args:
        stock_filter: 个股筛选器
        top_sectors: 最强板块列表
        max_stocks_per_sector: 每个板块最大个股数
    
    Returns:
        推荐个股列表
    """
    print("\n🔍 开始在推荐板块中筛选个股...")
    print("=" * 80)
    
    all_recommended_stocks = []
    
    for idx, sector in enumerate(top_sectors, 1):
        print(f"\n📊 [{idx}/{len(top_sectors)}] 分析板块: {sector['sector_name']}")
        print(f"   强度: {sector['strength']} | 得分: {sector['score']}")
        print(f"   风险等级: {sector['risk_level']} | 推荐: {sector['recommendation']}")
        
        try:
            # 获取板块成分股并筛选
            stocks = stock_filter.filter_stocks_in_sector(
                sector['sector_code'], 
                max_stocks=max_stocks_per_sector,
                strict_mode=False  # 先使用宽松模式
            )
            
            if not stocks:
                print(f"   ⚠️  未找到符合条件的个股")
                continue
            
            print(f"   ✅  找到 {len(stocks)} 只潜力个股:")
            
            for stock in stocks:
                print(f"      • {stock['name']} ({stock['symbol']})")
                print(f"        评分: {stock['total_score']} | 价格: {stock['price']:.2f} | 涨幅: {stock['change_pct']:.2f}%")
                print(f"        信号: {stock['entry_signal']} | 止损: {stock['stop_loss']:.2f}")
                
                # 生成交易决策
                buy_signal = ShortTermTradingDecision.get_buy_signal(stock)
                if buy_signal['suggested_action'] != '观望':
                    low, high = buy_signal['buy_price_range']
                    print(f"        操作: {buy_signal['suggested_action']} | 买入区间: {low:.2f}-{high:.2f}")
                    print(f"        目标: {buy_signal['target_price']:.2f} | 风险收益比: 1:{buy_signal['risk_reward_ratio']:.1f}")
                
                # 添加板块信息
                stock['sector_name'] = sector['sector_name']
                stock['sector_score'] = sector['score']
                stock['sector_strength'] = sector['strength']
                
                # 添加交易决策信息
                stock['buy_signal'] = buy_signal
                
                all_recommended_stocks.append(stock)
                
        except Exception as e:
            print(f"   ❌  分析板块 {sector['sector_name']} 时出错: {e}")
            continue
    
    return all_recommended_stocks

def save_results(all_stocks, top_sectors, sector_analyzer):
    """保存分析结果"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 保存板块分析结果
    sector_data = sector_analyzer.get_real_time_sector_data()
    if not sector_data.empty:
        sector_data.to_csv(f"results/sector_data_{timestamp}.csv", 
                          index=False, encoding='utf-8-sig')
        print(f"✅ 板块数据已保存: results/sector_data_{timestamp}.csv")
    
    # 2. 保存推荐板块
    if top_sectors:
        top_sectors_df = pd.DataFrame(top_sectors)
        top_sectors_df.to_csv(f"results/top_sectors_{timestamp}.csv", 
                             index=False, encoding='utf-8-sig')
        print(f"✅ 推荐板块已保存: results/top_sectors_{timestamp}.csv")
    
        # 3. 保存推荐个股
        if all_stocks:
            stocks_df = pd.DataFrame(all_stocks)
            
            # 展开buy_signal字典为单独列
            if 'buy_signal' in stocks_df.columns:
                buy_signals = stocks_df['buy_signal'].apply(pd.Series)
                buy_signals.columns = [f'buy_{col}' for col in buy_signals.columns]
                stocks_df = pd.concat([stocks_df.drop('buy_signal', axis=1), buy_signals], axis=1)
            
            # 排序：先按板块得分，再按个股得分
            stocks_df = stocks_df.sort_values(['sector_score', 'total_score'], 
                                             ascending=[False, False])
            
            stocks_df.to_csv(f"results/recommended_stocks_{timestamp}.csv", 
                        index=False, encoding='utf-8-sig')
            print(f"✅ 推荐个股已保存: results/recommended_stocks_{timestamp}.csv")
            
            # 生成详细交易计划文件
            trading_plans = []
            for stock in all_stocks:
                plan = ShortTermTradingDecision.generate_trading_plan(stock)
                trading_plans.append(plan)
                trading_plans.append("\n" + "="*80 + "\n")
            
            with open(f"results/trading_plans_{timestamp}.txt", 'w', encoding='utf-8') as f:
                f.write("\n".join(trading_plans))
            print(f"✅ 交易计划已保存: results/trading_plans_{timestamp}.txt")
        
        # 简化版
        simple_cols = ['symbol', 'name', 'sector_name', 'price', 'change_pct',
                      'total_score', 'entry_signal', 'stop_loss', 'rank_reasons']
        
        available_cols = [col for col in simple_cols if col in stocks_df.columns]
        if available_cols:
            stocks_simple = stocks_df[available_cols]
            stocks_simple.to_csv(f"results/stocks_simple_{timestamp}.csv", 
                               index=False, encoding='utf-8-sig')
            print(f"✅ 简化版个股列表已保存: results/stocks_simple_{timestamp}.csv")
    
    return timestamp

def generate_summary_report(all_stocks, top_sectors):
    """生成总结报告"""
    print("\n" + "="*100)
    print("📋 分析总结报告")
    print("="*100)
    
    if not top_sectors:
        print("⚠️  今日无推荐板块")
        return
    
    print(f"\n🎯 市场热点板块（共{len(top_sectors)}个）：")
    print("-" * 80)
    
    for sector in top_sectors:
        strength_emoji = "🔥" if sector['strength'] in ['强势', '偏强'] else "📊"
        risk_emoji = "⚠️" if sector['risk_level'] == 'high' else "✅"
        
        print(f"{strength_emoji} {sector['sector_name']}")
        print(f"   得分: {sector['score']} | 强度: {sector['strength']} | 风险: {risk_emoji} {sector['risk_level']}")
        print(f"   理由: {sector['reason']}")
    
    if all_stocks:
        print(f"\n📈 推荐个股汇总（共{len(all_stocks)}只）：")
        print("-" * 80)
        
        # 按板块分组显示
        stocks_by_sector = {}
        for stock in all_stocks:
            sector_name = stock.get('sector_name', '未知板块')
            if sector_name not in stocks_by_sector:
                stocks_by_sector[sector_name] = []
            stocks_by_sector[sector_name].append(stock)
        
        for sector_name, stocks in stocks_by_sector.items():
            # 查找板块信息
            sector_info = next((s for s in top_sectors if s['sector_name'] == sector_name), None)
            sector_score = sector_info['score'] if sector_info else 0
            
            print(f"\n📍 {sector_name} (板块得分: {sector_score})")
            
            for stock in sorted(stocks, key=lambda x: x['total_score'], reverse=True)[:3]:  # 只显示前3个
                score_emoji = "⭐" if stock['total_score'] >= 70 else "📈"
                print(f"   {score_emoji} {stock['name']} ({stock['symbol']})")
                print(f"      评分: {stock['total_score']} | 价格: {stock['price']:.2f} | 涨幅: {stock['change_pct']:.2f}%")
                print(f"      信号: {stock['entry_signal']}")
                
                # 显示交易建议
                if 'buy_signal' in stock:
                    buy_signal = stock['buy_signal']
                    if buy_signal['suggested_action'] != '观望':
                        low, high = buy_signal['buy_price_range']
                        print(f"      操作: {buy_signal['suggested_action']} | 买入区间: {low:.2f}-{high:.2f}")
                        print(f"      持有: {buy_signal['holding_days']}天 | 目标: {buy_signal['target_price']:.2f}")
        
        print("\n💡 操作建议:")
        print("  1. 优先关注评分≥70的个股")
        print("  2. 关注强势板块（🔥标记）")
        print("  3. 控制高风险板块的仓位（⚠️标记）")
        print("  4. 严格执行止损纪律")
        print("\n⏰ 操作时机:")
        print("  • 买入时机：次日开盘后30-60分钟（9:45-10:15）")
        print("  • 买入价格：在建议区间内分批买入")
        print("  • 持有周期：3-10个交易日")
        print("  • 止损纪律：亏损超过3-5%坚决卖出")
    else:
        print("\n⚠️  今日未找到符合策略的个股")
        print("建议：1. 放宽筛选条件 2. 关注其他板块 3. 保持观望")

def main():
    """主函数"""
    print("🚀 启动短线稳健策略执行系统（实时动态版）")
    print("=" * 80)
    
    # 1. 加载配置
    config = load_config()
    scan_params = config.get('scan_params', {})
    
    # 2. 初始化组件
    data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.3)
    sector_analyzer = OptimizedDynamicSectorAnalyzer(data_fetcher)
    stock_filter = StockFilter(data_fetcher, config=scan_params)
    
    try:
        # 3. 实时板块分析
        print("\n📊 正在实时分析板块强度...")
        sector_data = sector_analyzer.get_real_time_sector_data()
        
        if sector_data.empty:
            print("❌ 无法获取板块数据，请检查网络连接")
            return
        
        # 4. 获取最强板块
        top_sectors = sector_analyzer.get_top_sectors(sector_data, top_n=5)
        
        if not top_sectors:
            print("⚠️  未找到值得推荐的板块，市场可能整体偏弱")
            return
        
        # 5. 生成板块分析报告
        sector_report = sector_analyzer.generate_sector_report(sector_data, top_sectors)
        print(sector_report)
        
        # 6. 个股筛选
        all_stocks = analyze_stocks_in_top_sectors(stock_filter, top_sectors, max_stocks_per_sector=3)
        
        # 7. 保存结果
        timestamp = save_results(all_stocks, top_sectors, sector_analyzer)
        
        # 8. 生成总结报告
        generate_summary_report(all_stocks, top_sectors)
        
        print(f"\n📁 所有结果已保存到 results/ 目录，时间戳: {timestamp}")
        
    except Exception as e:
        print(f"\n❌ 系统运行出错: {e}")
        import traceback
        print(traceback.format_exc())
        
    finally:
        print("\n" + "="*80)
        print("✅ 分析完成！")
        print("="*80)

if __name__ == "__main__":
    main()