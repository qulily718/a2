"""
数据验证器 - 确保数据质量
"""
import pandas as pd
import numpy as np
from typing import Tuple, List
import logging

logger = logging.getLogger(__name__)

class DataValidator:
    """数据验证器"""
    
    @staticmethod
    def validate_stock_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        验证股票数据质量
        返回: (是否有效, 错误列表)
        """
        errors = []
        
        if df.empty:
            return False, ["数据为空"]
        
        # 检查必要列
        required_cols = ['close']
        for col in required_cols:
            if col not in df.columns:
                errors.append(f"缺少必要列: {col}")
        
        if errors:
            return False, errors
        
        # 检查数据完整性
        if df['close'].isna().sum() > len(df) * 0.1:  # 超过10%缺失
            errors.append("收盘价缺失过多")
        
        # 检查异常值
        if (df['close'] <= 0).any():
            errors.append("存在非正价格")
        
        # 检查数据量
        if len(df) < 20:
            errors.append("数据量不足（少于20条）")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """清理数据"""
        df_clean = df.copy()
        
        # 移除异常值
        if 'close' in df_clean.columns:
            df_clean = df_clean[df_clean['close'] > 0]
        
        # 填充缺失值
        df_clean = df_clean.ffill().bfill()
        
        return df_clean
