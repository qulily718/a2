"""
优化版动态板块分析器 - 基于AKShare实际支持的板块
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class OptimizedDynamicSectorAnalyzer:
    """优化版动态板块分析器"""
    
    def __init__(self, data_fetcher, config: Dict = None):
        self.data_fetcher = data_fetcher
        self.config = config or self._default_config()
        self.sector_cache = {}  # 缓存板块数据
        
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            'min_stock_count': 8,
            'max_sectors_to_analyze': 40,
            'top_sectors_to_select': 5,
            'min_sector_score': 50,
            
            # 排除的板块类型（基于名称关键词）
            'exclude_keywords': [
                'ST', '退市', '风险警示', '北证', '*ST',
                '已退市', '科创板', '创业板', '风险'
            ],
            
            # 重点关注板块（即使得分不高也关注）
            'focus_keywords': [
                '半导体', '芯片', '人工智能', 'AI',
                '新能源', '光伏', '电池', '电力',
                '有色金属', '煤炭', '化学', '医药'
            ],
            
            # 评分权重
            'score_weights': {
                'momentum': 0.35,      # 动量（涨跌幅）
                'breadth': 0.25,       # 广度（上涨家数比例）
                'attention': 0.20,     # 关注度（换手率）
                'stability': 0.20      # 稳定性
            }
        }
    
    def get_real_time_sector_data(self) -> pd.DataFrame:
        """
        获取实时板块数据（直接从AKShare获取带实时指标的数据）
        这是关键函数，直接使用显示的86个板块数据
        """
        logger.info("获取实时板块数据...")
        
        try:
            # 使用AKShare获取板块实时数据
            sector_df = ak.stock_board_industry_name_em()
            
            if sector_df is None or sector_df.empty:
                logger.error("无法获取板块实时数据")
                return pd.DataFrame()
            
            # 显示获取到的列名（调试用）
            logger.debug(f"板块数据列名: {list(sector_df.columns)}")
            logger.debug(f"获取到 {len(sector_df)} 个板块")
            
            # 标准化列名（确保一致性）
            column_mapping = {}
            for col in sector_df.columns:
                col_str = str(col)
                if '板块名称' in col_str or '名称' in col_str:
                    column_mapping['sector_name'] = col
                elif '板块代码' in col_str or '代码' in col_str:
                    column_mapping['sector_code'] = col
                elif '最新价' in col_str:
                    column_mapping['price'] = col
                elif '涨跌幅' in col_str or '涨跌额' in col_str:
                    column_mapping['change_pct'] = col
                elif '上涨家数' in col_str:
                    column_mapping['up_count'] = col
                elif '下跌家数' in col_str:
                    column_mapping['down_count'] = col
                elif '总市值' in col_str:
                    column_mapping['total_market_cap'] = col
                elif '换手率' in col_str:
                    column_mapping['turnover_rate'] = col
                elif '领涨股票-涨跌幅' in col_str:
                    column_mapping['leader_change_pct'] = col
            
            # 创建标准化的DataFrame
            processed_data = pd.DataFrame()
            
            # 复制必要字段
            for new_col, old_col in column_mapping.items():
                if old_col in sector_df.columns:
                    processed_data[new_col] = sector_df[old_col]
            
            # 确保有板块名称和代码
            if 'sector_name' not in processed_data.columns and len(sector_df.columns) > 1:
                processed_data['sector_name'] = sector_df.iloc[:, 1]
            
            if 'sector_code' not in processed_data.columns:
                processed_data['sector_code'] = processed_data['sector_name']
            
            # 数据清洗和类型转换
            numeric_columns = ['price', 'change_pct', 'up_count', 'down_count', 
                              'total_market_cap', 'turnover_rate', 'leader_change_pct']
            
            for col in numeric_columns:
                if col in processed_data.columns:
                    processed_data[col] = pd.to_numeric(processed_data[col], errors='coerce')
            
            # 计算额外指标
            if 'up_count' in processed_data.columns and 'down_count' in processed_data.columns:
                processed_data['total_count'] = processed_data['up_count'] + processed_data['down_count']
                processed_data['up_ratio'] = (processed_data['up_count'] / processed_data['total_count'] * 100).round(1)
            
            # 风险评估
            processed_data['risk_level'] = processed_data['sector_name'].apply(self._assess_risk_level)
            
            # 板块类型分类
            processed_data['sector_category'] = processed_data['sector_name'].apply(self._categorize_sector)
            
            logger.info(f"成功获取 {len(processed_data)} 个板块的实时数据")
            return processed_data
            
        except Exception as e:
            logger.error(f"获取实时板块数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return pd.DataFrame()
    
    def _assess_risk_level(self, sector_name: str) -> str:
        """评估板块风险等级"""
        sector_name_lower = str(sector_name).lower()
        
        # 低风险板块
        low_risk_keywords = ['银行', '煤炭', '电力', '公用事业', '食品', '饮料', '保险', '证券']
        for keyword in low_risk_keywords:
            if keyword in sector_name_lower:
                return 'low'
        
        # 高风险板块
        high_risk_keywords = ['半导体', '软件', '互联网', '科技', '芯片', '人工智能', 'AI', '生物', '游戏', '传媒']
        for keyword in high_risk_keywords:
            if keyword in sector_name_lower:
                return 'high'
        
        # 中等风险板块
        medium_risk_keywords = ['医药', '医疗', '化工', '机械', '汽车', '有色', '金属', '制造', '材料']
        for keyword in medium_risk_keywords:
            if keyword in sector_name_lower:
                return 'medium'
        
        return 'medium'  # 默认中等风险
    
    def _categorize_sector(self, sector_name: str) -> str:
        """分类板块"""
        sector_name_lower = str(sector_name).lower()
        
        # 科技成长类
        tech_keywords = ['半导体', '软件', '计算机', '互联网', '科技', '芯片', '人工智能', 'AI', '游戏', '通信']
        for keyword in tech_keywords:
            if keyword in sector_name_lower:
                return 'technology'
        
        # 消费类
        consumer_keywords = ['食品', '饮料', '酿酒', '家电', '汽车', '旅游', '酒店', '商贸', '零售']
        for keyword in consumer_keywords:
            if keyword in sector_name_lower:
                return 'consumer'
        
        # 周期类
        cyclical_keywords = ['有色', '金属', '煤炭', '化工', '石油', '钢铁', '建材', '水泥', '玻璃']
        for keyword in cyclical_keywords:
            if keyword in sector_name_lower:
                return 'cyclical'
        
        # 金融地产类
        finance_keywords = ['银行', '保险', '证券', '房地产', '多元金融']
        for keyword in finance_keywords:
            if keyword in sector_name_lower:
                return 'finance'
        
        # 医药医疗类
        medical_keywords = ['医药', '医疗', '生物', '中药', '制药', '器械', '健康']
        for keyword in medical_keywords:
            if keyword in sector_name_lower:
                return 'medical'
        
        return 'other'
    
    def calculate_sector_scores(self, sector_data: pd.DataFrame) -> pd.DataFrame:
        """
        计算板块综合得分
        """
        if sector_data.empty:
            return pd.DataFrame()
        
        df = sector_data.copy()
        
        # 1. 动量得分（基于涨跌幅）
        if 'change_pct' in df.columns:
            # 归一化涨跌幅到0-100分
            change_pct = df['change_pct'].fillna(0)
            momentum_score = 50 + change_pct * 10  # 每1%涨跌对应10分变化
            df['momentum_score'] = np.clip(momentum_score, 0, 100)
        else:
            df['momentum_score'] = 50
        
        # 2. 广度得分（基于上涨家数比例）
        if 'up_ratio' in df.columns:
            up_ratio = df['up_ratio'].fillna(50)
            breadth_score = up_ratio  # 直接使用上涨比例作为得分（0-100）
            df['breadth_score'] = np.clip(breadth_score, 0, 100)
        else:
            df['breadth_score'] = 50
        
        # 3. 关注度得分（基于换手率）
        if 'turnover_rate' in df.columns:
            turnover = df['turnover_rate'].fillna(2.0)
            # 换手率在1-10%之间比较合理
            attention_score = 50
            attention_score += (turnover - 2.0) * 10  # 2%为基准，每±1%对应10分
            df['attention_score'] = np.clip(attention_score, 0, 100)
        else:
            df['attention_score'] = 50
        
        # 4. 稳定性得分（基于市值和领涨股）
        stability_score = 50
        
        if 'total_market_cap' in df.columns:
            # 市值越大越稳定
            market_cap = df['total_market_cap'].fillna(1000)
            market_cap_score = (np.log10(market_cap) - 2) * 10  # 100亿市值得50分
            stability_score += market_cap_score.clip(-20, 20)
        
        if 'leader_change_pct' in df.columns:
            # 领涨股涨幅适中得分高，过大或过小得分低
            leader_change = df['leader_change_pct'].fillna(0).abs()
            leader_score = 50
            leader_score -= (leader_change - 5) * 2  # 5%涨幅最理想
            stability_score += (leader_score - 50) * 0.5
        
        df['stability_score'] = np.clip(stability_score, 0, 100)
        
        # 5. 计算综合得分
        weights = self.config['score_weights']
        df['total_score'] = (
            df['momentum_score'] * weights['momentum'] +
            df['breadth_score'] * weights['breadth'] +
            df['attention_score'] * weights['attention'] +
            df['stability_score'] * weights['stability']
        )
        
        # 根据风险等级调整
        risk_adjustment = {
            'low': 1.05,   # 低风险加分
            'medium': 1.00,
            'high': 0.95    # 高风险减分
        }
        df['risk_adjustment'] = df['risk_level'].map(risk_adjustment).fillna(1.0)
        df['total_score'] = df['total_score'] * df['risk_adjustment']
        df['total_score'] = df['total_score'].round(1)
        
        return df
    
    def filter_and_rank_sectors(self, sector_data: pd.DataFrame) -> pd.DataFrame:
        """
        过滤和排序板块
        """
        if sector_data.empty:
            return pd.DataFrame()
        
        df = sector_data.copy()
        
        # 1. 排除不需要的板块
        exclude_keywords = self.config['exclude_keywords']
        exclusion_mask = df['sector_name'].apply(
            lambda x: not any(keyword in str(x) for keyword in exclude_keywords)
        )
        df = df[exclusion_mask]
        
        # 2. 过滤掉股票数量太少的板块（如果数据中有）
        if 'total_count' in df.columns:
            df = df[df['total_count'] >= self.config['min_stock_count']]
        
        # 3. 计算得分（如果还没计算）
        if 'total_score' not in df.columns:
            df = self.calculate_sector_scores(df)
        
        # 4. 排序
        df = df.sort_values('total_score', ascending=False)
        
        # 5. 限制数量
        max_sectors = min(self.config['max_sectors_to_analyze'], len(df))
        df = df.head(max_sectors)
        
        return df
    
    def get_top_sectors(self, sector_data: pd.DataFrame = None, top_n: int = None) -> List[Dict]:
        """
        获取最强板块
        """
        if sector_data is None:
            sector_data = self.get_real_time_sector_data()
        
        if sector_data.empty:
            logger.warning("没有板块数据")
            return []
        
        # 过滤和排序
        ranked_sectors = self.filter_and_rank_sectors(sector_data)
        
        if ranked_sectors.empty:
            logger.warning("过滤后没有符合条件的板块")
            return []
        
        top_n = top_n or self.config['top_sectors_to_select']
        min_score = self.config['min_sector_score']
        
        # 选择得分最高的板块
        top_sectors = ranked_sectors[ranked_sectors['total_score'] >= min_score].head(top_n)
        
        if top_sectors.empty:
            # 如果没有达到最低分，返回前3个
            top_sectors = ranked_sectors.head(3)
            logger.warning(f"没有板块达到最低得分{min_score}，返回前3个")
        
        recommendations = []
        for _, row in top_sectors.iterrows():
            score = row['total_score']
            strength, recommendation = self._get_strength_recommendation(score)
            
            rec = {
                'sector_name': row['sector_name'],
                'sector_code': row.get('sector_code', row['sector_name']),
                'score': score,
                'strength': strength,
                'recommendation': recommendation,
                'risk_level': row['risk_level'],
                'sector_category': row.get('sector_category', 'unknown'),
                'change_pct': row.get('change_pct', 0),
                'up_ratio': row.get('up_ratio', 50),
                'reason': self._generate_recommendation_reason(row)
            }
            
            # 添加额外信息
            if 'total_count' in row:
                rec['stock_count'] = row['total_count']
            if 'turnover_rate' in row:
                rec['turnover_rate'] = row['turnover_rate']
            
            recommendations.append(rec)
        
        logger.info(f"推荐 {len(recommendations)} 个最强板块")
        return recommendations
    
    def _get_strength_recommendation(self, score: float) -> Tuple[str, str]:
        """根据得分获取强度等级和推荐建议"""
        if score >= 75:
            return "强势", "重点关注"
        elif score >= 65:
            return "偏强", "积极关注"
        elif score >= 55:
            return "中性", "适度关注"
        elif score >= 45:
            return "偏弱", "谨慎关注"
        else:
            return "弱势", "观望"
    
    def _generate_recommendation_reason(self, row: pd.Series) -> str:
        """生成推荐理由"""
        reasons = []
        
        if 'change_pct' in row and not pd.isna(row['change_pct']):
            change = row['change_pct']
            if change > 0:
                reasons.append(f"板块上涨{change:.2f}%")
            else:
                reasons.append(f"板块下跌{abs(change):.2f}%")
        
        if 'up_ratio' in row and not pd.isna(row['up_ratio']):
            up_ratio = row['up_ratio']
            if up_ratio > 60:
                reasons.append(f"{up_ratio:.1f}%股票上涨")
            elif up_ratio < 40:
                reasons.append(f"{up_ratio:.1f}%股票上涨（偏弱）")
        
        if 'turnover_rate' in row and not pd.isna(row['turnover_rate']):
            turnover = row['turnover_rate']
            if turnover > 3:
                reasons.append(f"换手率{turnover:.1f}%（活跃）")
        
        if not reasons:
            reasons.append("综合评分较高")
        
        return "，".join(reasons)
    
    def generate_sector_report(self, sector_data: pd.DataFrame = None, 
                              top_sectors: List[Dict] = None) -> str:
        """生成板块分析报告"""
        if sector_data is None:
            sector_data = self.get_real_time_sector_data()
        
        if sector_data.empty:
            return "板块分析报告：无数据"
        
        # 过滤和排序
        ranked_sectors = self.filter_and_rank_sectors(sector_data)
        
        if top_sectors is None:
            top_sectors = self.get_top_sectors(ranked_sectors)
        
        report_lines = []
        report_lines.append("=" * 100)
        report_lines.append("📊 动态板块分析报告（实时版）")
        report_lines.append("=" * 100)
        report_lines.append(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"分析板块总数: {len(sector_data)}")
        report_lines.append(f"推荐板块数量: {len(top_sectors)}")
        report_lines.append("")
        
        # 市场整体概况
        if 'change_pct' in ranked_sectors.columns:
            avg_change = ranked_sectors['change_pct'].mean()
            up_sector_ratio = (ranked_sectors['change_pct'] > 0).sum() / len(ranked_sectors) * 100
            report_lines.append("📈 市场整体概况:")
            report_lines.append(f"  板块平均涨跌幅: {avg_change:.2f}%")
            report_lines.append(f"  上涨板块比例: {up_sector_ratio:.1f}%")
            
            # 涨幅前三
            top_gainers = ranked_sectors.nlargest(3, 'change_pct')[['sector_name', 'change_pct']]
            report_lines.append(f"  涨幅前三板块:")
            for _, row in top_gainers.iterrows():
                report_lines.append(f"    • {row['sector_name']}: {row['change_pct']:.2f}%")
        
        # 板块类别分布
        if 'sector_category' in ranked_sectors.columns:
            category_counts = ranked_sectors['sector_category'].value_counts()
            report_lines.append(f"\n🏷️  板块类别分布:")
            for category, count in category_counts.items():
                percentage = count / len(ranked_sectors) * 100
                report_lines.append(f"  {category}: {count}个 ({percentage:.1f}%)")
        
        # 推荐板块详情
        report_lines.append("\n🎯 推荐关注板块（按强度排序）：")
        for i, sector in enumerate(top_sectors, 1):
            report_lines.append(f"\n{i}. {sector['sector_name']}")
            report_lines.append(f"   强度: {sector['strength']} | 综合得分: {sector['score']}")
            report_lines.append(f"   风险等级: {sector['risk_level']} | 类别: {sector['sector_category']}")
            report_lines.append(f"   推荐: {sector['recommendation']}")
            report_lines.append(f"   理由: {sector['reason']}")
            
            # 显示详细数据
            details = []
            if 'change_pct' in sector and sector['change_pct'] != 0:
                details.append(f"涨跌: {sector['change_pct']:.2f}%")
            if 'up_ratio' in sector:
                details.append(f"上涨比例: {sector['up_ratio']:.1f}%")
            if 'stock_count' in sector:
                details.append(f"股票数: {sector['stock_count']}")
            
            if details:
                report_lines.append(f"   数据: {' | '.join(details)}")
        
        # 风险提示
        report_lines.append("\n⚠️  风险提示:")
        high_risk_count = len([s for s in top_sectors if s['risk_level'] == 'high'])
        if high_risk_count > 2:
            report_lines.append(f"  注意：{high_risk_count}个高风险板块，建议控制仓位")
        
        # 操作建议
        report_lines.append("\n💡 操作建议:")
        if len(top_sectors) >= 3:
            report_lines.append("  1. 分散投资到2-3个不同类别的板块")
            report_lines.append("  2. 优先选择风险收益比较高的个股")
            report_lines.append("  3. 设置好止损位，控制单笔亏损")
        else:
            report_lines.append("  市场机会有限，建议轻仓或观望")
        
        report_lines.append("=" * 100)
        
        return "\n".join(report_lines)