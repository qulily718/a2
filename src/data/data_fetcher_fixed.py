"""
修复版数据获取器 - 专为短线策略设计
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import Optional, List, Dict
import logging
import sys

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShortTermDataFetcherFixed:
    """修复版短线策略专用数据获取器"""
    
    def __init__(self, use_cache: bool = True, rate_limit: float = 0.5):
        """
        Args:
            use_cache: 是否使用缓存
            rate_limit: 请求间隔（秒）
        """
        self.use_cache = use_cache
        self.rate_limit = rate_limit
        self.last_request_time = 0
        
    def _rate_limit_check(self):
        """简单的速率控制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()
    
    def get_sector_stocks(self, sector_name: str) -> pd.DataFrame:
        """获取板块成分股（直接使用akshare原始数据）"""
        self._rate_limit_check()
        
        try:
            stocks_df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if stocks_df is None or stocks_df.empty:
                logger.warning(f"板块 {sector_name} 返回空数据")
                return pd.DataFrame()
            
            # 直接打印原始数据查看结构
            logger.info(f"原始数据列名: {list(stocks_df.columns)}")
            logger.info(f"原始数据形状: {stocks_df.shape}")
            logger.info(f"原始数据类型: {stocks_df.dtypes}")
            
            # 创建一个新的DataFrame，直接使用原始数据
            result = pd.DataFrame()
            
            # 尝试直接映射常见的列名模式
            column_mapping = {}
            for col in stocks_df.columns:
                col_str = str(col).strip().lower()
                if any(keyword in col_str for keyword in ['代码', 'code']):
                    column_mapping[col] = 'code'
                elif any(keyword in col_str for keyword in ['名称', 'name']):
                    column_mapping[col] = 'name'
                elif any(keyword in col_str for keyword in ['最新价', '收盘', 'close', 'price']):
                    column_mapping[col] = 'price'
                elif any(keyword in col_str for keyword in ['涨跌幅', 'change', '涨幅']):
                    column_mapping[col] = 'change_pct'
            
            # 应用列名映射
            for old_col, new_col in column_mapping.items():
                result[new_col] = stocks_df[old_col]
            
            # 如果code列不存在，尝试从其他列推断
            if 'code' not in result.columns and len(stocks_df.columns) > 0:
                result['code'] = stocks_df.iloc[:, 0].astype(str)
            
            # 清理代码
            if 'code' in result.columns:
                result['code'] = result['code'].astype(str).str.replace(r'\D', '', regex=True)
                result['code'] = result['code'].apply(lambda x: x.zfill(6) if len(x) == 6 else x)
                
                # 添加完整symbol
                result['symbol'] = result['code'].apply(
                    lambda x: f"{x}.SS" if x.startswith('6') or x.startswith('688') else f"{x}.SZ"
                )
            
            # 转换数值列
            if 'price' in result.columns:
                result['price'] = pd.to_numeric(result['price'], errors='coerce')
            if 'change_pct' in result.columns:
                result['change_pct'] = pd.to_numeric(result['change_pct'], errors='coerce')
            
            logger.info(f"获取板块 [{sector_name}] 成分股 {len(result)} 只")
            
            # 显示部分数据供调试
            if not result.empty:
                logger.info("板块数据示例:")
                logger.info(result[['symbol', 'code', 'name', 'price', 'change_pct']].head(3).to_string())
            
            return result
            
        except Exception as e:
            logger.error(f"获取板块 {sector_name} 失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def get_stock_history(self, symbol: str, period: str = "6mo") -> pd.DataFrame:
        """获取个股历史数据（直接处理原始DataFrame）"""
        self._rate_limit_check()
        
        try:
            # 提取代码
            code = symbol.replace('.SS', '').replace('.SZ', '')
            
            # 计算日期范围
            end_date = datetime.now()
            if period == "6mo":
                start_date = end_date - timedelta(days=180)
            elif period == "3mo":
                start_date = end_date - timedelta(days=90)
            elif period == "1mo":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = end_date - timedelta(days=180)
            
            logger.info(f"获取股票 {symbol} 数据，时间范围: {start_date.date()} 到 {end_date.date()}")
            
            # 获取数据
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                adjust="qfq"
            )
            
            if df is None or df.empty:
                logger.warning(f"股票 {symbol} 历史数据为空")
                return pd.DataFrame()
            
            # 打印原始数据信息
            logger.info(f"原始数据形状: {df.shape}")
            logger.info(f"原始列名: {list(df.columns)}")
            logger.info(f"前3行数据:\n{df.head(3)}")
            
            # 方法1: 直接使用原始列名，不重命名
            result = df.copy()
            
            # 确保有日期列
            date_col = None
            for col in result.columns:
                col_str = str(col).lower()
                if '日期' in col_str:
                    date_col = col
                    break
            
            if date_col:
                result['date'] = pd.to_datetime(result[date_col])
                result.set_index('date', inplace=True)
            else:
                # 使用第一列作为日期
                result['date'] = pd.to_datetime(result.iloc[:, 0])
                result.set_index('date', inplace=True)
            
            # 识别价格列
            price_columns = {}
            for col in df.columns:
                col_str = str(col).lower()
                if '收盘' in col_str:
                    price_columns[col] = 'close'
                elif '开盘' in col_str:
                    price_columns[col] = 'open'
                elif '最高' in col_str:
                    price_columns[col] = 'high'
                elif '最低' in col_str:
                    price_columns[col] = 'low'
                elif '成交量' in col_str:
                    price_columns[col] = 'volume'
                elif '成交额' in col_str:
                    price_columns[col] = 'amount'
            
            # 重命名列
            result = result.rename(columns=price_columns)
            
            # 确保必要列存在
            required_cols = ['open', 'high', 'low', 'close']
            missing_cols = [col for col in required_cols if col not in result.columns]
            
            if missing_cols:
                logger.warning(f"缺失必要列: {missing_cols}")
                
                # 尝试从其他列推断
                if 'close' not in result.columns:
                    # 尝试找到价格列（任何包含数字的列）
                    for col in result.columns:
                        if result[col].dtype in [np.float64, np.int64]:
                            if 'close' not in result.columns:
                                result['close'] = result[col]
                                logger.info(f"使用列 {col} 作为收盘价")
                                break
            
            # 转换数值类型
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                if col in result.columns:
                    result[col] = pd.to_numeric(result[col], errors='coerce')
            
            # 检查数据质量
            if 'close' in result.columns:
                non_nan_count = result['close'].notna().sum()
                logger.info(f"收盘价非NaN数据条数: {non_nan_count}/{len(result)}")
                
                if non_nan_count > 0:
                    logger.info(f"收盘价范围: [{result['close'].min():.2f}, {result['close'].max():.2f}]")
                    logger.info(f"最新收盘价: {result['close'].iloc[-1]}")
                else:
                    logger.warning("收盘价全部为NaN，显示原始数据:")
                    logger.info(df.head())
            
            return result
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} 历史数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()

def test_data_fetcher_detailed():
    """详细测试数据获取器"""
    print("=" * 60)
    print("详细测试数据获取模块")
    print("=" * 60)
    
    # 初始化
    fetcher = ShortTermDataFetcherFixed(use_cache=False)
    
    # 测试1: 获取板块成分股
    print("\n1. 测试板块成分股获取...")
    sector_name = "有色金属"
    stocks = fetcher.get_sector_stocks(sector_name)
    
    if not stocks.empty:
        print(f"\n板块 '{sector_name}' 成分股 (显示前10只):")
        print(stocks[['symbol', 'name', 'price', 'change_pct']].head(10).to_string())
        print(f"\n总共获取到 {len(stocks)} 只股票")
        
        # 选择非科创板的股票进行测试
        suitable_stocks = []
        for _, stock in stocks.iterrows():
            symbol = stock['symbol']
            # 排除科创板
            if not symbol.startswith('688'):
                suitable_stocks.append((symbol, stock['name']))
                if len(suitable_stocks) >= 5:
                    break
        
        if suitable_stocks:
            test_symbol, test_name = suitable_stocks[0]
            print(f"\n选择测试股票: {test_symbol} ({test_name}) - 非科创板")
        else:
            # 如果没有合适的，使用主板股票
            test_symbol = "000001.SZ"
            test_name = "平安银行"
            print(f"\n使用默认测试股票: {test_symbol} ({test_name})")
    else:
        print("获取板块数据失败，使用默认测试股票")
        test_symbol = "000001.SZ"
        test_name = "平安银行"
    
    # 测试2: 获取个股历史数据
    print("\n" + "=" * 60)
    print("2. 测试个股历史数据获取...")
    print(f"测试股票: {test_symbol} ({test_name})")
    
    history = fetcher.get_stock_history(test_symbol, period="1mo")
    
    if not history.empty:
        print(f"\n股票 {test_symbol} 历史数据:")
        print(f"时间范围: {history.index[0].date()} 到 {history.index[-1].date()}")
        print(f"数据条数: {len(history)}")
        print(f"数据列: {list(history.columns)}")
        
        # 显示数据概览
        print("\n数据概览:")
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in history.columns:
                non_nan = history[col].notna().sum()
                if non_nan > 0:
                    print(f"  {col}: {non_nan}条有效数据, 范围: [{history[col].min():.2f}, {history[col].max():.2f}]")
                else:
                    print(f"  {col}: 全部为NaN")
        
        # 显示最近5天的数据
        print("\n最近5个交易日数据:")
        display_cols = []
        for col in ['open', 'high', 'low', 'close']:
            if col in history.columns:
                display_cols.append(col)
        
        if 'volume' in history.columns:
            display_cols.append('volume')
        
        if display_cols:
            recent_data = history[display_cols].tail(5)
            print(recent_data.to_string())
        else:
            print("没有可显示的数据列")
    else:
        print(f"未能获取股票 {test_symbol} 历史数据")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    return fetcher

if __name__ == "__main__":
    test_data_fetcher_detailed()
