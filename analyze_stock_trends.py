"""
股票趋势分析工具 - 可在任何时间运行
基于历史K线数据分析股票趋势，不依赖实时行情
"""
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加项目路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.data.data_fetcher import ShortTermDataFetcher
from src.core.stock_filter import StockFilter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StockTrendAnalyzer:
    """股票趋势分析器（基于历史数据）"""
    
    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher
    
    def analyze_trend(self, symbol: str, period: str = "1mo") -> dict:
        """
        分析单只股票的趋势
        
        Args:
            symbol: 股票代码，如 "000001.SZ"
            period: 数据周期，可选 "1mo", "3mo", "6mo"
        
        Returns:
            趋势分析结果字典
        """
        # 获取历史数据
        hist_data = self.data_fetcher.get_stock_history(symbol, period=period)
        
        if hist_data.empty or len(hist_data) < 20:
            return {
                'symbol': symbol,
                'status': 'insufficient_data',
                'message': '数据不足，无法分析'
            }
        
        # 计算技术指标
        closes = hist_data['close']
        volumes = hist_data['volume'] if 'volume' in hist_data.columns else None
        
        # 均线系统
        ma5 = closes.rolling(5).mean()
        ma10 = closes.rolling(10).mean()
        ma20 = closes.rolling(20).mean()
        
        current_price = closes.iloc[-1]
        ma5_current = ma5.iloc[-1]
        ma10_current = ma10.iloc[-1]
        ma20_current = ma20.iloc[-1]
        
        # 趋势判断
        trend_direction = self._judge_trend(current_price, ma5_current, ma10_current, ma20_current)
        
        # 动量分析
        momentum_5d = (closes.iloc[-1] / closes.iloc[-5] - 1) * 100 if len(closes) >= 5 else 0
        momentum_20d = (closes.iloc[-1] / closes.iloc[-20] - 1) * 100 if len(closes) >= 20 else 0
        
        # 成交量分析
        volume_trend = 'unknown'
        if volumes is not None and len(volumes) >= 10:
            recent_vol = volumes.iloc[-5:].mean()
            earlier_vol = volumes.iloc[-10:-5].mean()
            if recent_vol > earlier_vol * 1.2:
                volume_trend = 'increasing'
            elif recent_vol < earlier_vol * 0.8:
                volume_trend = 'decreasing'
            else:
                volume_trend = 'stable'
        
        # 波动率
        volatility = closes.pct_change().std() * np.sqrt(252) * 100  # 年化波动率
        
        # 支撑位和阻力位
        support = closes.tail(20).min()
        resistance = closes.tail(20).max()
        
        # 综合评分
        score = self._calculate_trend_score(
            trend_direction, momentum_5d, momentum_20d, 
            volume_trend, volatility
        )
        
        return {
            'symbol': symbol,
            'status': 'success',
            'current_price': round(current_price, 2),
            'trend_direction': trend_direction,
            'trend_strength': self._get_trend_strength(trend_direction, momentum_5d),
            'ma5': round(ma5_current, 2),
            'ma10': round(ma10_current, 2),
            'ma20': round(ma20_current, 2),
            'momentum_5d': round(momentum_5d, 2),
            'momentum_20d': round(momentum_20d, 2),
            'volume_trend': volume_trend,
            'volatility': round(volatility, 2),
            'support': round(support, 2),
            'resistance': round(resistance, 2),
            'score': round(score, 1),
            'recommendation': self._get_recommendation(score, trend_direction),
            'last_update': hist_data.index[-1].strftime('%Y-%m-%d')
        }
    
    def _judge_trend(self, price, ma5, ma10, ma20) -> str:
        """判断趋势方向"""
        if price > ma5 > ma10 > ma20:
            return 'strong_uptrend'  # 强势上升
        elif price > ma5 > ma10:
            return 'uptrend'  # 上升趋势
        elif price > ma20:
            return 'weak_uptrend'  # 弱势上升
        elif price < ma5 < ma10 < ma20:
            return 'strong_downtrend'  # 强势下降
        elif price < ma5 < ma10:
            return 'downtrend'  # 下降趋势
        elif price < ma20:
            return 'weak_downtrend'  # 弱势下降
        else:
            return 'sideways'  # 震荡
    
    def _get_trend_strength(self, trend_direction: str, momentum_5d: float) -> str:
        """获取趋势强度"""
        if 'strong' in trend_direction:
            return 'strong'
        elif abs(momentum_5d) > 5:
            return 'moderate'
        else:
            return 'weak'
    
    def _calculate_trend_score(self, trend, mom5, mom20, vol_trend, volatility) -> float:
        """计算趋势评分"""
        score = 50  # 基础分
        
        # 趋势方向得分
        if trend == 'strong_uptrend':
            score += 30
        elif trend == 'uptrend':
            score += 20
        elif trend == 'weak_uptrend':
            score += 10
        elif trend == 'strong_downtrend':
            score -= 30
        elif trend == 'downtrend':
            score -= 20
        elif trend == 'weak_downtrend':
            score -= 10
        
        # 动量得分
        if mom5 > 0:
            score += min(mom5, 10)  # 最多加10分
        else:
            score += max(mom5, -10)  # 最多减10分
        
        # 成交量得分
        if vol_trend == 'increasing':
            score += 5
        elif vol_trend == 'decreasing':
            score -= 5
        
        # 波动率扣分（波动率过高不好）
        if volatility > 40:
            score -= 10
        elif volatility > 30:
            score -= 5
        
        return max(0, min(100, score))
    
    def _get_recommendation(self, score: float, trend: str) -> str:
        """获取操作建议"""
        if score >= 70 and 'uptrend' in trend:
            return '买入'
        elif score >= 60 and 'uptrend' in trend:
            return '关注'
        elif score >= 50:
            return '观望'
        elif score >= 40:
            return '谨慎'
        else:
            return '回避'
    
    def analyze_watchlist(self, watchlist: list, period: str = "1mo") -> pd.DataFrame:
        """
        分析监控列表中的所有股票
        
        Args:
            watchlist: 股票列表，格式 [{'symbol': '000001.SZ', 'name': '平安银行'}, ...]
            period: 数据周期
        
        Returns:
            DataFrame，包含所有股票的趋势分析结果
        """
        results = []
        
        print(f"\n📊 开始分析 {len(watchlist)} 只股票的趋势...")
        
        for idx, stock in enumerate(watchlist, 1):
            symbol = stock.get('symbol', '')
            name = stock.get('name', '')
            
            if not symbol:
                continue
            
            print(f"  [{idx}/{len(watchlist)}] 分析 {name} ({symbol})...", end='\r')
            
            try:
                trend_result = self.analyze_trend(symbol, period)
                trend_result['name'] = name
                results.append(trend_result)
            except Exception as e:
                logger.warning(f"分析 {symbol} 失败: {e}")
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'status': 'error',
                    'message': str(e)
                })
        
        print(" " * 80, end='\r')  # 清除进度行
        print(f"✅ 分析完成，共 {len(results)} 只股票")
        
        return pd.DataFrame(results)


def load_watchlist_from_results(results_dir: str = "results") -> list:
    """从结果文件加载监控列表"""
    import glob
    
    if not os.path.exists(results_dir):
        return []
    
    # 查找最新的推荐股票文件
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
    print(f"📂 加载监控列表: {os.path.basename(latest_file)}")
    
    df = pd.read_csv(latest_file, encoding='utf-8-sig')
    
    watchlist = []
    for _, row in df.iterrows():
        symbol = str(row.get('symbol', '')).strip()
        name = str(row.get('name', '')).strip()
        if symbol:
            watchlist.append({'symbol': symbol, 'name': name})
    
    return watchlist


def display_trend_report(df: pd.DataFrame):
    """显示趋势分析报告"""
    if df.empty:
        print("没有可显示的数据")
        return
    
    # 过滤成功分析的数据
    success_df = df[df['status'] == 'success'].copy()
    
    if success_df.empty:
        print("没有成功分析的数据")
        return
    
    # 按评分排序
    success_df = success_df.sort_values('score', ascending=False)
    
    print("\n" + "="*100)
    print("📈 股票趋势分析报告")
    print("="*100)
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"分析股票数: {len(success_df)}")
    print()
    
    # 按趋势分类显示
    print("🔥 强势上升趋势 (评分≥70):")
    strong_uptrend = success_df[
        (success_df['score'] >= 70) & 
        (success_df['trend_direction'].str.contains('uptrend', na=False))
    ]
    if not strong_uptrend.empty:
        for _, row in strong_uptrend.iterrows():
            print(f"  ⭐ {row['name']} ({row['symbol']})")
            print(f"     价格: {row['current_price']:.2f} | 趋势: {row['trend_direction']} | 评分: {row['score']}")
            print(f"     5日涨幅: {row['momentum_5d']:+.2f}% | 20日涨幅: {row['momentum_20d']:+.2f}%")
            print(f"     建议: {row['recommendation']} | 支撑: {row['support']:.2f} | 阻力: {row['resistance']:.2f}")
            print()
    else:
        print("  暂无")
        print()
    
    print("📊 上升趋势 (评分60-70):")
    uptrend = success_df[
        (success_df['score'] >= 60) & (success_df['score'] < 70) &
        (success_df['trend_direction'].str.contains('uptrend', na=False))
    ]
    if not uptrend.empty:
        for _, row in uptrend.head(5).iterrows():
            print(f"  📈 {row['name']} ({row['symbol']})")
            print(f"     价格: {row['current_price']:.2f} | 评分: {row['score']} | 建议: {row['recommendation']}")
            print()
    else:
        print("  暂无")
        print()
    
    print("⚠️  下降趋势 (评分<50):")
    downtrend = success_df[
        (success_df['score'] < 50) |
        (success_df['trend_direction'].str.contains('downtrend', na=False))
    ]
    if not downtrend.empty:
        for _, row in downtrend.head(5).iterrows():
            print(f"  ⬇️  {row['name']} ({row['symbol']})")
            print(f"     价格: {row['current_price']:.2f} | 评分: {row['score']} | 趋势: {row['trend_direction']}")
            print()
    else:
        print("  暂无")
        print()
    
    # 统计信息
    print("="*100)
    print("📊 统计信息:")
    print(f"  强势上升: {len(strong_uptrend)} 只")
    print(f"  上升趋势: {len(uptrend)} 只")
    print(f"  下降趋势: {len(downtrend)} 只")
    print(f"  平均评分: {success_df['score'].mean():.1f}")
    print("="*100)


def main():
    """主函数"""
    print("="*100)
    print("📈 股票趋势分析工具（可在任何时间运行）")
    print("="*100)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 加载监控列表
    print("\n1. 加载监控列表...")
    watchlist = load_watchlist_from_results()
    
    if not watchlist:
        print("❌ 未找到监控列表，请先运行盘前分析（main_realtime.py）")
        print("\n或者手动指定股票代码：")
        print("  示例: python analyze_stock_trends.py --symbols 000001.SZ,600519.SS")
        return
    
    print(f"✅ 加载成功: {len(watchlist)} 只股票")
    
    # 2. 初始化分析器
    print("\n2. 初始化分析器...")
    data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.3)
    analyzer = StockTrendAnalyzer(data_fetcher)
    
    # 3. 分析趋势（使用 try/finally 确保 BaoStock 连接关闭）
    print("\n3. 分析股票趋势（基于历史K线数据）...")
    try:
        results_df = analyzer.analyze_watchlist(watchlist, period="1mo")
    finally:
        data_fetcher.close()  # 批量处理完成后关闭 BaoStock 连接
    
    # 4. 显示报告
    display_trend_report(results_df)
    
    # 5. 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"results/trend_analysis_{timestamp}.csv"
    
    # 只保存成功分析的数据
    success_df = results_df[results_df['status'] == 'success']
    if not success_df.empty:
        success_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n💾 结果已保存: {output_file}")
    
    print("\n✅ 分析完成！")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="股票趋势分析工具")
    parser.add_argument('--symbols', type=str, help='手动指定股票代码，用逗号分隔，如: 000001.SZ,600519.SS')
    parser.add_argument('--period', type=str, default='1mo', choices=['1mo', '3mo', '6mo'], 
                       help='分析周期（默认1mo）')
    
    args = parser.parse_args()
    
    # 如果指定了股票代码，使用指定的
    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(',')]
        watchlist = [{'symbol': s, 'name': s} for s in symbols if s]
        
        if watchlist:
            print(f"使用指定的股票代码: {len(watchlist)} 只")
            data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.3)
            analyzer = StockTrendAnalyzer(data_fetcher)
            try:
                results_df = analyzer.analyze_watchlist(watchlist, period=args.period)
                display_trend_report(results_df)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = f"results/trend_analysis_{timestamp}.csv"
                success_df = results_df[results_df['status'] == 'success']
                if not success_df.empty:
                    success_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"\n💾 结果已保存: {output_file}")
            finally:
                data_fetcher.close()  # 确保关闭 BaoStock 连接
        else:
            print("❌ 无效的股票代码")
    else:
        main()
