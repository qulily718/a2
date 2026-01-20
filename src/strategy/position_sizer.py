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
