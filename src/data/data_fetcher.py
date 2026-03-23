"""
精简版数据获取器 - 专为短线策略设计
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import Optional, List, Dict
import logging
import random

try:
    import baostock as bs  # type: ignore
except Exception:
    bs = None  # Optional dependency

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
        self.bs_logged_in = False  # BaoStock 连接状态（用于连接复用）
        
    def _rate_limit_check(self):
        """简单的速率控制"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()

    def _sleep_backoff(self, attempt: int, base: float = 0.8, cap: float = 8.0) -> None:
        """指数退避（带抖动），用于网络/上游偶发断连."""
        delay = min(cap, base * (2 ** attempt))
        delay = delay * (0.75 + random.random() * 0.5)  # jitter: 0.75~1.25
        time.sleep(delay)

    def _symbol_to_baostock_code(self, symbol: str) -> str:
        """000001.SZ -> sz.000001; 600519.SS -> sh.600519"""
        code = symbol.replace(".SS", "").replace(".SZ", "").strip()
        if symbol.endswith(".SS") or code.startswith("6"):
            return f"sh.{code}"
        return f"sz.{code}"

    def _ensure_bs_login(self, force_reconnect: bool = False) -> bool:
        """
        确保 BaoStock 已登录（连接复用，避免每只股票都 login/logout）
        Args:
            force_reconnect: 强制重新登录（用于连接失效时）
        Returns:
            True 如果已登录或登录成功，False 如果登录失败
        """
        if bs is None:
            return False
        
        if force_reconnect:
            self.bs_logged_in = False
        
        if self.bs_logged_in:
            return True
        
        login = bs.login()
        if login.error_code == "0":
            self.bs_logged_in = True
            logger.info("BaoStock 登录成功（连接复用）")
            return True
        else:
            logger.warning("BaoStock 登录失败: %s %s", login.error_code, login.error_msg)
            return False

    def _fetch_history_baostock(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        使用 BaoStock 获取日线（前复权由策略侧处理；这里提供原始日线/成交量）。
        返回列：open/high/low/close/volume/amount，index 为 datetime。
        注意：使用连接复用，不会自动 logout（批量处理时更高效）
        """
        if not self._ensure_bs_login():
            return pd.DataFrame()

        bs_code = self._symbol_to_baostock_code(symbol)
        # 注意：BaoStock 的 volume 通常是"手"，amount 是"元"
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2",  # 2: 不复权（更稳）；复权可在策略侧处理
        )
        if rs.error_code != "0":
            # 如果是"用户未登录"错误，尝试重新登录并重试一次
            if rs.error_code == "10001001":
                logger.warning("BaoStock 连接失效，尝试重新登录...")
                if self._ensure_bs_login(force_reconnect=True):
                    # 重试查询
                    rs = bs.query_history_k_data_plus(
                        bs_code,
                        "date,open,high,low,close,volume,amount",
                        start_date=start_date,
                        end_date=end_date,
                        frequency="d",
                        adjustflag="2",
                    )
                    if rs.error_code != "0":
                        logger.warning("BaoStock 查询失败 %s (重试后): %s %s", symbol, rs.error_code, rs.error_msg)
                        return pd.DataFrame()
                else:
                    logger.warning("BaoStock 重新登录失败，无法查询 %s", symbol)
                    return pd.DataFrame()
            else:
                logger.warning("BaoStock 查询失败 %s: %s %s", symbol, rs.error_code, rs.error_msg)
                return pd.DataFrame()

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=[c.strip() for c in rs.fields])
        # 类型转换
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for c in ["open", "high", "low", "close", "volume", "amount"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        df = df.dropna(subset=["date"]).set_index("date").sort_index()
        df = df.rename(columns={"date": "dt"})
        df = df[["open", "high", "low", "close", "volume", "amount"]]
        return df

    def close(self):
        """
        关闭 BaoStock 连接（批量处理完成后调用，确保资源释放）
        建议在批量处理时使用 try/finally 确保调用
        """
        if self.bs_logged_in and bs is not None:
            try:
                bs.logout()
                self.bs_logged_in = False
                logger.info("BaoStock 连接已关闭")
            except Exception as e:
                logger.warning("关闭 BaoStock 连接时出错: %s", e)
    
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
        """尝试获取板块数据的内部函数，包含重试机制和异常捕获"""
        import time
        
        # 重试3次，每次间隔递增
        for attempt in range(3):
            try:
                self._rate_limit_check()
                # 这是获取行业成分股的正确接口
                result = ak.stock_board_industry_cons_em(symbol=sector_name)
                if result is not None and not result.empty:
                    return result
                else:
                    logger.debug(f"板块 '{sector_name}' 返回空数据（第{attempt+1}次）")
            except Exception as e:
                error_msg = str(e)
                # 如果是连接错误，等待更长时间
                if attempt < 2:
                    wait_time = (attempt + 1) * 3  # 3秒、6秒
                    logger.debug(f"获取板块 '{sector_name}' 失败（第{attempt+1}次）: {error_msg[:100]}，{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"获取板块 '{sector_name}' 失败（3次均失败）: {error_msg[:100]}")
        
        # 所有重试都失败，尝试备用接口（如果有）
        try:
            logger.debug(f"尝试备用接口获取板块 '{sector_name}'...")
            # 尝试使用另一个可能的接口（如果存在）
            # 注意：这里可以根据实际情况添加其他数据源的接口
            pass  # 暂时没有其他备用接口
        except Exception as e:
            logger.debug(f"备用接口也失败: {e}")
        
        # 所有尝试都失败，返回 None
        return None
    
    
    def get_stock_history(self, symbol: str, period: str = "6mo") -> pd.DataFrame:
        """
        获取个股历史数据（离线/稳健版）

        说明：
        - 完全移除 AkShare，对你当前网络环境更友好
        - 只使用 BaoStock 获取日线数据（前复权）
        """
        # 计算日期范围
        end_dt = datetime.now()
        if period == "6mo":
            start_dt = end_dt - timedelta(days=180)
        elif period == "3mo":
            start_dt = end_dt - timedelta(days=90)
        elif period == "1mo":
            start_dt = end_dt - timedelta(days=30)
        else:
            start_dt = end_dt - timedelta(days=180)

        # 直接使用 BaoStock（日线，前复权）
        try:
            bs_df = self._fetch_history_baostock(
                symbol,
                start_date=start_dt.strftime("%Y-%m-%d"),
                end_date=end_dt.strftime("%Y-%m-%d"),
            )
            if bs_df is not None and not bs_df.empty and "close" in bs_df.columns and not bs_df["close"].isna().all():
                logger.info("使用 BaoStock 获取 %s 成功（无 AkShare）", symbol)
                return bs_df.sort_index().ffill().bfill()
        except Exception as e:
            logger.warning("BaoStock 获取 %s 失败: %s", symbol, e)

        logger.error("获取股票 %s 历史数据失败（仅 BaoStock，未使用 AkShare）", symbol)
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