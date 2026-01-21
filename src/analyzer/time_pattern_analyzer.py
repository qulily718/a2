"""
全时段市场分析器 - 支持不同时间段的走势分析
"""
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class TimePatternAnalyzer:
    """时间模式分析器"""
    
    # 市场时间段定义
    MARKET_SESSIONS = {
        'morning_open': (time(9, 30), time(10, 0)),      # 开盘30分钟
        'morning_mid': (time(10, 0), time(11, 30)),      # 上午盘中
        'noon_break': (time(11, 30), time(13, 0)),       # 午间休市
        'afternoon_early': (time(13, 0), time(14, 0)),   # 下午开盘
        'afternoon_mid': (time(14, 0), time(14, 30)),    # 下午盘中
        'closing': (time(14, 30), time(15, 0)),          # 尾盘30分钟
        'post_market': (time(15, 0), time(21, 0)),       # 盘后分析
        'pre_market': (time(21, 0), time(9, 30))         # 盘前预判
    }
    
    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher
        self.current_mode = self._get_current_mode()
        
    def _get_current_mode(self) -> str:
        """获取当前时间对应的分析模式"""
        now = datetime.now().time()
        current_date = datetime.now()
        
        # 检查是否交易日
        weekday = current_date.weekday()
        if weekday >= 5:  # 周末
            return 'weekend_analysis'
        
        for mode, (start, end) in self.MARKET_SESSIONS.items():
            if start <= now < end:
                return mode
        
        return 'general_analysis'
    
    def analyze_current_market(self, watchlist: List[Dict]) -> Dict:
        """
        根据当前时间分析市场
        
        Args:
            watchlist: 监控股票列表
            
        Returns:
            分析结果
        """
        mode = self.current_mode
        logger.info(f"当前分析模式: {mode}")
        
        analysis_methods = {
            'morning_open': self._analyze_morning_open,
            'morning_mid': self._analyze_morning_mid,
            'noon_break': self._analyze_noon_break,
            'afternoon_early': self._analyze_afternoon_early,
            'afternoon_mid': self._analyze_afternoon_mid,
            'closing': self._analyze_closing,
            'post_market': self._analyze_post_market,
            'pre_market': self._analyze_pre_market,
            'weekend_analysis': self._analyze_weekend,
            'general_analysis': self._analyze_general
        }
        
        method = analysis_methods.get(mode, self._analyze_general)
        return method(watchlist)
    
    def _analyze_morning_open(self, watchlist: List[Dict]) -> Dict:
        """分析开盘30分钟"""
        logger.info("分析模式: 开盘30分钟 (9:30-10:00)")
        
        analysis_results = []
        
        for stock in watchlist[:15]:  # 限制数量
            try:
                # 获取历史数据作为参考（实际应获取实时分时数据）
                hist_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if hist_data is not None and not hist_data.empty:
                    analysis = self._analyze_opening_pattern(hist_data, stock)
                    analysis_results.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析股票 {stock.get('name', 'N/A')} 失败: {e}")
        
        return {
            'mode': 'morning_open',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '开盘强势股识别、资金流向判断',
            'recommendation': self._generate_opening_recommendation(analysis_results),
            'stocks_analyzed': len(analysis_results),
            'results': analysis_results[:10]
        }
    
    def _analyze_morning_mid(self, watchlist: List[Dict]) -> Dict:
        """分析上午盘中(10:00-11:30)"""
        logger.info("分析模式: 上午盘中 (10:00-11:30)")
        
        analysis_results = []
        
        for stock in watchlist[:20]:
            try:
                hist_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if hist_data is not None and not hist_data.empty:
                    analysis = self._analyze_morning_pattern(hist_data, stock)
                    analysis_results.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'morning_mid',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '上午趋势确认、回调机会识别',
            'recommendation': self._generate_mid_morning_recommendation(analysis_results),
            'stocks_analyzed': len(analysis_results),
            'results': sorted(analysis_results, key=lambda x: x.get('score', 0), reverse=True)[:10]
        }
    
    def _analyze_noon_break(self, watchlist: List[Dict]) -> Dict:
        """分析午间休市(11:30-13:00)"""
        logger.info("分析模式: 午间休市 (11:30-13:00)")
        
        morning_summary = []
        
        for stock in watchlist[:25]:
            try:
                hist_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if hist_data is not None and not hist_data.empty:
                    analysis = self._analyze_morning_performance(hist_data, stock)
                    morning_summary.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        afternoon_outlook = self._predict_afternoon_outlook(morning_summary)
        
        return {
            'mode': 'noon_break',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '上午总结、下午走势预判',
            'morning_summary': morning_summary[:15],
            'afternoon_outlook': afternoon_outlook,
            'recommendation': self._generate_noon_recommendation(morning_summary, afternoon_outlook)
        }
    
    def _analyze_afternoon_early(self, watchlist: List[Dict]) -> Dict:
        """分析下午开盘(13:00-14:00)"""
        logger.info("分析模式: 下午开盘 (13:00-14:00)")
        
        analysis_results = []
        
        for stock in watchlist[:20]:
            try:
                hist_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if hist_data is not None and not hist_data.empty:
                    analysis = self._analyze_afternoon_open_pattern(hist_data, stock)
                    analysis_results.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'afternoon_early',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '下午开盘走势、上午强势股延续性',
            'recommendation': self._generate_afternoon_open_recommendation(analysis_results),
            'stocks_analyzed': len(analysis_results),
            'results': sorted(analysis_results, key=lambda x: x.get('afternoon_score', 0), reverse=True)[:10]
        }
    
    def _analyze_afternoon_mid(self, watchlist: List[Dict]) -> Dict:
        """分析下午盘中(14:00-14:30)"""
        logger.info("分析模式: 下午盘中 (14:00-14:30)")
        
        analysis_results = []
        
        for stock in watchlist[:20]:
            try:
                hist_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if hist_data is not None and not hist_data.empty:
                    analysis = self._analyze_afternoon_mid_pattern(hist_data, stock)
                    analysis_results.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'afternoon_mid',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '全天趋势确认、尾盘机会识别',
            'recommendation': self._generate_afternoon_mid_recommendation(analysis_results),
            'stocks_analyzed': len(analysis_results),
            'results': sorted(analysis_results, key=lambda x: x.get('trend_score', 0), reverse=True)[:10]
        }
    
    def _analyze_closing(self, watchlist: List[Dict]) -> Dict:
        """分析尾盘(14:30-15:00)"""
        logger.info("分析模式: 尾盘30分钟 (14:30-15:00)")
        
        analysis_results = []
        
        for stock in watchlist[:15]:
            try:
                hist_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if hist_data is not None and not hist_data.empty:
                    analysis = self._analyze_closing_pattern(hist_data, stock)
                    analysis_results.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'closing',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '尾盘抢筹/抛售、次日预判',
            'recommendation': self._generate_closing_recommendation(analysis_results),
            'stocks_analyzed': len(analysis_results),
            'results': sorted(analysis_results, key=lambda x: x.get('closing_score', 0), reverse=True)[:10]
        }
    
    def _analyze_post_market(self, watchlist: List[Dict]) -> Dict:
        """分析盘后(15:00后)"""
        logger.info("分析模式: 盘后分析 (15:00后)")
        
        daily_analysis = []
        
        for stock in watchlist:
            try:
                daily_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if daily_data is not None and not daily_data.empty:
                    analysis = self._analyze_daily_performance(daily_data, stock)
                    daily_analysis.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'post_market',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '全天复盘、技术指标分析、次日策略',
            'daily_summary': daily_analysis[:20],
            'tomorrow_outlook': self._predict_tomorrow_outlook(daily_analysis),
            'recommendation': self._generate_post_market_recommendation(daily_analysis)
        }
    
    def _analyze_pre_market(self, watchlist: List[Dict]) -> Dict:
        """分析盘前(前一日21:00-次日9:30)"""
        logger.info("分析模式: 盘前预判 (夜盘/早盘)")
        
        previous_day_analysis = []
        
        for stock in watchlist[:30]:
            try:
                previous_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if previous_data is not None and not previous_data.empty:
                    analysis = self._analyze_pre_market_pattern(previous_data, stock)
                    previous_day_analysis.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'pre_market',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '隔夜消息、技术形态、当日策略',
            'stock_analysis': previous_day_analysis[:15],
            'opening_prediction': self._predict_opening_impact(previous_day_analysis),
            'recommendation': self._generate_pre_market_recommendation(previous_day_analysis)
        }
    
    def _analyze_weekend(self, watchlist: List[Dict]) -> Dict:
        """分析周末"""
        logger.info("分析模式: 周末分析")
        
        weekly_analysis = []
        
        for stock in watchlist[:25]:
            try:
                weekly_data = self.data_fetcher.get_stock_history(stock['symbol'], period='3mo')
                
                if weekly_data is not None and not weekly_data.empty:
                    analysis = self._analyze_weekly_pattern(weekly_data, stock)
                    weekly_analysis.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'weekend_analysis',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '周线分析、技术形态、下周策略',
            'weekly_analysis': weekly_analysis[:15],
            'next_week_outlook': self._predict_next_week_outlook(weekly_analysis),
            'recommendation': self._generate_weekend_recommendation(weekly_analysis)
        }
    
    def _analyze_general(self, watchlist: List[Dict]) -> Dict:
        """通用分析（其他时间）"""
        logger.info("分析模式: 通用分析")
        
        general_analysis = []
        
        for stock in watchlist[:20]:
            try:
                recent_data = self.data_fetcher.get_stock_history(stock['symbol'], period='1mo')
                
                if recent_data is not None and not recent_data.empty:
                    analysis = self._analyze_general_pattern(recent_data, stock)
                    general_analysis.append(analysis)
                    
            except Exception as e:
                logger.error(f"分析失败: {e}")
        
        return {
            'mode': 'general_analysis',
            'analysis_time': datetime.now().strftime('%H:%M'),
            'focus': '近期走势、技术指标、买卖点',
            'results': sorted(general_analysis, key=lambda x: x.get('opportunity_score', 0), reverse=True)[:10],
            'recommendation': self._generate_general_recommendation(general_analysis)
        }
    
    # 以下是分析辅助方法
    def _analyze_opening_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析开盘模式"""
        if hist_data.empty or len(hist_data) < 5:
            return {'symbol': stock['symbol'], 'name': stock.get('name', ''), 'score': 0}
        
        closes = hist_data['close']
        score = 50
        
        # 最近5日表现
        if len(closes) >= 5:
            change_5d = (closes.iloc[-1] / closes.iloc[-5] - 1) * 100
            if change_5d > 2:
                score += 20
            elif change_5d > 0:
                score += 10
        
        # 均线位置
        if len(closes) >= 20:
            ma20 = closes.rolling(20).mean().iloc[-1]
            if closes.iloc[-1] > ma20:
                score += 15
        
        return {
            'symbol': stock['symbol'],
            'name': stock.get('name', ''),
            'score': min(100, score),
            'opening_change': round(change_5d, 2) if 'change_5d' in locals() else 0,
            'signal': '强势' if score > 70 else '一般' if score > 60 else '弱势'
        }
    
    def _analyze_morning_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析上午模式"""
        if hist_data.empty:
            return {'symbol': stock['symbol'], 'name': stock.get('name', ''), 'score': 50, 'change_pct': 0}
        
        closes = hist_data['close']
        score = 50
        change_pct = 0
        
        # 计算涨跌幅（使用监控列表中的实时数据，如果没有则用历史数据计算）
        if stock.get('change_pct'):
            change_pct = stock.get('change_pct', 0)
        elif len(closes) >= 2:
            # 用历史数据计算（昨日到今日的变化）
            change_pct = (closes.iloc[-1] / closes.iloc[-2] - 1) * 100
        
        # 根据涨跌幅调整评分
        if change_pct > 5:
            score += 35
        elif change_pct > 3:
            score += 25
        elif change_pct > 1:
            score += 15
        elif change_pct > 0:
            score += 5
        
        if len(closes) >= 10:
            ma10 = closes.rolling(10).mean().iloc[-1]
            if closes.iloc[-1] > ma10:
                score += 20
        
        return {
            'symbol': stock['symbol'],
            'name': stock.get('name', ''),
            'score': min(100, score),
            'change_pct': round(change_pct, 2),
            'trend': 'up' if score > 60 else 'down',
            'signal': '强势' if score > 75 else '一般' if score > 55 else '弱势'
        }
    
    def _analyze_morning_performance(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析上午表现"""
        return self._analyze_morning_pattern(hist_data, stock)
    
    def _analyze_afternoon_open_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析下午开盘模式"""
        analysis = self._analyze_morning_pattern(hist_data, stock)
        analysis['afternoon_score'] = analysis.get('score', 50)
        return analysis
    
    def _analyze_afternoon_mid_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析下午盘中模式"""
        if hist_data.empty:
            return {'symbol': stock['symbol'], 'name': stock.get('name', ''), 'trend_score': 50}
        
        closes = hist_data['close']
        score = 50
        
        if len(closes) >= 20:
            ma20 = closes.rolling(20).mean().iloc[-1]
            current = closes.iloc[-1]
            if current > ma20:
                score += 25
        
        return {
            'symbol': stock['symbol'],
            'name': stock.get('name', ''),
            'trend_score': min(100, score)
        }
    
    def _analyze_closing_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析尾盘模式"""
        if hist_data.empty:
            return {'symbol': stock['symbol'], 'name': stock.get('name', ''), 'closing_score': 50}
        
        closes = hist_data['close']
        score = 50
        
        # 尾盘通常关注全天表现
        if len(closes) >= 5:
            change = (closes.iloc[-1] / closes.iloc[-5] - 1) * 100
            if change > 1:
                score += 20
        
        return {
            'symbol': stock['symbol'],
            'name': stock.get('name', ''),
            'closing_score': min(100, score)
        }
    
    def _analyze_daily_performance(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析全天表现"""
        if hist_data.empty:
            return {'symbol': stock['symbol'], 'name': stock.get('name', ''), 'score': 50}
        
        closes = hist_data['close']
        score = 50
        
        if len(closes) >= 20:
            ma20 = closes.rolling(20).mean().iloc[-1]
            current = closes.iloc[-1]
            
            if current > ma20:
                score += 20
            
            # 动量
            if len(closes) >= 5:
                momentum = (current / closes.iloc[-5] - 1) * 100
                if momentum > 3:
                    score += 15
        
        return {
            'symbol': stock['symbol'],
            'name': stock.get('name', ''),
            'score': min(100, score),
            'trend': 'up' if score > 60 else 'down'
        }
    
    def _analyze_pre_market_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析盘前模式"""
        return self._analyze_daily_performance(hist_data, stock)
    
    def _analyze_weekly_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析周线模式"""
        if hist_data.empty:
            return {'symbol': stock['symbol'], 'name': stock.get('name', ''), 'score': 50, 'pattern': 'unknown'}
        
        closes = hist_data['close']
        score = 50
        
        if len(closes) >= 20:
            ma20 = closes.rolling(20).mean().iloc[-1]
            if closes.iloc[-1] > ma20:
                score += 25
                pattern = '上升趋势'
            else:
                pattern = '下降趋势'
        else:
            pattern = '震荡'
        
        return {
            'symbol': stock['symbol'],
            'name': stock.get('name', ''),
            'score': min(100, score),
            'pattern': pattern
        }
    
    def _analyze_general_pattern(self, hist_data: pd.DataFrame, stock: Dict) -> Dict:
        """分析通用模式"""
        if hist_data.empty:
            return {'symbol': stock['symbol'], 'name': stock.get('name', ''), 'opportunity_score': 50}
        
        closes = hist_data['close']
        score = 50
        
        if len(closes) >= 10:
            ma10 = closes.rolling(10).mean().iloc[-1]
            if closes.iloc[-1] > ma10:
                score += 20
        
        return {
            'symbol': stock['symbol'],
            'name': stock.get('name', ''),
            'opportunity_score': min(100, score)
        }
    
    # 推荐生成方法
    def _generate_opening_recommendation(self, results: List[Dict]) -> str:
        """生成开盘推荐"""
        if not results:
            return "无数据，建议观望"
        
        strong_stocks = [r for r in results if r.get('score', 0) > 70]
        
        if len(strong_stocks) >= 3:
            return f"开盘强势，建议关注前{min(3, len(strong_stocks))}只强势股"
        elif len(strong_stocks) >= 1:
            return "局部强势，可选择性操作"
        else:
            return "开盘偏弱，建议谨慎"
    
    def _generate_mid_morning_recommendation(self, results: List[Dict]) -> str:
        """生成上午盘中推荐"""
        if not results:
            return "无数据，建议观望"
        
        up_count = len([r for r in results if r.get('trend') == 'up'])
        total = len(results)
        
        if up_count / total > 0.6:
            return "上午趋势良好，可寻找回调买入机会"
        else:
            return "上午分化明显，建议谨慎操作"
    
    def _generate_noon_recommendation(self, morning_summary: List[Dict], outlook: Dict) -> str:
        """生成午间推荐"""
        if not morning_summary:
            return "无数据，建议观望"
        
        up_count = len([s for s in morning_summary if s.get('trend') == 'up'])
        total = len(morning_summary)
        
        if total == 0:
            return "无数据，建议观望"
        
        up_ratio = up_count / total
        
        if up_ratio > 0.7:
            return "上午普涨，下午有望延续，可寻找机会"
        elif up_ratio > 0.4:
            return "上午分化，下午可能震荡，谨慎操作"
        else:
            return "上午偏弱，下午可能调整，建议观望"
    
    def _generate_afternoon_open_recommendation(self, results: List[Dict]) -> str:
        """生成下午开盘推荐"""
        if not results:
            return "无数据，建议观望"
        
        strong = len([r for r in results if r.get('afternoon_score', 0) > 65])
        
        if strong >= 3:
            return "下午开盘延续强势，可关注"
        else:
            return "下午开盘偏弱，建议观望"
    
    def _generate_afternoon_mid_recommendation(self, results: List[Dict]) -> str:
        """生成下午盘中推荐"""
        if not results:
            return "无数据，建议观望"
        
        return "下午盘中，关注尾盘机会"
    
    def _generate_closing_recommendation(self, results: List[Dict]) -> str:
        """生成尾盘推荐"""
        if not results:
            return "无数据，建议观望"
        
        return "尾盘谨慎操作，关注异动股票"
    
    def _generate_post_market_recommendation(self, daily_analysis: List[Dict]) -> str:
        """生成盘后推荐"""
        if not daily_analysis:
            return "无数据，建议观望"
        
        good_stocks = [s for s in daily_analysis if s.get('score', 0) > 65]
        
        if len(good_stocks) >= 5:
            return f"市场表现良好，{len(good_stocks)}只股票技术面向好，可关注"
        elif len(good_stocks) >= 2:
            return "市场分化，可精选个股操作"
        else:
            return "市场偏弱，建议谨慎"
    
    def _generate_pre_market_recommendation(self, previous_day_analysis: List[Dict]) -> str:
        """生成盘前推荐"""
        if not previous_day_analysis:
            return "无数据，建议观望"
        
        good = len([s for s in previous_day_analysis if s.get('score', 0) > 65])
        
        if good >= 3:
            return f"技术面良好，{good}只股票值得关注"
        else:
            return "技术面一般，建议谨慎"
    
    def _generate_weekend_recommendation(self, weekly_analysis: List[Dict]) -> str:
        """生成周末推荐"""
        if not weekly_analysis:
            return "无数据，建议观望"
        
        up_trend = len([s for s in weekly_analysis if s.get('pattern') == '上升趋势'])
        
        if up_trend >= 5:
            return f"周线趋势良好，{up_trend}只股票处于上升趋势"
        else:
            return "周线趋势一般，建议精选个股"
    
    def _generate_general_recommendation(self, general_analysis: List[Dict]) -> str:
        """生成通用推荐"""
        if not general_analysis:
            return "无数据，建议观望"
        
        opportunities = len([s for s in general_analysis if s.get('opportunity_score', 0) > 60])
        
        if opportunities >= 3:
            return f"发现{opportunities}个操作机会，可关注"
        else:
            return "机会有限，建议观望"
    
    # 预测方法
    def _predict_afternoon_outlook(self, morning_summary: List[Dict]) -> Dict:
        """预测下午走势"""
        if not morning_summary:
            return {'trend': 'neutral', 'confidence': 0.5}
        
        up_count = len([s for s in morning_summary if s.get('trend') == 'up'])
        total = len(morning_summary)
        
        if up_count / total > 0.6:
            return {'trend': 'bullish', 'confidence': 0.7}
        elif up_count / total > 0.4:
            return {'trend': 'neutral', 'confidence': 0.6}
        else:
            return {'trend': 'bearish', 'confidence': 0.7}
    
    def _predict_tomorrow_outlook(self, daily_analysis: List[Dict]) -> Dict:
        """预测明日走势"""
        if not daily_analysis:
            return {'trend': 'neutral', 'confidence': 0.5}
        
        good = len([s for s in daily_analysis if s.get('score', 0) > 65])
        total = len(daily_analysis)
        
        if good / total > 0.5:
            return {'trend': 'bullish', 'confidence': 0.65}
        else:
            return {'trend': 'neutral', 'confidence': 0.6}
    
    def _predict_next_week_outlook(self, weekly_analysis: List[Dict]) -> Dict:
        """预测下周走势"""
        if not weekly_analysis:
            return {'trend': 'neutral', 'confidence': 0.5}
        
        up = len([s for s in weekly_analysis if s.get('pattern') == '上升趋势'])
        total = len(weekly_analysis)
        
        if up / total > 0.5:
            return {'trend': 'bullish', 'confidence': 0.65}
        else:
            return {'trend': 'neutral', 'confidence': 0.6}
    
    def _predict_opening_impact(self, previous_day_analysis: List[Dict]) -> Dict:
        """预测开盘影响"""
        if not previous_day_analysis:
            return {'impact': 'neutral', 'strength': 0.5}
        
        good = len([s for s in previous_day_analysis if s.get('score', 0) > 65])
        total = len(previous_day_analysis)
        
        if good / total > 0.5:
            return {'impact': 'positive', 'strength': 0.7}
        else:
            return {'impact': 'neutral', 'strength': 0.5}
