"""
缓存管理器 - 减少API调用
"""
import os
import pickle
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """数据缓存管理器"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
    
    def _get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        safe_key = key.replace('/', '_').replace('\\', '_')
        return os.path.join(self.cache_dir, f"{safe_key}.pkl")
    
    def get(self, key: str, max_age_hours: int = 1) -> Optional[pd.DataFrame]:
        """获取缓存数据"""
        cache_path = self._get_cache_path(key)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            # 检查文件年龄
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
            if datetime.now() - file_time > timedelta(hours=max_age_hours):
                return None
            
            # 加载缓存
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
            logger.debug(f"从缓存加载: {key}")
            return data
            
        except Exception as e:
            logger.warning(f"读取缓存失败 {key}: {e}")
            return None
    
    def set(self, key: str, data: pd.DataFrame):
        """保存数据到缓存"""
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
            logger.debug(f"保存到缓存: {key}")
        except Exception as e:
            logger.warning(f"保存缓存失败 {key}: {e}")
