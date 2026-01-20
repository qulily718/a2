"""
趋势跟随策略
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class TrendFollower:
    """趋势跟随策略"""
    
    def __init__(self, ma_short: int = 5, ma_long: int = 20):
        self.ma_short = ma_short
        self.ma_long = ma_long
    
    def analyze_trend(self, hist_data: pd.DataFrame) -> Dict:
        """
        分析趋势信号
        返回: 趋势分析结果
        """
        if len(hist_data) < self.ma_long:
            return {
                'signal': 'neutral',
                'strength': 0,
                'reason': '数据不足'
            }
        
        closes = hist_data['close']
        ma_short = closes.rolling(self.ma_short).mean()
        ma_long = closes.rolling(self.ma_long).mean()
        
        current_price = closes.iloc[-1]
        current_ma_short = ma_short.iloc[-1]
        current_ma_long = ma_long.iloc[-1]
        
        # 判断趋势
        if current_ma_short > current_ma_long and current_price > current_ma_short:
            signal = 'bullish'
            strength = min(100, (current_price / current_ma_long - 1) * 1000)
        elif current_ma_short < current_ma_long and current_price < current_ma_short:
            signal = 'bearish'
            strength = min(100, abs((current_price / current_ma_long - 1) * 1000))
        else:
            signal = 'neutral'
            strength = 0
        
        return {
            'signal': signal,
            'strength': round(strength, 2),
            'ma_short': round(current_ma_short, 2),
            'ma_long': round(current_ma_long, 2),
            'price': round(current_price, 2)
        }
