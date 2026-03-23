"""
短线稳健策略执行系统 - 离线版（不依赖板块接口）
支持多种输入方式：已有结果文件、手动输入、配置文件
"""
import yaml
import logging
import pandas as pd
import os
import glob
from datetime import datetime, time
from typing import List, Dict, Optional
from src.data.data_fetcher import ShortTermDataFetcher
from src.core.stock_filter import StockFilter
from analyze_anytime import update_realtime_data

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """加载配置文件"""
    try:
        with open('config/sectors.yaml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning("配置文件不存在，使用默认配置")
        return {'scan_params': {}}


def load_stocks_from_results(results_dir: str = "results") -> List[Dict]:
    """从已有结果文件加载股票列表"""
    if not os.path.exists(results_dir):
        return []
    
    patterns = [
        "simple_recommendations_*.csv",
        "recommendations_*.csv",
        "recommended_stocks_*.csv",
        "stocks_simple_*.csv"
    ]
    
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(results_dir, pattern)))
    
    if not files:
        return []
    
    # 使用最新的文件
    latest_file = max(files, key=os.path.getctime)
    logger.info(f"从结果文件加载: {os.path.basename(latest_file)}")
    
    try:
        df = pd.read_csv(latest_file, encoding='utf-8-sig')
        stocks = []
        for _, row in df.iterrows():
            symbol = str(row.get('symbol', '')).strip()
            if symbol:
                stocks.append({
                    'symbol': symbol,
                    'name': str(row.get('name', '')).strip() or symbol,
                    'sector_name': str(row.get('sector_name', row.get('sector', ''))).strip(),
                    'price': float(row.get('price', 0)) if pd.notna(row.get('price')) else 0,
                    'change_pct': float(row.get('change_pct', 0)) if pd.notna(row.get('change_pct')) else 0,
                })
        return stocks
    except Exception as e:
        logger.error(f"加载结果文件失败: {e}")
        return []


def load_stocks_from_config(config_path: str = "config/manual_watchlist.yaml") -> List[Dict]:
    """从配置文件加载股票列表"""
    if not os.path.exists(config_path):
        return []
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        watchlist = config.get('watchlist', [])
        stocks = []
        for item in watchlist:
            symbol = str(item.get('symbol', '')).strip()
            if symbol:
                stocks.append({
                    'symbol': symbol,
                    'name': str(item.get('name', '')).strip() or symbol,
                    'sector_name': str(item.get('sector_name', '')).strip(),
                })
        return stocks
    except Exception as e:
        logger.error(f"加载配置文件失败: {e}")
        return []


def get_stocks_from_input() -> List[Dict]:
    """手动输入股票代码"""
    print("\n📝 手动输入股票代码（每行一个，格式：600000 或 600000.SS，输入空行结束）")
    print("   示例：")
    print("   601899")
    print("   300034.SZ")
    print("   002978")
    print("   （输入空行结束）")
    
    stocks = []
    while True:
        try:
            line = input("股票代码: ").strip()
            if not line:
                break
            
            # 处理代码格式
            code = line.replace('.SS', '').replace('.SZ', '')
            if code.isdigit() and len(code) == 6:
                # 自动判断市场
                if code.startswith('6') or code.startswith('9'):
                    symbol = f"{code}.SS"
                else:
                    symbol = f"{code}.SZ"
                
                stocks.append({
                    'symbol': symbol,
                    'name': code,  # 名称稍后从数据获取
                })
                print(f"  ✅ 已添加: {symbol}")
            else:
                print(f"  ⚠️  无效代码格式: {line}，请输入6位数字")
        except (EOFError, KeyboardInterrupt):
            break
    
    return stocks


def analyze_custom_stocks(stock_filter: StockFilter, stocks: List[Dict], strict_mode: bool = True) -> List[Dict]:
    """分析自定义股票列表"""
    print(f"\n🔍 开始分析 {len(stocks)} 只股票...")
    print("=" * 80)
    
    filtered_stocks = []
    
    for idx, stock in enumerate(stocks, 1):
        symbol = stock.get('symbol', '')
        name = stock.get('name', symbol)
        
        if not symbol:
            continue
        
        # 显示进度
        if idx % 5 == 0 or idx == len(stocks):
            print(f"  分析进度: {idx}/{len(stocks)} ({name})")
        
        try:
            # 获取历史数据
            hist_data = stock_filter.data_fetcher.get_stock_history(symbol, period="3mo")
            if hist_data.empty or len(hist_data) < stock_filter.config.get('min_trading_days', 60):
                logger.debug(f"{symbol} 历史数据不足，跳过")
                continue
            
            # 可选：获取市值仅用于展示（不再作为筛选条件）
            market_cap = stock_filter._get_stock_market_cap(symbol, pd.Series(stock))
            
            # 详细技术分析
            stock_data = pd.Series(stock)
            analysis_result = stock_filter._analyze_stock_technicals(hist_data, stock_data)
            
            # 计算综合评分
            total_score, breakdown = stock_filter._calculate_total_score(analysis_result)
            
            # 检查是否通过筛选
            if stock_filter._pass_screening(analysis_result, strict_mode):
                stock_info = {
                    'symbol': symbol,
                    'name': name,
                    'price': stock.get('price', 0),
                    'change_pct': stock.get('change_pct', 0),
                    'sector': stock.get('sector_name', ''),
                    'total_score': round(total_score, 1),
                    'rank_reasons': stock_filter._generate_rank_reasons(analysis_result),
                    'risk_level': stock_filter._assess_risk_level(analysis_result),
                    'entry_signal': stock_filter._generate_entry_signal(analysis_result),
                    'stop_loss': stock_filter._calculate_stop_loss(hist_data, stock_data),
                    'analysis_details': analysis_result,
                    'score_breakdown': breakdown
                }
                if market_cap is not None:
                    stock_info['market_cap'] = round(market_cap, 1)
                
                filtered_stocks.append(stock_info)
                print(f"  ✅ {name} ({symbol}) - 评分: {total_score:.1f}, 市值: {market_cap:.1f}亿" if market_cap else f"  ✅ {name} ({symbol}) - 评分: {total_score:.1f}")
        
        except Exception as e:
            logger.error(f"分析股票 {symbol} 失败: {e}")
            continue
    
    # 按评分排序
    filtered_stocks.sort(key=lambda x: x['total_score'], reverse=True)
    return filtered_stocks


def main():
    """主函数"""
    print("=" * 80)
    print("📈 短线稳健策略执行系统 - 离线版")
    print("=" * 80)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. 加载配置
    config = load_config()
    scan_params = config.get('scan_params', {})
    
    # 2. 初始化组件
    print("\n1. 初始化分析组件...")
    data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.3)
    stock_filter = StockFilter(data_fetcher, config=scan_params)
    
    # 3. 获取股票列表（多种方式）
    print("\n2. 获取股票列表...")
    stocks = []
    
    # 方式1：从已有结果文件加载
    stocks = load_stocks_from_results()
    if stocks:
        print(f"✅ 从结果文件加载了 {len(stocks)} 只股票")
    
    # 方式2：如果结果文件没有，尝试从配置文件加载
    if not stocks:
        stocks = load_stocks_from_config()
        if stocks:
            print(f"✅ 从配置文件加载了 {len(stocks)} 只股票")
    
    # 方式3：如果都没有，提示手动输入
    if not stocks:
        print("⚠️  未找到已有结果文件或配置文件")
        print("\n💡 请选择输入方式：")
        print("  1. 手动输入股票代码（推荐）")
        print("  2. 退出，先运行其他脚本生成结果文件")
        
        choice = input("\n请选择 (1/2): ").strip()
        if choice == '1':
            stocks = get_stocks_from_input()
            if not stocks:
                print("❌ 未输入任何股票代码")
                return
        else:
            print("👋 退出")
            return
    
    print(f"\n📊 准备分析 {len(stocks)} 只股票")
    print(f"   筛选条件：技术面评分")
    
    # 4. 分析股票
    try:
        filtered_stocks = analyze_custom_stocks(stock_filter, stocks, strict_mode=True)
        
        # 5. 如果是盘中时段，更新实时价格
        if filtered_stocks:
            current_time = datetime.now().time()
            is_trading_time = (time(9, 30) <= current_time <= time(11, 30)) or (time(13, 0) <= current_time <= time(15, 0))
            
            if is_trading_time:
                print("\n3. 更新实时价格...")
                try:
                    filtered_stocks = update_realtime_data(filtered_stocks, data_fetcher)
                    print(f"✅ 已更新 {len(filtered_stocks)} 只股票的实时数据")
                except Exception as e:
                    logger.warning(f"更新实时价格失败: {e}")
        
        # 6. 显示结果
        print("\n" + "=" * 80)
        print("📊 筛选结果")
        print("=" * 80)
        
        if filtered_stocks:
            print(f"\n✅ 找到 {len(filtered_stocks)} 只符合策略的股票：\n")
            
            for i, stock in enumerate(filtered_stocks, 1):
                price = stock.get('price', 0)
                change_pct = stock.get('change_pct', 0)
                market_cap = stock.get('market_cap', 0)
                
                price_str = f"{price:.2f}" if price and price > 0 else "N/A"
                change_str = f"{change_pct:.2f}%" if change_pct is not None and not pd.isna(change_pct) else "N/A"
                cap_str = f"{market_cap:.1f}亿" if market_cap else "N/A"
                
                print(f"{i:2d}. {stock['name']} ({stock['symbol']})")
                print(f"     评分: {stock['total_score']}/100 | 市值: {cap_str}")
                print(f"     价格: {price_str} | 涨跌: {change_str}")
                print(f"     信号: {stock['entry_signal']} | 止损: {stock['stop_loss']:.2f}")
                print(f"     理由: {', '.join(stock['rank_reasons'][:2])}")
                print()
            
            # 7. 保存结果
            df = pd.DataFrame(filtered_stocks)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 保存完整数据
            os.makedirs("results", exist_ok=True)
            df.to_csv(f"results/offline_recommendations_{timestamp}.csv", 
                     index=False, encoding='utf-8-sig')
            
            # 保存简化版
            simple_cols = ['symbol', 'name', 'market_cap', 'price', 'change_pct', 
                          'total_score', 'risk_level', 'entry_signal', 
                          'stop_loss', 'rank_reasons']
            
            if all(col in df.columns for col in simple_cols):
                df_simple = df[simple_cols]
                df_simple.to_csv(f"results/offline_simple_{timestamp}.csv", 
                               index=False, encoding='utf-8-sig')
            
            print(f"💾 结果已保存: results/offline_recommendations_{timestamp}.csv")
        else:
            print("\n⚠️  未找到符合策略的股票（技术面评分）")
            print("建议：")
            print("  1. 检查输入的股票代码是否正确")
            print("  2. 放宽筛选条件（修改 config/sectors.yaml 中的 scan_params）")
            print("  3. 或等待网络恢复后使用 main.py 获取更多候选股票")
    
    finally:
        data_fetcher.close()
    
    print("\n" + "=" * 80)
    print("✅ 分析完成！")
    print("=" * 80)


if __name__ == "__main__":
    main()
