"""
短线稳健策略个股筛选器 - 完整版
基于市场分析器推荐的板块，执行严格的多维度筛选
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Any
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StockFilter:
    """短线稳健策略个股筛选器"""
    
    # 修改 stock_filter.py 中的 __init__ 方法
    def __init__(self, data_fetcher, config: Dict = None):
        self.data_fetcher = data_fetcher
        self.config = self._merge_config(config)
        
    def _merge_config(self, user_config: Dict = None) -> Dict:
        """合并用户配置和默认配置"""
        default_config = self._default_config()
        
        if user_config is None:
            return default_config
        
        # 深度合并配置
        merged_config = default_config.copy()
        
        for key, value in user_config.items():
            if key in merged_config and isinstance(merged_config[key], dict) and isinstance(value, dict):
                # 如果是字典，递归合并
                merged_config[key].update(value)
            else:
                merged_config[key] = value
        
        return merged_config
    
    def _default_config(self) -> Dict:
        """默认配置参数"""
        return {
            # 技术面参数
            'min_price': 5.0,           # 最低股价
            'max_price': 200.0,         # 最高股价
            'min_volume': 10000000,     # 最低日均成交量（股）
            'min_trading_days': 60,     # 最少交易日
            
            # 趋势条件
            'ma_periods': [5, 10, 20],  # 均线周期
            'price_above_ma': 20,       # 价格在X日线上方
            
            # 动量条件
            'min_5d_change': 2.0,       # 5日最小涨幅(%)
            'max_5d_change': 15.0,      # 5日最大涨幅(%)
            'min_20d_change': 5.0,      # 20日最小涨幅(%)
            
            # 波动率条件
            'max_volatility': 0.4,      # 最大年化波动率
            
            # 资金流向
            'volume_ratio_threshold': 1.2,  # 成交量比率阈值
            
            # 评分权重
            'weights': {
                'trend': 0.25,      # 趋势强度
                'momentum': 0.25,   # 动量
                'volume': 0.20,     # 成交量
                'volatility': 0.15, # 波动率
                'position': 0.15    # 相对位置
            }
        }
    
    def filter_stocks_in_sector(self, sector_code: str, 
                               max_stocks: int = 10,
                               strict_mode: bool = True) -> List[Dict]:
        """
        筛选板块内符合短线稳健策略的个股
        
        Args:
            sector_code: 板块代码
            max_stocks: 返回的最大股票数量
            strict_mode: 是否启用严格模式
            
        Returns:
            筛选后的股票列表，按综合评分排序
        """
        logger.info(f"开始筛选板块 [{sector_code}] 的个股...")
        
        # 1. 获取板块成分股
        stocks_df = self.data_fetcher.get_sector_stocks(sector_code)
        if stocks_df.empty:
            logger.warning(f"板块 {sector_code} 无成分股数据")
            return []
        
        # 显示板块基本信息
        logger.info(f"板块 {sector_code} 共有 {len(stocks_df)} 只成分股")
        
        # 2. 多阶段筛选
        filtered_stocks = []
        
        # 第一阶段：快速预筛选
        pre_filtered = self._pre_filter(stocks_df)
        logger.info(f"预筛选后剩余 {len(pre_filtered)} 只股票")
        
        if len(pre_filtered) == 0:
            return []
        
        # 第二阶段：详细分析
        for idx, stock in enumerate(pre_filtered.iterrows()):
            _, stock_data = stock
            symbol = stock_data.get('symbol', '')
            
            if not symbol:
                continue
            
            # 显示进度
            if (idx + 1) % 10 == 0:
                logger.info(f"分析进度: {idx + 1}/{len(pre_filtered)}")
            
            try:
                # 获取历史数据
                hist_data = self.data_fetcher.get_stock_history(symbol, period="3mo")
                if hist_data.empty or len(hist_data) < self.config['min_trading_days']:
                    continue
                
                # 详细技术分析
                analysis_result = self._analyze_stock_technicals(hist_data, stock_data)
                
                # 计算综合评分
                total_score, breakdown = self._calculate_total_score(analysis_result)
                
                # 检查是否通过筛选
                if self._pass_screening(analysis_result, strict_mode):
                    stock_info = {
                        'symbol': symbol,
                        'name': stock_data.get('name', ''),
                        'price': stock_data.get('price', 0),
                        'change_pct': stock_data.get('change_pct', 0),
                        'sector': sector_code,
                        'total_score': round(total_score, 1),
                        'rank_reasons': self._generate_rank_reasons(analysis_result),
                        'risk_level': self._assess_risk_level(analysis_result),
                        'entry_signal': self._generate_entry_signal(analysis_result),
                        'stop_loss': self._calculate_stop_loss(hist_data, stock_data),
                        'analysis_details': analysis_result,
                        'score_breakdown': breakdown
                    }
                    filtered_stocks.append(stock_info)
                    
            except Exception as e:
                logger.error(f"分析股票 {symbol} 失败: {e}")
                continue
        
        # 第三阶段：排序并返回
        if filtered_stocks:
            # 按综合评分排序
            filtered_stocks.sort(key=lambda x: x['total_score'], reverse=True)
            
            # 输出筛选结果
            logger.info(f"板块 {sector_code} 筛选完成，找到 {len(filtered_stocks)} 只符合策略的股票")
            
            # 只返回前max_stocks只
            return filtered_stocks[:max_stocks]
        else:
            logger.info(f"板块 {sector_code} 未找到符合策略的股票")
            return []
    
    def _pre_filter(self, stocks_df: pd.DataFrame) -> pd.DataFrame:
        """
        快速预筛选，过滤明显不合格的股票
        """
        filtered = stocks_df.copy()
        
        # 1. 过滤ST、*ST、退市股票
        name_condition = filtered['name'].apply(
            lambda x: not any(keyword in str(x).upper() 
                             for keyword in ['ST', '*ST', '退市', '暂停'])
        )
        filtered = filtered[name_condition]
        
        # 2. 过滤价格范围外的
        price_condition = (filtered['price'] >= self.config['min_price']) & \
                         (filtered['price'] <= self.config['max_price'])
        filtered = filtered[price_condition]
        
        # 3. 过滤涨幅异常的（涨停/跌停过多）
        if 'change_pct' in filtered.columns:
            change_condition = (filtered['change_pct'].abs() <= 11.0)  # 非涨跌停
            filtered = filtered[change_condition]
        
        return filtered
    
    def _analyze_stock_technicals(self, hist_data: pd.DataFrame, 
                                 stock_data: pd.Series) -> Dict[str, Any]:
        """
        详细技术面分析
        """
        closes = hist_data['close']
        volumes = hist_data['volume']
        highs = hist_data['high']
        lows = hist_data['low']
        
        analysis = {}
        
        # 1. 趋势分析
        analysis['trend'] = self._analyze_trend(closes)
        
        # 2. 动量分析
        analysis['momentum'] = self._analyze_momentum(closes)
        
        # 3. 成交量分析
        analysis['volume'] = self._analyze_volume(closes, volumes)
        
        # 4. 波动率分析
        analysis['volatility'] = self._analyze_volatility(closes)
        
        # 5. 相对位置分析
        analysis['position'] = self._analyze_position(closes, highs, lows)
        
        # 6. 资金流向（简化版）
        analysis['money_flow'] = self._analyze_money_flow(closes, volumes)
        
        # 7. 形态识别（基础）
        analysis['pattern'] = self._detect_patterns(closes)
        
        return analysis
    
    def _analyze_trend(self, closes: pd.Series) -> Dict[str, Any]:
        """趋势强度分析"""
        result = {'score': 50, 'details': {}}
        
        # 计算各周期均线
        for period in self.config['ma_periods']:
            ma = closes.rolling(period).mean()
            result['details'][f'ma{period}'] = ma.iloc[-1]
        
        # 当前价格
        current_price = closes.iloc[-1]
        
        # 判断均线排列
        ma20 = result['details']['ma20']
        ma10 = result['details']['ma10']
        ma5 = result['details']['ma5']
        
        # 多头排列加分
        if ma5 > ma10 > ma20 and current_price > ma5:
            result['score'] += 20
            result['details']['alignment'] = '多头排列'
        elif current_price > ma20:
            result['score'] += 10
            result['details']['alignment'] = '站上20日线'
        else:
            result['score'] -= 15
            result['details']['alignment'] = '空头排列'
        
        # 均线斜率
        ma20_slope = self._calculate_slope(result['details']['ma20'], 
                                          closes.rolling(20).mean().iloc[-5])
        if ma20_slope > 0:
            result['score'] += 5
            result['details']['ma20_slope'] = f'上升({ma20_slope:.3f})'
        
        return result
    
    def _analyze_momentum(self, closes: pd.Series) -> Dict[str, Any]:
        """动量分析"""
        result = {'score': 50, 'details': {}}
        
        if len(closes) < 20:
            return result
        
        # 计算不同周期涨幅
        periods = [1, 3, 5, 10, 20]
        for period in periods:
            if len(closes) >= period:
                change = (closes.iloc[-1] / closes.iloc[-period] - 1) * 100
                result['details'][f'{period}d_change'] = round(change, 2)
        
        # 5日涨幅评分
        change_5d = result['details'].get('5d_change', 0)
        if self.config['min_5d_change'] <= change_5d <= self.config['max_5d_change']:
            result['score'] += 15  # 适度上涨
            result['details']['5d_status'] = '适中'
        elif change_5d > self.config['max_5d_change']:
            result['score'] -= 10  # 涨幅过大
            result['details']['5d_status'] = '过大'
        else:
            result['score'] -= 5   # 涨幅不足
            result['details']['5d_status'] = '不足'
        
        # 20日涨幅要求
        change_20d = result['details'].get('20d_change', 0)
        if change_20d >= self.config['min_20d_change']:
            result['score'] += 10
            result['details']['20d_status'] = '达标'
        else:
            result['score'] -= 5
            result['details']['20d_status'] = '不达标'
        
        # RSI动量指标
        rsi = self._calculate_rsi(closes, period=14)
        result['details']['rsi'] = round(rsi, 2) if not pd.isna(rsi) else 0
        
        # RSI在合理区间
        if 30 <= rsi <= 70:
            result['score'] += 5
            result['details']['rsi_status'] = '合理'
        elif rsi > 70:
            result['score'] -= 5
            result['details']['rsi_status'] = '超买'
        else:
            result['score'] -= 5
            result['details']['rsi_status'] = '超卖'
        
        return result
    
    def _analyze_volume(self, closes: pd.Series, volumes: pd.Series) -> Dict[str, Any]:
        """成交量分析"""
        result = {'score': 50, 'details': {}}
        
        if len(volumes) < 20:
            return result
        
        # 成交量均线
        volume_ma5 = volumes.rolling(5).mean().iloc[-1]
        volume_ma20 = volumes.rolling(20).mean().iloc[-1]
        
        result['details']['volume_ma5'] = volume_ma5
        result['details']['volume_ma20'] = volume_ma20
        
        # 量比
        volume_ratio = volumes.iloc[-1] / volume_ma20
        result['details']['volume_ratio'] = round(volume_ratio, 2)
        
        # 量价配合
        price_change = (closes.iloc[-1] / closes.iloc[-5] - 1) * 100
        
        if volume_ratio > self.config['volume_ratio_threshold'] and price_change > 0:
            result['score'] += 15  # 放量上涨
            result['details']['price_volume'] = '放量上涨'
        elif volume_ratio > self.config['volume_ratio_threshold'] and price_change < 0:
            result['score'] -= 10  # 放量下跌
            result['details']['price_volume'] = '放量下跌'
        elif volume_ratio < 0.8 and price_change < 0:
            result['score'] += 5   # 缩量下跌
            result['details']['price_volume'] = '缩量下跌'
        else:
            result['details']['price_volume'] = '量价平淡'
        
        # 成交量趋势
        recent_avg = volumes.iloc[-5:].mean()
        older_avg = volumes.iloc[-20:-15].mean()
        if recent_avg > older_avg:
            result['score'] += 5
            result['details']['volume_trend'] = '上升'
        
        return result
    
    def _analyze_volatility(self, closes: pd.Series) -> Dict[str, Any]:
        """波动率分析"""
        result = {'score': 50, 'details': {}}
        
        if len(closes) < 20:
            return result
        
        # 计算日收益率
        returns = closes.pct_change().dropna()
        
        # 年化波动率
        volatility = returns.std() * np.sqrt(252)
        result['details']['annual_volatility'] = round(volatility, 3)
        
        # 波动率评分（越低越好，但也不能太低）
        if volatility <= 0.25:
            result['score'] += 15  # 低波动，稳健
            result['details']['volatility_status'] = '低'
        elif volatility <= self.config['max_volatility']:
            result['score'] += 5   # 中等波动
            result['details']['volatility_status'] = '中'
        else:
            result['score'] -= 15  # 高波动，风险大
            result['details']['volatility_status'] = '高'
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(closes)
        result['details']['max_drawdown'] = round(max_drawdown * 100, 2)
        
        if max_drawdown < 0.10:  # 最大回撤小于10%
            result['score'] += 10
            result['details']['drawdown_status'] = '良好'
        elif max_drawdown < 0.15:
            result['score'] += 5
            result['details']['drawdown_status'] = '一般'
        else:
            result['score'] -= 10
            result['details']['drawdown_status'] = '较差'
        
        return result
    
    def _analyze_position(self, closes: pd.Series, 
                         highs: pd.Series, 
                         lows: pd.Series) -> Dict[str, Any]:
        """相对位置分析"""
        result = {'score': 50, 'details': {}}
        
        if len(closes) < 20:
            return result
        
        current_price = closes.iloc[-1]
        
        # 近期高低点
        recent_high = highs.iloc[-20:].max()
        recent_low = lows.iloc[-20:].min()
        
        result['details']['recent_high'] = recent_high
        result['details']['recent_low'] = recent_low
        
        # 相对位置（0-1之间）
        if recent_high != recent_low:
            position_ratio = (current_price - recent_low) / (recent_high - recent_low)
            result['details']['position_ratio'] = round(position_ratio, 2)
            
            # 位置评分：不追高，不抄底
            if 0.3 <= position_ratio <= 0.7:
                result['score'] += 15  # 中间位置，安全
                result['details']['position_status'] = '安全区'
            elif position_ratio > 0.7:
                result['score'] -= 10  # 接近高点，风险高
                result['details']['position_status'] = '高位'
            else:
                result['score'] -= 5   # 低位，但可能弱势
                result['details']['position_status'] = '低位'
        
        return result
    
    def _analyze_money_flow(self, closes: pd.Series, 
                           volumes: pd.Series) -> Dict[str, Any]:
        """资金流向分析（简化版）"""
        result = {'score': 50, 'details': {}}
        
        if len(closes) < 5:
            return result
        
        # 计算价量关系
        price_changes = closes.diff()
        volume_changes = volumes.diff()
        
        # 简单的资金流向判断
        recent_days = 5
        money_inflow_days = 0
        
        for i in range(-recent_days, 0):
            if i >= -len(price_changes):
                if price_changes.iloc[i] > 0 and volume_changes.iloc[i] > 0:
                    money_inflow_days += 1
        
        result['details']['money_inflow_days'] = money_inflow_days
        result['details']['inflow_ratio'] = money_inflow_days / min(recent_days, len(price_changes))
        
        if money_inflow_days >= 3:
            result['score'] += 10
            result['details']['money_flow_status'] = '净流入'
        elif money_inflow_days <= 1:
            result['score'] -= 10
            result['details']['money_flow_status'] = '净流出'
        else:
            result['details']['money_flow_status'] = '平衡'
        
        return result
    
    def _detect_patterns(self, closes: pd.Series) -> Dict[str, Any]:
        """形态识别（基础版）"""
        result = {'score': 0, 'patterns': []}
        
        if len(closes) < 20:
            return result
        
        # 检查是否突破近期平台
        recent_range = closes.iloc[-10:].max() - closes.iloc[-10:].min()
        if recent_range / closes.iloc[-10:].mean() < 0.05:  # 窄幅震荡
            result['patterns'].append('平台整理')
            result['score'] += 5
        
        # 检查是否在上升通道中
        ma20 = closes.rolling(20).mean()
        ma60 = closes.rolling(60).mean()
        
        if closes.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1]:
            result['patterns'].append('上升趋势')
            result['score'] += 10
        
        return result
    
    def _calculate_total_score(self, analysis_result: Dict) -> Tuple[float, Dict]:
        """计算综合评分"""
        weights = self.config['weights']
        
        score_breakdown = {}
        total_score = 0
        
        for category, weight in weights.items():
            if category in analysis_result:
                category_score = analysis_result[category].get('score', 50)
                score_breakdown[category] = {
                    'raw_score': category_score,
                    'weighted_score': category_score * weight
                }
                total_score += category_score * weight
            else:
                score_breakdown[category] = {
                    'raw_score': 50,
                    'weighted_score': 50 * weight
                }
                total_score += 50 * weight
        
        # 确保分数在0-100之间
        total_score = max(0, min(100, total_score))
        
        return total_score, score_breakdown
    
    def _pass_screening(self, analysis_result: Dict, strict_mode: bool) -> bool:
        """检查是否通过筛选条件"""
        if strict_mode:
            # 严格模式：所有关键条件必须满足
            conditions = []
            
            # 1. 价格必须在20日线上方
            if 'trend' in analysis_result:
                trend_details = analysis_result['trend'].get('details', {})
                if trend_details.get('alignment') == '空头排列':
                    return False
            
            # 2. 5日涨幅在合理范围内
            if 'momentum' in analysis_result:
                momentum_details = analysis_result['momentum'].get('details', {})
                if momentum_details.get('5d_status') == '过大':
                    return False
            
            # 3. 波动率不能过高
            if 'volatility' in analysis_result:
                volatility_details = analysis_result['volatility'].get('details', {})
                if volatility_details.get('volatility_status') == '高':
                    return False
            
            # 4. 相对位置不能过高
            if 'position' in analysis_result:
                position_details = analysis_result['position'].get('details', {})
                if position_details.get('position_status') == '高位':
                    return False
            
            return True
        else:
            # 宽松模式：综合评分大于60即可
            total_score, _ = self._calculate_total_score(analysis_result)
            return total_score >= 60
    
    def _generate_rank_reasons(self, analysis_result: Dict) -> List[str]:
        """生成排名理由"""
        reasons = []
        
        # 从各个分析维度提取优点
        if 'trend' in analysis_result:
            trend_details = analysis_result['trend'].get('details', {})
            alignment = trend_details.get('alignment', '')
            if alignment == '多头排列':
                reasons.append("均线多头排列")
            elif alignment == '站上20日线':
                reasons.append("站稳20日线")
        
        if 'momentum' in analysis_result:
            momentum_details = analysis_result['momentum'].get('details', {})
            if momentum_details.get('5d_status') == '适中':
                reasons.append("短期动量适中")
            if momentum_details.get('20d_status') == '达标':
                reasons.append("中期趋势良好")
        
        if 'volume' in analysis_result:
            volume_details = analysis_result['volume'].get('details', {})
            if volume_details.get('price_volume') == '放量上涨':
                reasons.append("量价配合良好")
        
        if 'volatility' in analysis_result:
            volatility_details = analysis_result['volatility'].get('details', {})
            if volatility_details.get('volatility_status') == '低':
                reasons.append("波动率较低")
            if volatility_details.get('drawdown_status') == '良好':
                reasons.append("回撤控制良好")
        
        # 限制理由数量
        return reasons[:3] if len(reasons) > 3 else reasons
    
    def _assess_risk_level(self, analysis_result: Dict) -> str:
        """评估风险等级"""
        total_score, _ = self._calculate_total_score(analysis_result)
        
        if total_score >= 80:
            return "低风险"
        elif total_score >= 70:
            return "中低风险"
        elif total_score >= 60:
            return "中等风险"
        elif total_score >= 50:
            return "中高风险"
        else:
            return "高风险"
    
    def _generate_entry_signal(self, analysis_result: Dict) -> str:
        """生成入场信号"""
        signals = []
        
        if 'trend' in analysis_result:
            trend_details = analysis_result['trend'].get('details', {})
            if trend_details.get('alignment') == '多头排列':
                signals.append("趋势向上")
        
        if 'momentum' in analysis_result:
            momentum_details = analysis_result['momentum'].get('details', {})
            if momentum_details.get('5d_status') == '适中':
                signals.append("动量适中")
        
        if 'volume' in analysis_result:
            volume_details = analysis_result['volume'].get('details', {})
            if volume_details.get('price_volume') == '放量上涨':
                signals.append("放量启动")
        
        if signals:
            return " | ".join(signals)
        else:
            return "观望"
    
    def _calculate_stop_loss(self, hist_data: pd.DataFrame, 
                            stock_data: pd.Series) -> float:
        """计算止损位"""
        current_price = stock_data.get('price', 0)
        
        if current_price <= 0:
            return 0
        
        # 使用最近20日最低点作为止损参考
        recent_low = hist_data['low'].iloc[-20:].min()
        
        # 止损位：低于近期低点3%
        stop_loss = recent_low * 0.97
        
        return round(stop_loss, 2)
    
    def _calculate_slope(self, current_value: float, past_value: float) -> float:
        """计算斜率"""
        if past_value == 0:
            return 0
        return (current_value - past_value) / past_value
    
    def _calculate_rsi(self, closes: pd.Series, period: int = 14) -> float:
        """计算RSI指标"""
        if len(closes) < period + 1:
            return 50
        
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def _calculate_max_drawdown(self, closes: pd.Series) -> float:
        """计算最大回撤"""
        if len(closes) < 2:
            return 0
        
        cumulative_returns = (closes / closes.iloc[0]) - 1
        running_max = cumulative_returns.expanding().max()
        drawdown = cumulative_returns - running_max
        max_drawdown = drawdown.min()
        
        return abs(max_drawdown) if max_drawdown < 0 else 0
    
    def get_screening_report(self, filtered_stocks: List[Dict]) -> str:
        """生成筛选报告"""
        if not filtered_stocks:
            return "未找到符合策略的股票"
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("短线稳健策略 - 个股筛选报告")
        report_lines.append("=" * 80)
        report_lines.append(f"筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"筛选结果: 共找到 {len(filtered_stocks)} 只符合策略的股票")
        report_lines.append("")
        
        for i, stock in enumerate(filtered_stocks, 1):
            report_lines.append(f"{i}. {stock['name']} ({stock['symbol']})")
            report_lines.append(f"   评分: {stock['total_score']} | 价格: {stock['price']:.2f} | 涨幅: {stock['change_pct']:.2f}%")
            report_lines.append(f"   风险等级: {stock['risk_level']} | 信号: {stock['entry_signal']}")
            report_lines.append(f"   止损位: {stock['stop_loss']:.2f} | 推荐理由: {', '.join(stock['rank_reasons'])}")
            
            # 显示详细评分
            if 'score_breakdown' in stock:
                breakdown = stock['score_breakdown']
                breakdown_str = " | ".join([f"{k}:{v['raw_score']}" for k, v in breakdown.items()])
                report_lines.append(f"   评分详情: {breakdown_str}")
            
            report_lines.append("")
        
        # 风险分布统计
        risk_levels = [s['risk_level'] for s in filtered_stocks]
        risk_counts = {level: risk_levels.count(level) for level in set(risk_levels)}
        report_lines.append("风险分布统计:")
        for level, count in risk_counts.items():
            report_lines.append(f"  {level}: {count}只 ({count/len(filtered_stocks)*100:.1f}%)")
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)