"""
精简版数据获取器 - 专为短线策略设计
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

class ShortTermDataFetcher:
    """短线策略专用数据获取器"""
    
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
    
    def debug_print_all_sectors(self):
        """打印AKShare支持的所有行业板块名称（用于调试）"""
        try:
            # 获取板块列表的接口
            sector_list_df = ak.stock_board_industry_name_em()
            print("="*60)
            print(f"AKShare 支持的行业板块名称列表（共{len(sector_list_df)}个）:")
            print("="*60)
            
            if not sector_list_df.empty:
                # 首先打印列名，以便确认
                print("数据列名:", list(sector_list_df.columns))
                print()
                
                # 尝试找到包含名称的列
                name_column = None
                for col in sector_list_df.columns:
                    col_str = str(col).lower()
                    if '名称' in str(col) or 'name' in col_str or '板块' in str(col):
                        name_column = col
                        break
                
                if name_column:
                    sectors = sector_list_df[name_column].dropna().unique()
                    print(f"找到 {len(sectors)} 个板块（使用列: {name_column}）:")
                    print()
                    for idx, sector in enumerate(sorted(sectors), 1):
                        print(f"{idx:3d}. {sector}")
                    
                    # 额外信息：检查配置文件中使用的板块是否在列表中
                    print("\n" + "="*60)
                    print("检查配置文件中的板块名称:")
                    print("="*60)
                    try:
                        import yaml
                        import os
                        config_path = os.path.join(
                            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            'config', 'sectors.yaml'
                        )
                        if os.path.exists(config_path):
                            with open(config_path, 'r', encoding='utf-8') as f:
                                config = yaml.safe_load(f)
                            focus_sectors = config.get('focus_sectors', [])
                            
                            print(f"\n配置文件中定义了 {len(focus_sectors)} 个板块:")
                            for sector in focus_sectors:
                                sector_name = sector.get('code', '')
                                if sector_name in sectors:
                                    print(f"  ✓ {sector_name} - 匹配成功")
                                else:
                                    print(f"  ✗ {sector_name} - 未找到，可能需要修正")
                                    # 尝试模糊匹配
                                    similar = [s for s in sectors if sector_name in s or s in sector_name]
                                    if similar:
                                        print(f"    可能的匹配: {similar[:3]}")
                        else:
                            print(f"配置文件不存在: {config_path}")
                    except Exception as e:
                        print(f"检查配置文件时出错: {e}")
                else:
                    # 如果找不到，打印前几行看看结构
                    print("未找到名称列，显示数据结构:")
                    print(sector_list_df.head(20))
                    print("\n所有列的数据类型:")
                    print(sector_list_df.dtypes)
        except Exception as e:
            print(f"获取板块列表失败，错误: {e}")
            import traceback
            traceback.print_exc()
            # 尝试另一个可能的接口
            try:
                print("\n尝试使用备用接口...")
                alternative_list = ak.stock_board_industry_name_ths()
                print("备用接口获取成功，列名:", list(alternative_list.columns))
                print(alternative_list.head(20))
            except Exception as e2:
                print(f"备用接口也失败: {e2}")
                import traceback
                traceback.print_exc()
    
    # 在data_fetcher.py中尝试不同的板块名称
    def get_sector_stocks(self, sector_name: str) -> pd.DataFrame:
        """获取板块成分股（增强兼容版）"""
        self._rate_limit_check()
        
        # 板块名称映射表：常见的名称差异映射
        # 这是修复的核心，如果标准名称失败，会尝试这些别名
        sector_alias_map = {
            "煤炭开采": ["煤炭行业", "煤炭", "煤炭开采加工"],
            "计算机应用": ["软件开发", "计算机软件", "信息技术"],
            "半导体": ["半导体及元件"],
            "化学原料": ["化工原料"],
            # 你可以根据需要继续添加其他映射
        }
        
        # 首先尝试用户传入的原始名称
        stocks_df = self._try_fetch_sector_data(sector_name)
        
        # 如果失败，尝试使用映射表中的别名
        if (stocks_df is None or stocks_df.empty) and sector_name in sector_alias_map:
            logger.info(f"板块 '{sector_name}' 获取失败，尝试别名...")
            for alias in sector_alias_map[sector_name]:
                stocks_df = self._try_fetch_sector_data(alias)
                if stocks_df is not None and not stocks_df.empty:
                    logger.info(f"使用别名 '{alias}' 成功获取数据")
                    sector_name = alias  # 更新为实际使用的名称
                    break
        
        if stocks_df is None or stocks_df.empty:
            logger.error(f"所有尝试均失败，无法获取板块 '{sector_name}' 数据")
            return pd.DataFrame()
        
        # 以下是原有的数据处理逻辑（保持你测试成功的版本）
        result = pd.DataFrame()
        # 查找代码列...
        for col in stocks_df.columns:
            col_str = str(col).lower()
            if '代码' in col_str or 'code' in col_str:
                result['code'] = stocks_df[col].astype(str).str.zfill(6)
            elif '名称' in col_str or 'name' in col_str:
                result['name'] = stocks_df[col]
            elif '最新价' in col_str or 'close' in col_str:
                result['price'] = pd.to_numeric(stocks_df[col], errors='coerce')
            elif '涨跌幅' in col_str:
                result['change_pct'] = pd.to_numeric(stocks_df[col], errors='coerce')
        
        if 'code' in result.columns:
            result['symbol'] = result['code'].apply(
                lambda x: f"{x}.SS" if x.startswith('6') else f"{x}.SZ"
            )
        
        logger.info(f"获取板块 [{sector_name}] 成分股 {len(result)} 只")
        return result

    def _try_fetch_sector_data(self, sector_name: str):
        """尝试获取板块数据的内部函数，包含异常捕获"""
        try:
            # 这是你原来调用的接口，根据[citation:2]，这是获取行业成分股的正确接口
            return ak.stock_board_industry_cons_em(symbol=sector_name)
        except Exception as e:
            logger.debug(f"尝试获取板块 '{sector_name}' 时出错: {e}")
            return None
    
    
    def get_stock_history(self, symbol: str, period: str = "6mo") -> pd.DataFrame:
        """获取个股历史数据（完全修复版）"""
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
            
            # 获取数据
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                adjust="qfq"
            )
            
            if df is None or df.empty:
                logger.warning(f"股票 {symbol} 返回空数据")
                return pd.DataFrame()
            
            # 调试：打印原始数据信息
            logger.debug(f"原始数据形状: {df.shape}")
            logger.debug(f"原始列名: {list(df.columns)}")
            
            # 方法：先收集所有列，再设置索引
            df_clean = pd.DataFrame()
            
            # 第一步：找到日期列并提取
            date_col = None
            date_values = None
            for col in df.columns:
                col_str = str(col).lower()
                if '日期' in col_str:
                    date_col = col
                    date_values = pd.to_datetime(df[col])
                    break
            
            # 如果没找到日期列，使用第一列
            if date_col is None:
                date_values = pd.to_datetime(df.iloc[:, 0])
            
            # 第二步：识别并提取所有价格和成交量列（在设置索引之前）
            column_mapping = {}
            for col in df.columns:
                col_str = str(col).lower()
                if col == date_col or (date_col is None and col == df.columns[0]):
                    continue  # 跳过日期列
                elif '收盘' in col_str:
                    column_mapping['close'] = col
                elif '开盘' in col_str:
                    column_mapping['open'] = col
                elif '最高' in col_str:
                    column_mapping['high'] = col
                elif '最低' in col_str:
                    column_mapping['low'] = col
                elif '成交量' in col_str:
                    column_mapping['volume'] = col
                elif '成交额' in col_str:
                    column_mapping['amount'] = col
            
            # 第三步：创建新的DataFrame，先添加所有列
            for new_col, old_col in column_mapping.items():
                df_clean[new_col] = pd.to_numeric(df[old_col], errors='coerce')
            
            # 第四步：设置日期索引
            if date_values is not None and len(date_values) == len(df_clean):
                df_clean.index = date_values
            else:
                # 如果长度不匹配，使用默认索引
                logger.warning(f"日期列长度不匹配，使用默认索引")
            
            # 确保必要列存在
            if 'close' not in df_clean.columns:
                logger.error(f"股票 {symbol} 数据缺少收盘价列")
                logger.error(f"可用列: {list(df_clean.columns)}")
                logger.error(f"原始列: {list(df.columns)}")
                return pd.DataFrame()
            
            # 检查数据质量
            if df_clean['close'].isna().all():
                logger.warning(f"股票 {symbol} 收盘价全部为NaN")
                logger.debug(f"原始数据前3行:\n{df.head(3)}")
            
            # 填充缺失值（只填充中间缺失，不填充全部为NaN的情况）
            df_clean = df_clean.ffill().bfill()
            
            return df_clean.sort_index()
            
        except Exception as e:
            logger.error(f"获取股票 {symbol} 历史数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()

def test_data_fetcher():
    """测试数据获取器（修复版）"""
    print("=== 测试数据获取模块 ===")
    
    # 初始化日志
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 初始化
    fetcher = ShortTermDataFetcher(use_cache=False)
    
    # 可选：打印所有支持的板块名称（用于调试）
    # 取消下面的注释来查看所有可用板块
    # print("\n" + "="*60)
    # print("调试：打印所有支持的板块名称")
    # print("="*60)
    # fetcher.debug_print_all_sectors()
    # print("\n" + "="*60)
    
    # 测试1: 获取板块成分股
    print("\n1. 测试板块成分股获取...")
    sector_name = "有色金属"
    stocks = fetcher.get_sector_stocks(sector_name)
    
    if not stocks.empty:
        print(f"板块 '{sector_name}' 成分股示例:")
        print(stocks[['symbol', 'name', 'price', 'change_pct']].head(10))
        print(f"总共获取到 {len(stocks)} 只股票")
        
        # 选择更适合的股票进行测试（避开科创板，优先主板）
        suitable_stocks = []
        for _, stock in stocks.iterrows():
            symbol = stock['symbol']
            # 优先选择主板和中小板股票
            if symbol.startswith('60') or symbol.startswith('00') or symbol.startswith('30'):
                suitable_stocks.append((symbol, stock['name']))
                if len(suitable_stocks) >= 5:  # 选5只作为备选
                    break
        
        if suitable_stocks:
            test_symbol, test_name = suitable_stocks[0]
            print(f"\n选择测试股票: {test_symbol} ({test_name}) - 非科创板")
        else:
            # 如果没有合适的，就选第一只
            test_symbol = stocks.iloc[0]['symbol']
            test_name = stocks.iloc[0]['name']
            print(f"\n选择测试股票: {test_symbol} ({test_name})")
            
    else:
        print(f"未能获取板块 {sector_name} 数据")
        test_symbol = "000001.SZ"  # 默认测试平安银行
        test_name = "平安银行"
        print(f"使用默认测试股票: {test_symbol} ({test_name})")
    
    # 测试2: 获取个股历史数据
    print("\n2. 测试个股历史数据获取...")
    print(f"测试股票: {test_symbol} ({test_name})")
    history = fetcher.get_stock_history(test_symbol, period="1mo")
    
    if not history.empty:
        print(f"股票 {test_symbol} 历史数据:")
        print(f"时间范围: {history.index[0].date()} 到 {history.index[-1].date()}")
        print(f"数据条数: {len(history)}")
        
        # 检查是否有有效数据
        if 'close' in history.columns:
            # 检查非NaN值
            valid_data = history['close'].dropna()
            if len(valid_data) > 0:
                print(f"有效数据条数: {len(valid_data)}")
                print(f"最新收盘价: {valid_data.iloc[-1]}")
                
                # 显示数据概览
                print(f"\n数据概览:")
                print(f"开盘价 range: [{history['open'].min():.2f}, {history['open'].max():.2f}]")
                print(f"收盘价 range: [{history['close'].min():.2f}, {history['close'].max():.2f}]")
                print(f"最高价 range: [{history['high'].min():.2f}, {history['high'].max():.2f}]")
                print(f"最低价 range: [{history['low'].min():.2f}, {history['low'].max():.2f}]")
                if 'volume' in history.columns:
                    print(f"成交量 mean: {history['volume'].mean():.0f}")
            else:
                print("警告: 收盘价数据全为NaN")
        
        # 显示最近5天的数据
        print("\n最近5个交易日数据:")
        if 'close' in history.columns:
            cols_to_show = ['open', 'high', 'low', 'close']
            if 'volume' in history.columns:
                cols_to_show.append('volume')
            
            # 只显示非全NaN的行
            recent_data = history[cols_to_show].tail(5)
            if not recent_data.empty:
                print(recent_data)
            else:
                print("最近交易日数据全为NaN")
    else:
        print(f"未能获取股票 {test_symbol} 历史数据")
    
    print("\n=== 测试完成 ===")
    return fetcher

if __name__ == "__main__":
    # 直接运行此文件进行测试
    test_data_fetcher()