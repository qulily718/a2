"""
仓位计算器
"""
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class PositionSizer:
    """仓位计算器"""
    
    def __init__(self, risk_manager):
        self.risk_manager = risk_manager
    
    def calculate_position_size(self, stock_info: Dict, 
                               total_capital: float,
                               current_positions: List[Dict]) -> float:
        """
        计算建议仓位大小
        """
        # 获取最大仓位限制
        max_position_ratio = self.risk_manager.calculate_max_position(
            stock_info, current_positions
        )
        
        if max_position_ratio <= 0:
            return 0
        
        # 根据评分调整仓位
        score = stock_info.get('total_score', 50)
        score_multiplier = score / 100  # 0-1之间
        
        # 计算建议仓位
        suggested_ratio = max_position_ratio * score_multiplier
        
        # 确保不超过总仓位限制
        total_position_ratio = sum([p.get('position_ratio', 0) for p in current_positions])
        max_total = 0.8  # 最大总仓位80%
        
        if total_position_ratio + suggested_ratio > max_total:
            suggested_ratio = max(0, max_total - total_position_ratio)
        
        position_size = total_capital * suggested_ratio
        
        return round(position_size, 2)


class PositionManager:
    """仓位管理器（金字塔式仓位管理）"""
    
    def __init__(self, total_capital: float, max_risk_per_trade: float = 0.02):
        """
        Args:
            total_capital: 总资金
            max_risk_per_trade: 单笔最大风险比例（默认2%）
        """
        self.total_capital = total_capital
        self.max_risk_per_trade = max_risk_per_trade
        self.positions = {}
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, 
                               confidence: float = 0.7) -> float:
        """
        计算仓位大小
        
        Args:
            entry_price: 买入价格
            stop_loss: 止损价格
            confidence: 信心水平 (0-1)
            
        Returns:
            建议买入金额
        """
        # 计算风险金额
        risk_per_share = entry_price - stop_loss
        if risk_per_share <= 0:
            return 0
        
        # 单笔最大损失
        max_loss_amount = self.total_capital * self.max_risk_per_trade
        
        # 根据信心调整
        confidence_factor = min(1.0, confidence * 1.2)
        adjusted_max_loss = max_loss_amount * confidence_factor
        
        # 计算股数
        shares = adjusted_max_loss / risk_per_share
        position_value = shares * entry_price
        
        # 限制单只股票仓位
        max_position_per_stock = self.total_capital * 0.10  # 单只最大10%
        
        return min(position_value, max_position_per_stock)
    
    def suggest_buy_strategy(self, stock_data: Dict) -> Dict:
        """建议买入策略"""
        entry_price = stock_data.get('price', 0)
        stop_loss = stock_data.get('stop_loss', 0)
        
        if entry_price <= 0 or stop_loss <= 0:
            return {
                'total_position_value': 0,
                'suggested_shares': 0,
                'risk_amount': 0,
                'risk_percentage': 0,
                'position_percentage': 0
            }
        
        confidence = min(1.0, stock_data.get('total_score', 50) / 100)
        
        position_size = self.calculate_position_size(entry_price, stop_loss, confidence)
        
        shares = int(position_size / entry_price) if entry_price > 0 else 0
        risk_amount = (entry_price - stop_loss) * shares
        risk_percentage = (entry_price - stop_loss) / entry_price * 100 if entry_price > 0 else 0
        
        return {
            'total_position_value': round(position_size, 2),
            'suggested_shares': shares,
            'risk_amount': round(risk_amount, 2),
            'risk_percentage': round(risk_percentage, 2),
            'position_percentage': round(position_size / self.total_capital * 100, 2) if self.total_capital > 0 else 0
        }
