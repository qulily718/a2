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
from typing import List, Dict, Optional, Any

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
        
        # 不截断，按文件内容全部加载（由调用方决定是否限制）
        return watchlist
        
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


def display_analysis_report(analysis_result: dict, watchlist: Optional[List[Dict[str, Any]]] = None):
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
    
    # 用 watchlist 补全价格/昨收等信息（用于解释涨跌来源）
    watch_map: Dict[str, Dict[str, Any]] = {}
    if watchlist:
        for w in watchlist:
            sym = str(w.get("symbol", "")).strip()
            if sym:
                watch_map[sym] = w

    # 显示详细结果（不截断）
    if 'results' in analysis_result and analysis_result['results']:
        results = analysis_result['results']
        print(f"\n📊 分析结果（共{len(results)}只，不截断）：")
        print("-"*110)
        print(f"{'序号':>3}  {'代码':<10} {'名称':<12} {'评分':>6} {'现价':>8} {'昨收':>8} {'涨跌%':>8}  {'信号/备注'}")
        print("-"*110)

        for i, item in enumerate(results, 1):
            symbol = str(item.get('symbol', '')).strip()
            name = str(item.get('name', '')).strip() or symbol

            # 分析分数
            score = item.get('score', item.get('opportunity_score', 0))
            try:
                score = float(score)
            except Exception:
                score = 0.0

            # 价格与涨跌：以上一交易日收盘价 vs 当前价（盘中“现价”只认实时行情）
            ref = watch_map.get(symbol, {})
            current_price = ref.get('price', ref.get('current_price', item.get('price', None)))
            prev_close = ref.get('prev_close', item.get('prev_close', 0))
            last_close = ref.get('last_close', item.get('last_close', None))
            change_pct = ref.get('change_pct', item.get('change_pct', item.get('opening_change', 0)))
            price_source = str(ref.get('price_source', 'unknown'))

            def _fmt_num(x, width=8):
                try:
                    v = float(x)
                    if pd.isna(v):
                        return " " * (width - 3) + "N/A"
                    return f"{v:>{width}.2f}"
                except Exception:
                    return " " * (width - 3) + "N/A"

            def _fmt_pct(x, width=8):
                try:
                    v = float(x)
                    if pd.isna(v):
                        return " " * (width - 3) + "N/A"
                    return f"{v:>{width}.2f}"
                except Exception:
                    return " " * (width - 3) + "N/A"

            signal = item.get('signal', item.get('trend', ''))
            note_parts = []
            if prev_close not in (None, 0) and current_price is not None and not pd.isna(current_price):
                note_parts.append("昨收→现价")
            if price_source and price_source != "unknown":
                note_parts.append(f"src={price_source}")
            if (current_price is None or pd.isna(current_price)) and last_close is not None and not pd.isna(last_close):
                note_parts.append(f"最近收盘={float(last_close):.2f}")
            note = f" ({' | '.join(note_parts)})" if note_parts else ""
            print(
                f"{i:>3}  {symbol:<10} {name[:12]:<12} {score:>6.1f} "
                f"{_fmt_num(current_price)} {_fmt_num(prev_close)} {_fmt_pct(change_pct)}  {signal}{note}"
            )
    
    elif 'daily_summary' in analysis_result and analysis_result['daily_summary']:
        print(f"\n📋 股票分析汇总:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['daily_summary'], 1):
            symbol = str(stock.get('symbol', '')).strip()
            name = stock.get('name', symbol)
            score = stock.get('score', 0)
            trend = stock.get('trend', '')
            
            print(f"{i:2d}. {symbol:<10} {str(name)[:12]:<12} 评分: {float(score):>5.1f} 趋势: {trend}")
    
    elif 'stock_analysis' in analysis_result and analysis_result['stock_analysis']:
        print(f"\n🔍 股票技术分析:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['stock_analysis'], 1):
            symbol = str(stock.get('symbol', '')).strip()
            name = stock.get('name', symbol)
            score = stock.get('score', 0)
            pattern = stock.get('pattern', '')
            
            print(f"{i:2d}. {symbol:<10} {str(name)[:12]:<12} 评分: {float(score):>5.1f} 形态: {pattern}")
    
    elif 'weekly_analysis' in analysis_result and analysis_result['weekly_analysis']:
        print(f"\n📅 周线分析:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['weekly_analysis'], 1):
            symbol = str(stock.get('symbol', '')).strip()
            name = stock.get('name', symbol)
            score = stock.get('score', 0)
            pattern = stock.get('pattern', '')
            
            print(f"{i:2d}. {symbol:<10} {str(name)[:12]:<12} 评分: {float(score):>5.1f} 形态: {pattern}")
    
    elif 'morning_summary' in analysis_result and analysis_result['morning_summary']:
        print(f"\n🌅 上午表现汇总:")
        print("-"*80)
        
        for i, stock in enumerate(analysis_result['morning_summary'], 1):
            symbol = str(stock.get('symbol', '')).strip()
            name = stock.get('name', symbol)
            score = stock.get('score', 0)
            trend = stock.get('trend', '')
            
            print(f"{i:2d}. {symbol:<10} {str(name)[:12]:<12} 评分: {float(score):>5.1f} 趋势: {trend}")
    
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

    def _build_eq_code(symbol: str) -> str:
        """easyquotation 常用代码格式：sh600000 / sz000001"""
        code = symbol.replace('.SS', '').replace('.SZ', '')
        if symbol.endswith('.SS'):
            return f"sh{code}"
        if symbol.endswith('.SZ'):
            return f"sz{code}"
        return code

    # 1) 全市场实时行情（尽量一次请求）
    realtime_df = None
    try:
        realtime_df = ak.stock_zh_a_spot_em()
    except Exception:
        realtime_df = None

    # 2) easyquotation：无论 spot_em 成功与否，都提前批量取 watchlist 报价，用来兜底缺失项
    eq_quotes: Dict[str, Any] = {}
    try:
        import easyquotation  # type: ignore

        eq_codes_prefixed = [_build_eq_code(s.get('symbol', '')) for s in watchlist if s.get('symbol')]
        eq_codes_prefixed = [c for c in eq_codes_prefixed if c]
        eq_codes_digits = [c[2:] if c.startswith(("sh", "sz")) else c for c in eq_codes_prefixed]

        # 先用 tencent（偏常用），若为空再尝试 sina
        quotation = easyquotation.use('tencent')
        if eq_codes_prefixed:
            eq_quotes = quotation.stocks(eq_codes_prefixed) or {}
        if not eq_quotes and eq_codes_digits:
            quotation = easyquotation.use('sina')
            eq_quotes = quotation.stocks(eq_codes_digits) or {}
    except Exception as e:
        logger.debug("easyquotation 获取失败: %s", e)
        eq_quotes = {}
    
    for stock in watchlist:
        try:
            symbol = stock['symbol']
            # 转换股票代码格式（去掉后缀）
            code = symbol.replace('.SS', '').replace('.SZ', '')
            
            # 先用历史数据拿“昨收”（上一个交易日收盘价），用于解释涨跌来源
            prev_close = None
            hist_data = None
            last_close = None
            try:
                # 用更稳健的 close 序列，避免盘中日线 close 被填充成昨收造成误解
                hist_data = data_fetcher.get_stock_history(symbol, period='10d')
                if hist_data is not None and not hist_data.empty and 'close' in hist_data.columns:
                    # 确保索引是日期类型（用于按日期筛选）
                    if not isinstance(hist_data.index, pd.DatetimeIndex):
                        try:
                            hist_data.index = pd.to_datetime(hist_data.index)
                        except Exception:
                            pass
                    
                    closes = pd.to_numeric(hist_data['close'], errors='coerce').dropna()
                    if len(closes) >= 1:
                        today = pd.Timestamp(datetime.now().date())
                        is_date_index = isinstance(hist_data.index, pd.DatetimeIndex)
                        
                        # 获取最新收盘价和日期
                        last_close = float(closes.iloc[-1])
                        last_date = hist_data.index[-1] if is_date_index else None
                        stock['last_close'] = last_close
                        stock['last_close_date'] = last_date.strftime('%Y-%m-%d') if is_date_index and last_date else 'N/A'
                        
                        # 计算"昨收"：今天之前最近一个交易日的收盘价
                        if is_date_index:
                            # 筛选今天之前的数据（不包括今天）
                            before_today = hist_data[hist_data.index < today]
                            if not before_today.empty and 'close' in before_today.columns:
                                prev_closes = pd.to_numeric(before_today['close'], errors='coerce').dropna()
                                if len(prev_closes) >= 1:
                                    prev_close = float(prev_closes.iloc[-1])
                                    prev_date = before_today.index[-1]
                                    stock['prev_close'] = prev_close
                                    stock['prev_close_date'] = prev_date.strftime('%Y-%m-%d')
                                    logger.debug(f"{symbol} 昨收: {prev_close:.2f} (日期: {prev_date.strftime('%Y-%m-%d')})")
                        else:
                            # 如果索引不是日期，回退到简单逻辑：取倒数第二个（如果有）
                            if len(closes) >= 2:
                                prev_close = float(closes.iloc[-2])
                                stock['prev_close'] = prev_close
                                stock['prev_close_date'] = 'N/A (非日期索引)'
            except Exception as e:
                logger.debug(f"计算昨收失败 {symbol}: {e}")
                pass

            # 再尝试用实时数据拿“现价”
            current_price = None
            # 2.1 先用 spot_em（若可用）
            if realtime_df is not None and not realtime_df.empty and '代码' in realtime_df.columns:
                stock_data = realtime_df[realtime_df['代码'].astype(str) == str(code)]
                if not stock_data.empty:
                    row = stock_data.iloc[0]
                    v = pd.to_numeric(row.get('最新价', None), errors='coerce')
                    if v is not None and not pd.isna(v):
                        current_price = float(v)
                        stock['price'] = current_price  # 现价（实时）
                        stock['price_source'] = 'spot'

            # 2.2 spot_em 失败/缺失 -> easyquotation 兜底
            if current_price is None:
                eq_code = _build_eq_code(symbol)
                q = None
                if isinstance(eq_quotes, dict):
                    q = eq_quotes.get(eq_code) or eq_quotes.get(code) or eq_quotes.get(eq_code[2:]) or eq_quotes.get(eq_code.upper())
                if isinstance(q, dict):
                    raw_now = q.get('now', q.get('price', q.get('current', q.get('last', None))))
                    v = pd.to_numeric(raw_now, errors='coerce')
                    if v is not None and not pd.isna(v):
                        current_price = float(v)
                        stock['price'] = current_price
                        stock['price_source'] = 'easyquotation'
                        # 若昨收缺失，尝试从报价里拿 close
                        if prev_close is None:
                            raw_close = q.get('close', q.get('yesterday_close', q.get('pre_close', None)))
                            c = pd.to_numeric(raw_close, errors='coerce')
                            if c is not None and not pd.isna(c):
                                prev_close = float(c)
                                stock['prev_close'] = prev_close

            # 2.3 再兜底：分钟线（个股请求，有时比 spot_em 稳）
            if current_price is None:
                try:
                    df_min = ak.stock_zh_a_hist_min_em(
                        symbol=code,
                        period="1",
                        start_date=datetime.now().strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d"),
                        adjust="",
                    )
                    if df_min is not None and not df_min.empty:
                        last = df_min.iloc[-1]
                        v = pd.to_numeric(last.get("收盘", None), errors="coerce")
                        if v is not None and not pd.isna(v):
                            current_price = float(v)
                            stock['price'] = current_price
                            stock['price_source'] = 'min1'
                except Exception:
                    pass

            if current_price is None:
                stock['price'] = None
                stock['price_source'] = 'unavailable'

            # 统一按“昨收→现价”计算涨跌幅（更清晰）
            if current_price is not None and prev_close is not None and prev_close > 0:
                stock['change_pct'] = (current_price / prev_close - 1) * 100
                src = stock.get('price_source', 'unknown')
                stock['change_source'] = f"prev_close_vs_{src}"
            else:
                # 盘中拿不到实时价时，不用“最近收盘”冒充“现价”，避免看起来现价=昨收
                stock['change_pct'] = None
                stock['change_source'] = 'unavailable'
                    
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
    
    # 3. 根据当前时间进行分析（使用 try/finally 确保 BaoStock 连接关闭）
    mode_name = time_analyzer.current_mode.replace('_', ' ')
    print(f"\n3. 开始{mode_name}...")
    try:
        analysis_result = time_analyzer.analyze_current_market(watchlist)
        
        # 4. 显示分析报告
        display_analysis_report(analysis_result, watchlist=watchlist)
        
        # 5. 保存结果
        save_analysis_result(analysis_result)
    finally:
        data_fetcher.close()  # 批量处理完成后关闭 BaoStock 连接
    
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
