"""
全时段市场分析系统 - 支持任何时间运行
根据当前时间自动选择分析模式
"""
import sys
import os
import pandas as pd
from datetime import datetime, time
import logging
import glob
from typing import List, Dict

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.data.data_fetcher import ShortTermDataFetcher
from src.analyzer.time_pattern_analyzer import TimePatternAnalyzer
from src.core.dynamic_sector_analyzer_v2 import OptimizedDynamicSectorAnalyzer
from src.core.stock_filter import StockFilter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """加载配置文件"""
    try:
        import yaml
        with open('config/sectors.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("配置文件不存在，使用默认配置")
        return {
            'scan_params': {
                'data_period': '6mo',
                'min_trading_days': 60,
                'min_avg_volume': 10000000,
                'max_stocks_per_sector': 20
            }
        }


def get_watchlist_from_file(results_dir: str = "results"):
    """从文件获取监控列表"""
    if not os.path.exists(results_dir):
        return []
    
    # 查找最新的分析结果
    patterns = [
        "recommended_stocks_*.csv",
        "stocks_simple_*.csv",
        "simple_recommendations_*.csv",
        "recommendations_*.csv",
    ]
    
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(results_dir, pattern)))
    
    if not files:
        return []
    
    latest_file = max(files, key=os.path.getctime)
    logger.info(f"从文件加载监控列表: {os.path.basename(latest_file)}")
    
    try:
        df = pd.read_csv(latest_file, encoding='utf-8-sig')
        
        watchlist = []
        for _, row in df.iterrows():
            symbol = str(row.get('symbol', '')).strip()
            if symbol:
                watchlist.append({
                    'symbol': symbol,
                    'name': str(row.get('name', '')).strip(),
                    'sector_name': str(row.get('sector_name', row.get('sector', ''))).strip(),
                    'score': float(row.get('total_score', 0)) if pd.notna(row.get('total_score')) else 0,
                    'price': float(row.get('price', 0)) if pd.notna(row.get('price')) else 0,
                    'change_pct': float(row.get('change_pct', 0)) if pd.notna(row.get('change_pct')) else 0
                })
        
        return watchlist[:30]  # 限制数量
        
    except Exception as e:
        logger.error(f"加载文件失败: {e}")
        return []


def get_realtime_watchlist():
    """获取实时监控列表"""
    try:
        data_fetcher = ShortTermDataFetcher(rate_limit=0.5)
        sector_analyzer = OptimizedDynamicSectorAnalyzer(data_fetcher)
        
        # 获取板块数据
        sector_data = sector_analyzer.get_real_time_sector_data()
        
        if sector_data.empty:
            return []
        
        # 选择最强板块
        top_sectors = sector_analyzer.get_top_sectors(sector_data, top_n=3)
        
        # 获取每个板块的股票
        watchlist = []
        stock_filter = StockFilter(data_fetcher)
        
        for sector in top_sectors[:2]:  # 只取前2个板块
            stocks = stock_filter.filter_stocks_in_sector(
                sector['sector_code'], 
                max_stocks=10,
                strict_mode=False
            )
            
            for stock in stocks:
                watchlist.append({
                    'symbol': stock['symbol'],
                    'name': stock['name'],
                    'sector_name': sector['sector_name'],
                    'score': stock.get('total_score', 0),
                    'price': stock.get('price', 0),
                    'change_pct': stock.get('change_pct', 0)
                })
        
        return watchlist[:25]
        
    except Exception as e:
        logger.error(f"获取实时监控列表失败: {e}")
        return []


def display_analysis_report(analysis_result: dict):
    """显示分析报告"""
    mode_descriptions = {
        'morning_open': "开盘30分钟分析",
        'morning_mid': "上午盘中分析",
        'noon_break': "午间休市分析",
        'afternoon_early': "下午开盘分析",
        'afternoon_mid': "下午盘中分析",
        'closing': "尾盘30分钟分析",
        'post_market': "盘后复盘分析",
        'pre_market': "盘前预判分析",
        'weekend_analysis': "周末分析",
        'general_analysis': "通用分析"
    }
    
    mode = analysis_result.get('mode', 'general_analysis')
    mode_desc = mode_descriptions.get(mode, "市场分析")
    
    print("\n" + "="*100)
    print(f"📈 {mode_desc}")
    print("="*100)
    print(f"分析时间: {analysis_result.get('analysis_time', 'N/A')}")
    print(f"分析模式: {mode}")
    print(f"分析重点: {analysis_result.get('focus', 'N/A')}")
    
    # 显示推荐
    recommendation = analysis_result.get('recommendation', '')
    if recommendation:
        print(f"\n🎯 操作建议: {recommendation}")
    
    # 显示详细结果
    if 'results' in analysis_result and analysis_result['results']:
        print(f"\n📊 分析结果 (前{min(10, len(analysis_result['results']))}只):")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['results'][:10], 1):
            name = stock.get('name', stock.get('symbol', ''))
            score = stock.get('score', stock.get('opportunity_score', 0))
            change = stock.get('opening_change', stock.get('change_pct', 0))
            signal = stock.get('signal', stock.get('trend', ''))
            
            print(f"{i:2d}. {name[:10]:<10} 评分: {score:>5.1f} 涨跌: {change:>6.2f}% 信号: {signal}")
    
    elif 'daily_summary' in analysis_result and analysis_result['daily_summary']:
        print(f"\n📋 股票分析汇总:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['daily_summary'][:10], 1):
            name = stock.get('name', stock.get('symbol', ''))
            score = stock.get('score', 0)
            trend = stock.get('trend', '')
            
            print(f"{i:2d}. {name[:12]:<12} 评分: {score:>5.1f} 趋势: {trend}")
    
    elif 'stock_analysis' in analysis_result and analysis_result['stock_analysis']:
        print(f"\n🔍 股票技术分析:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['stock_analysis'][:10], 1):
            name = stock.get('name', stock.get('symbol', ''))
            score = stock.get('score', 0)
            pattern = stock.get('pattern', '')
            
            print(f"{i:2d}. {name[:12]:<12} 评分: {score:>5.1f} 形态: {pattern}")
    
    elif 'weekly_analysis' in analysis_result and analysis_result['weekly_analysis']:
        print(f"\n📅 周线分析:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['weekly_analysis'][:10], 1):
            name = stock.get('name', stock.get('symbol', ''))
            score = stock.get('score', 0)
            pattern = stock.get('pattern', '')
            
            print(f"{i:2d}. {name[:12]:<12} 评分: {score:>5.1f} 形态: {pattern}")
    
    elif 'morning_summary' in analysis_result and analysis_result['morning_summary']:
        print(f"\n🌅 上午表现汇总:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['morning_summary'][:10], 1):
            name = stock.get('name', stock.get('symbol', ''))
            score = stock.get('score', 0)
            trend = stock.get('trend', '')
            
            print(f"{i:2d}. {name[:12]:<12} 评分: {score:>5.1f} 趋势: {trend}")
    
    # 显示市场预测
    if 'afternoon_outlook' in analysis_result:
        outlook = analysis_result['afternoon_outlook']
        trend_map = {'bullish': '看涨', 'bearish': '看跌', 'neutral': '中性'}
        print(f"\n🌅 下午走势预测: {trend_map.get(outlook.get('trend', 'neutral'), '中性')} (置信度: {outlook.get('confidence', 0)*100:.0f}%)")
    
    if 'tomorrow_outlook' in analysis_result:
        outlook = analysis_result['tomorrow_outlook']
        trend_map = {'bullish': '看涨', 'bearish': '看跌', 'neutral': '中性'}
        print(f"\n📅 明日走势预测: {trend_map.get(outlook.get('trend', 'neutral'), '中性')} (置信度: {outlook.get('confidence', 0)*100:.0f}%)")
    
    if 'next_week_outlook' in analysis_result:
        outlook = analysis_result['next_week_outlook']
        trend_map = {'bullish': '看涨', 'bearish': '看跌', 'neutral': '中性'}
        print(f"\n🗓️  下周走势预测: {trend_map.get(outlook.get('trend', 'neutral'), '中性')} (置信度: {outlook.get('confidence', 0)*100:.0f}%)")
    
    if 'opening_prediction' in analysis_result:
        prediction = analysis_result['opening_prediction']
        impact_map = {'positive': '正面', 'negative': '负面', 'neutral': '中性'}
        print(f"\n🌄 开盘预测: {impact_map.get(prediction.get('impact', 'neutral'), '中性')} (强度: {prediction.get('strength', 0):.1f})")
    
    # 显示统计信息
    stocks_analyzed = analysis_result.get('stocks_analyzed', 0)
    if stocks_analyzed == 0:
        # 尝试从其他字段获取
        for key in ['results', 'daily_summary', 'stock_analysis', 'weekly_analysis', 'morning_summary']:
            if key in analysis_result and analysis_result[key]:
                stocks_analyzed = len(analysis_result[key])
                break
    
    print(f"\n📈 分析统计:")
    print(f"  分析股票数: {stocks_analyzed}")
    
    # 根据模式给出具体建议
    print(f"\n💡 具体操作建议:")
    
    mode_specific_advice = {
        'morning_open': [
            "1. 关注开盘30分钟强势股",
            "2. 在9:45前完成第一批买入",
            "3. 设置好止损位（-2%到-3%）"
        ],
        'morning_mid': [
            "1. 观察上午趋势是否延续",
            "2. 寻找回调买入机会",
            "3. 控制仓位在5成以下"
        ],
        'noon_break': [
            "1. 复盘上午操作",
            "2. 制定下午交易计划",
            "3. 关注午间消息面"
        ],
        'afternoon_early': [
            "1. 观察开盘是否延续上午趋势",
            "2. 谨慎追高，等待回调",
            "3. 关注量能变化"
        ],
        'afternoon_mid': [
            "1. 确认全天趋势",
            "2. 尾盘寻找机会",
            "3. 避免重仓过夜"
        ],
        'closing': [
            "1. 尾盘谨慎操作",
            "2. 关注最后30分钟异动",
            "3. 准备盘后复盘"
        ],
        'post_market': [
            "1. 复盘全天交易",
            "2. 分析技术指标",
            "3. 制定次日策略"
        ],
        'pre_market': [
            "1. 关注技术形态",
            "2. 制定开盘策略",
            "3. 设置观察清单"
        ],
        'weekend_analysis': [
            "1. 分析周线趋势",
            "2. 关注周末政策",
            "3. 制定下周策略"
        ],
        'general_analysis': [
            "1. 分析近期走势",
            "2. 寻找技术买点",
            "3. 控制风险"
        ]
    }
    
    for advice in mode_specific_advice.get(mode, ["根据具体分析结果操作"]):
        print(f"  {advice}")
    
    print("\n" + "="*100)


def save_analysis_result(analysis_result: dict):
    """保存分析结果"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    results_dir = "analysis_results"
    mode = analysis_result.get('mode', 'general')
    
    # 创建目录
    os.makedirs(results_dir, exist_ok=True)
    
    # 保存为JSON
    import json
    filename = os.path.join(results_dir, f"{mode}_analysis_{timestamp}.json")
    
    # 转换不可序列化的对象
    def make_serializable(obj):
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict('records')
        elif isinstance(obj, (int, float, str, bool, type(None))):
            return obj
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(v) for v in obj]
        else:
            return str(obj)
    
    try:
        cleaned_result = make_serializable(analysis_result)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(cleaned_result, f, ensure_ascii=False, indent=2)
        
        print(f"💾 分析结果已保存: {filename}")
        
        # 同时保存为CSV格式（如果有股票数据）
        for key in ['results', 'daily_summary', 'stock_analysis', 'weekly_analysis', 'morning_summary']:
            if key in analysis_result and analysis_result[key]:
                df = pd.DataFrame(analysis_result[key])
                csv_file = os.path.join(results_dir, f"{mode}_stocks_{timestamp}.csv")
                df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"💾 股票数据已保存: {csv_file}")
                break
                
    except Exception as e:
        logger.error(f"保存结果失败: {e}")


def update_realtime_data(watchlist: List[Dict], data_fetcher) -> List[Dict]:
    """更新监控列表的实时数据"""
    import akshare as ak
    
    updated_list = []
    
    for stock in watchlist:
        try:
            symbol = stock['symbol']
            # 转换股票代码格式（去掉后缀）
            code = symbol.replace('.SS', '').replace('.SZ', '')
            
            # 获取实时数据
            try:
                realtime_df = ak.stock_zh_a_spot_em()
                stock_data = realtime_df[realtime_df['代码'] == code]
                
                if not stock_data.empty:
                    row = stock_data.iloc[0]
                    stock['price'] = float(row.get('最新价', stock.get('price', 0)))
                    stock['change_pct'] = float(row.get('涨跌幅', stock.get('change_pct', 0)))
            except Exception as e:
                # 如果实时数据获取失败，尝试使用历史数据
                hist_data = data_fetcher.get_stock_history(symbol, period='5d')
                if hist_data is not None and len(hist_data) >= 2:
                    today_close = hist_data['close'].iloc[-1]
                    yesterday_close = hist_data['close'].iloc[-2]
                    stock['change_pct'] = (today_close / yesterday_close - 1) * 100
                    stock['price'] = today_close
                    
            updated_list.append(stock)
            
        except Exception as e:
            logger.error(f"更新 {stock.get('name', 'N/A')} 实时数据失败: {e}")
            updated_list.append(stock)
    
    return updated_list


def main():
    """主函数"""
    print("="*100)
    print("📈 全时段市场分析系统")
    print("="*100)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 初始化组件
    print("\n1. 初始化分析组件...")
    data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.3)
    time_analyzer = TimePatternAnalyzer(data_fetcher)
    
    # 2. 获取监控列表
    print("\n2. 获取监控股票列表...")
    watchlist = get_watchlist_from_file()
    
    # 如果文件加载失败，尝试实时获取
    if not watchlist:
        print("   文件加载失败，尝试实时获取...")
        watchlist = get_realtime_watchlist()
    
    if not watchlist:
        print("❌ 无法获取监控列表，程序退出")
        print("提示：请先运行 main_realtime.py 生成推荐股票列表")
        return
    
    print(f"✅ 获取到 {len(watchlist)} 只监控股票")
    
    # 2.5 如果是盘中时段，更新实时数据
    current_time = datetime.now().time()
    is_trading_time = (time(9, 30) <= current_time <= time(11, 30)) or (time(13, 0) <= current_time <= time(15, 0))
    
    if is_trading_time:
        print("\n2.5 更新实时数据...")
        watchlist = update_realtime_data(watchlist, data_fetcher)
        print(f"✅ 已更新 {len(watchlist)} 只股票的实时数据")
    
    # 3. 根据当前时间进行分析
    mode_name = time_analyzer.current_mode.replace('_', ' ')
    print(f"\n3. 开始{mode_name}...")
    analysis_result = time_analyzer.analyze_current_market(watchlist)
    
    # 4. 显示分析报告
    display_analysis_report(analysis_result)
    
    # 5. 保存结果
    save_analysis_result(analysis_result)
    
    print("\n" + "="*100)
    print("✅ 分析完成!")
    print("="*100)


if __name__ == "__main__":
    # 检查必要的库
    try:
        import pandas as pd
        import numpy as np
        import yaml
    except ImportError as e:
        print(f"❌ 缺少必要库: {e}")
        print("请运行: pip install pandas numpy pyyaml")
        sys.exit(1)
    
    main()
