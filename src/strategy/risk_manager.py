"""
风险管理模块
"""
import yaml
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class RiskManager:
    """风险管理器"""
    
    def __init__(self, risk_config_path: str = "config/risk_rules.yaml"):
        with open(risk_config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
    
    def calculate_max_position(self, stock_info: Dict, current_positions: List[Dict]) -> float:
        """
        计算单只股票的最大仓位
        """
        risk_level = stock_info.get('risk_level', 'medium')
        risk_limits = self.config['risk_management']['risk_limits']
        
        if risk_level == 'high':
            max_pos = risk_limits['high_risk_max_position']
        elif risk_level == 'low':
            max_pos = risk_limits['low_risk_max_position']
        else:
            max_pos = risk_limits['medium_risk_max_position']
        
        # 检查板块仓位限制
        sector = stock_info.get('sector', '')
        sector_positions = sum([p.get('position', 0) for p in current_positions 
                               if p.get('sector') == sector])
        max_sector_pos = self.config['risk_management']['position']['max_position_per_sector']
        
        if sector_positions >= max_sector_pos:
            return 0
        
        return min(max_pos, max_sector_pos - sector_positions)
    
    def should_stop_loss(self, entry_price: float, current_price: float) -> bool:
        """判断是否应该止损"""
        if not self.config['risk_management']['stop_loss']['enabled']:
            return False
        
        loss_ratio = (current_price - entry_price) / entry_price
        threshold = self.config['risk_management']['stop_loss']['loss_threshold']
        
        return loss_ratio <= threshold
    
    def should_stop_profit(self, entry_price: float, current_price: float) -> bool:
        """判断是否应该止盈"""
        if not self.config['risk_management']['stop_profit']['enabled']:
            return False
        
        profit_ratio = (current_price - entry_price) / entry_price
        threshold = self.config['risk_management']['stop_profit']['profit_threshold']
        
        return profit_ratio >= threshold
