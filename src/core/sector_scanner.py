"""
板块强度扫描器
"""
import pandas as pd
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class SectorScanner:
    """板块扫描器"""
    
    def __init__(self, data_fetcher, market_analyzer):
        self.data_fetcher = data_fetcher
        self.market_analyzer = market_analyzer
    
    def scan_all_sectors(self, sector_list: List[Dict]) -> pd.DataFrame:
        """扫描所有板块"""
        return self.market_analyzer.analyze_sector_strength(sector_list)
    
    def get_top_sectors(self, sector_list: List[Dict], top_n: int = 5) -> List[Dict]:
        """获取前N个强势板块"""
        strength_df = self.scan_all_sectors(sector_list)
        if strength_df.empty:
            return []
        
        top_sectors = strength_df.head(top_n)
        return top_sectors.to_dict('records')
