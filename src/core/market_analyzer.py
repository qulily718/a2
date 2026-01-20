# src/core/market_analyzer.py
"""
市场环境分析器 - 确定当前市场主线方向
"""
import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import logging
import warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)

class MarketAnalyzer:
    """市场环境分析器"""
    
    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher
        self.sectors = []  # 将从配置文件加载
        
    def load_sectors_from_config(self, config_path: str = None) -> List[Dict]:
        """
        直接从 config/sectors.yaml 文件加载板块配置。
        这是最可靠的方式，前提是配置文件格式正确。
        """
        import yaml
        import os
        
        if config_path is None:
            # 假设配置文件在项目根目录的 config 文件夹下
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            config_path = os.path.join(project_root, 'config', 'sectors.yaml')
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # 从配置中提取 focus_sectors 列表
            sectors_list = config_data.get('focus_sectors', [])
            
            # 确保每个板块字典都有我们需要的字段，并统一键名
            formatted_sectors = []
            for sector in sectors_list:
                # 这里将配置中的字段映射到我们代码内部期望的字段名
                formatted_sector = {
                    'name': sector.get('name', ''),
                    'code': sector.get('code', ''),  # 这是关键，从配置的‘code’字段读取
                    'weight': sector.get('weight', 0.1),
                    'risk_level': sector.get('risk_level', 'medium')
                }
                # 可选：验证code是否有效
                if not formatted_sector['code']:
                    logger.warning(f"板块 {formatted_sector['name']} 的 code 字段为空，将被跳过。")
                    continue
                formatted_sectors.append(formatted_sector)
            
            logger.info(f"从 {config_path} 成功加载 {len(formatted_sectors)} 个板块配置。")
            self.sectors = formatted_sectors
            return self.sectors
            
        except FileNotFoundError:
            logger.error(f"配置文件未找到: {config_path}，请检查路径。")
            return []
        except yaml.YAMLError as e:
            logger.error(f"YAML配置文件解析失败: {e}")
            return []
        except Exception as e:
            logger.error(f"加载配置文件时发生未知错误: {e}")
            return []
    
    def analyze_sector_strength(self, sector_list: List[Dict] = None) -> pd.DataFrame:
        """
        分析板块强度
        返回按强度排序的板块DataFrame
        """
        if sector_list is None:
            sector_list = self.sectors if self.sectors else self.load_sectors_from_config()
        
        results = []
        
        for sector in sector_list:
            sector_name = sector['name']
            sector_code = sector['code']
            
            try:
                logger.info(f"分析板块: {sector_name}")
                
                # 1. 获取板块成分股
                stocks = self.data_fetcher.get_sector_stocks(sector_code)
                if len(stocks) < 5:  # 成分股太少
                    logger.warning(f"板块 {sector_name} 成分股太少: {len(stocks)}")
                    continue
                
                # 2. 计算板块平均表现
                if 'change_pct' in stocks.columns:
                    avg_change = stocks['change_pct'].mean()
                    up_ratio = (stocks['change_pct'] > 0).sum() / len(stocks)
                else:
                    avg_change = 0
                    up_ratio = 0
                
                # 3. 计算板块动量得分
                momentum_score = self._calculate_momentum_score(stocks)
                
                # 4. 计算资金关注度
                volume_score = self._calculate_volume_score(stocks)
                
                # 5. 计算龙头股表现
                leader_score = self._calculate_leader_score(stocks)
                
                # 综合得分
                total_score = (
                    momentum_score * 0.4 +
                    volume_score * 0.3 +
                    leader_score * 0.2 +
                    min(avg_change * 5, 100) * 0.1  # 归一化涨跌幅
                )
                
                # 确定趋势方向
                trend = self._determine_trend(avg_change, up_ratio, momentum_score)
                
                results.append({
                    'sector_name': sector_name,
                    'sector_code': sector_code,
                    'stock_count': len(stocks),
                    'avg_change': round(avg_change, 2),
                    'up_ratio': round(up_ratio * 100, 1),
                    'momentum_score': round(momentum_score, 1),
                    'volume_score': round(volume_score, 1),
                    'leader_score': round(leader_score, 1),
                    'total_score': round(total_score, 1),
                    'trend': trend,
                    'weight': sector.get('weight', 0.1),
                    'risk_level': sector.get('risk_level', 'medium')
                })
                
                logger.info(f"板块 {sector_name} 分析完成: 得分 {total_score:.1f}, 趋势 {trend}")
                
            except Exception as e:
                logger.error(f"分析板块 {sector_name} 失败: {e}")
                continue
        
        # 转换为DataFrame并排序
        if results:
            df = pd.DataFrame(results)
            df = df.sort_values('total_score', ascending=False)
            df.reset_index(drop=True, inplace=True)
            return df
        else:
            logger.warning("没有板块分析结果")
            return pd.DataFrame()
    
    def _calculate_momentum_score(self, stocks_df: pd.DataFrame) -> float:
        """计算动量得分"""
        if 'change_pct' not in stocks_df.columns:
            return 50  # 默认中间值
        
        changes = stocks_df['change_pct'].dropna()
        if len(changes) < 3:
            return 50
        
        # 上涨股票比例
        up_ratio = (changes > 0).sum() / len(changes)
        
        # 平均涨幅
        avg_up = changes[changes > 0].mean() if (changes > 0).any() else 0
        
        # 动量强度（基于涨幅分布）
        if len(changes) >= 5:
            top_performers = changes.nlargest(min(5, len(changes)))
            avg_top = top_performers.mean()
        else:
            avg_top = avg_up
        
        # 动量得分（0-100）
        momentum_score = min(100, up_ratio * 60 + min(avg_up, 10) * 2 + min(avg_top, 20) * 1)
        return momentum_score
    
    def _calculate_volume_score(self, stocks_df: pd.DataFrame) -> float:
        """计算成交量得分（简化版）"""
        # 这里简化处理，实际应用中可能需要获取历史成交量数据
        if 'change_pct' not in stocks_df.columns:
            return 50
        
        # 假设涨幅大的股票通常成交量也活跃
        changes = stocks_df['change_pct'].dropna()
        if len(changes) < 3:
            return 50
        
        # 基于涨幅的活跃度估计
        positive_changes = changes[changes > 0]
        if len(positive_changes) > 0:
            avg_positive = positive_changes.mean()
            score = min(100, 50 + avg_positive * 3)
        else:
            score = 40
        
        return score
    
    def _calculate_leader_score(self, stocks_df: pd.DataFrame) -> float:
        """计算龙头股表现得分"""
        if len(stocks_df) < 3:
            return 50
        
        # 选择市值或价格较高的作为龙头（简化处理）
        if 'price' in stocks_df.columns:
            # 按价格排序，价格高的可能是龙头
            sorted_stocks = stocks_df.sort_values('price', ascending=False)
            top_stocks = sorted_stocks.head(min(3, len(sorted_stocks)))
            
            if 'change_pct' in top_stocks.columns:
                avg_leader_change = top_stocks['change_pct'].mean()
                # 龙头股得分：50分基础，根据表现加减
                score = 50 + avg_leader_change * 2
                return max(0, min(100, score))
        
        return 50
    
    def _determine_trend(self, avg_change: float, up_ratio: float, momentum_score: float) -> str:
        """确定趋势方向"""
        if momentum_score >= 70 and up_ratio >= 60:
            return "强势上涨"
        elif momentum_score >= 60 and up_ratio >= 50:
            return "温和上涨"
        elif momentum_score >= 40 and up_ratio >= 40:
            return "震荡整理"
        elif momentum_score >= 30:
            return "弱势整理"
        else:
            return "趋势向下"
    
    def get_recommended_sectors(self, sector_strength_df: pd.DataFrame, 
                           max_sectors: int = 3) -> List[Dict]:
        """
        获取推荐关注的板块
        """
        if sector_strength_df.empty:
            return []
        
        # 按综合得分排序
        sector_strength_df = sector_strength_df.sort_values('total_score', ascending=False)
        
        # 选择前N个板块
        selected = sector_strength_df.head(max_sectors)
        
        recommendations = []
        for _, row in selected.iterrows():
            # 根据得分确定推荐强度
            score = row['total_score']
            if score >= 70:
                strength = "强势"
                recommendation = "重点关注"
            elif score >= 50:
                strength = "中性"
                recommendation = "适度关注"
            else:
                strength = "弱势"
                recommendation = "谨慎关注"
            
            recommendations.append({
                'sector_name': row['sector_name'],
                'sector_code': row['sector_code'],
                'score': score,
                'strength': strength,  # 添加这个字段
                'trend': row.get('trend_status', '未知'),
                'recommendation': recommendation,
                'weight': row.get('weight', 0.1),
                'risk_level': row.get('risk_level', 'medium'),
                'reason': f"综合得分{score:.1f}，趋势{row.get('trend_status', '未知')}"
            })
        
        return recommendations
    
    def _generate_recommendation(self, score: float, trend: str) -> str:
        """生成推荐建议"""
        if score >= 70:
            return "重点关注，积极配置"
        elif score >= 60:
            return "适度关注，分批布局"
        elif score >= 50:
            return "观察等待，谨慎参与"
        elif score >= 40:
            return "暂时回避，等待信号"
        else:
            return "风险较高，建议规避"
    
    def analyze_top_stocks_in_sector(self, sector_code: str, top_n: int = 10) -> pd.DataFrame:
        """
        分析板块内表现最好的股票
        """
        try:
            # 获取板块成分股
            stocks = self.data_fetcher.get_sector_stocks(sector_code)
            if stocks.empty:
                return pd.DataFrame()
            
            # 按涨跌幅排序
            if 'change_pct' in stocks.columns:
                sorted_stocks = stocks.sort_values('change_pct', ascending=False)
                top_stocks = sorted_stocks.head(top_n)
                
                # 添加分析指标
                result = pd.DataFrame()
                result['symbol'] = top_stocks['symbol']
                result['name'] = top_stocks['name']
                result['price'] = top_stocks['price']
                result['change_pct'] = top_stocks['change_pct']
                
                # 计算相对强度
                if len(stocks) > 1:
                    mean_change = stocks['change_pct'].mean()
                    std_change = stocks['change_pct'].std()
                    result['rel_strength'] = (result['change_pct'] - mean_change) / std_change if std_change > 0 else 0
                
                return result
            else:
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"分析板块 {sector_code} 内股票失败: {e}")
            return pd.DataFrame()

def test_market_analyzer():
    """测试市场分析器"""
    print("=" * 60)
    print("测试市场分析器模块")
    print("=" * 60)
    
    # 添加项目根目录到路径（支持直接运行此文件）
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # 初始化日志
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 导入数据获取器
    from src.data.data_fetcher import ShortTermDataFetcher
    
    # 创建数据获取器实例
    fetcher = ShortTermDataFetcher(use_cache=False)
    
    # 创建市场分析器
    analyzer = MarketAnalyzer(fetcher)
    
    # 加载板块配置
    sectors = analyzer.load_sectors_from_config()
    print(f"\n加载了 {len(sectors)} 个板块配置:")
    for sector in sectors:
        print(f"  - {sector['name']} (权重: {sector['weight']}, 风险: {sector['risk_level']})")
    
    # 分析板块强度
    print("\n" + "-" * 60)
    print("开始分析板块强度...")
    sector_strength = analyzer.analyze_sector_strength(sectors)
    
    if not sector_strength.empty:
        print("\n板块强度分析结果:")
        print(sector_strength[['sector_name', 'total_score', 'trend', 'avg_change', 'up_ratio', 'stock_count']])
        
        # 获取推荐板块
        recommendations = analyzer.get_recommended_sectors(sector_strength, max_sectors=3)
        
        print("\n" + "-" * 60)
        print("推荐关注板块:")
        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec['sector_name']}")
            print(f"   综合得分: {rec['total_score']}")
            print(f"   当前趋势: {rec['trend']}")
            print(f"   建议操作: {rec['recommendation']}")
            print(f"   策略权重: {rec['weight']}")
            print(f"   风险等级: {rec['risk_level']}")
            
            # 分析该板块内的强势股票
            print(f"\n   板块内强势股票:")
            top_stocks = analyzer.analyze_top_stocks_in_sector(rec['sector_code'], top_n=5)
            if not top_stocks.empty:
                for j, (_, stock) in enumerate(top_stocks.iterrows(), 1):
                    print(f"      {j}. {stock['name']} ({stock['symbol']})")
                    print(f"          价格: {stock['price']}, 涨跌幅: {stock['change_pct']:.2f}%")
    else:
        print("板块分析失败")
    
    print("\n" + "=" * 60)
    print("市场分析器测试完成")
    print("=" * 60)
    return analyzer

if __name__ == "__main__":
    test_market_analyzer()