"""
短线操作价格决策模块
"""
from typing import Dict, Tuple
import logging

logger = logging.getLogger(__name__)

class ShortTermTradingDecision:
    """短线交易决策器"""
    
    @staticmethod
    def get_buy_signal(stock_data: Dict, market_condition: str = "normal") -> Dict:
        """
        生成买入信号和价格建议
        
        Args:
            stock_data: 股票数据（包含价格、技术指标等）
            market_condition: 市场状况（normal/bull/bear/volatile）
            
        Returns:
            包含买入建议的字典
        """
        current_price = stock_data.get('price', 0)
        change_pct = stock_data.get('change_pct', 0)
        stop_loss = stock_data.get('stop_loss', 0)
        entry_signal = stock_data.get('entry_signal', '')
        
        # 基础买入建议
        buy_signal = {
            'suggested_action': '观望',
            'buy_price_range': (0, 0),
            'stop_loss_price': stop_loss,
            'position_size': 0,  # 仓位比例
            'holding_days': 0,
            'target_price': 0,
            'risk_reward_ratio': 0,
            'trading_notes': []
        }
        
        if current_price <= 0:
            return buy_signal
        
        # 根据市场状况调整策略
        strategy_params = {
            'normal': {'position': 0.05, 'days': 5, 'target_pct': 0.08},
            'bull': {'position': 0.07, 'days': 3, 'target_pct': 0.12},
            'bear': {'position': 0.03, 'days': 7, 'target_pct': 0.05},
            'volatile': {'position': 0.04, 'days': 4, 'target_pct': 0.06}
        }
        
        params = strategy_params.get(market_condition, strategy_params['normal'])
        
        # 根据技术信号判断
        technical_score = stock_data.get('total_score', 0)
        entry_strength = 0
        
        if isinstance(entry_signal, str):
            if '趋势向上' in entry_signal or '买入' in entry_signal:
                entry_strength += 1
            if '放量' in entry_signal or '启动' in entry_signal:
                entry_strength += 2
            if '动量' in entry_signal or '适中' in entry_signal:
                entry_strength += 1
        
        # 决策逻辑
        if technical_score >= 75 and entry_strength >= 2:
            # 强势信号
            buy_signal['suggested_action'] = '积极买入'
            
            # 价格区间（基于昨日收盘）
            base_price = current_price / (1 + change_pct/100)  # 还原昨日收盘价
            buy_range_low = base_price * 0.99   # -1%
            buy_range_high = base_price * 1.02  # +2%
            
            buy_signal['buy_price_range'] = (buy_range_low, buy_range_high)
            buy_signal['position_size'] = params['position']  # 5-7%仓位
            buy_signal['holding_days'] = max(1, params['days'] - 1)   # 因为已有1天涨幅
            
        elif technical_score >= 65 and entry_strength >= 1:
            # 中等信号
            buy_signal['suggested_action'] = '谨慎买入'
            
            base_price = current_price / (1 + change_pct/100)
            buy_range_low = base_price * 0.985   # -1.5%
            buy_range_high = base_price * 1.01   # +1%
            
            buy_signal['buy_price_range'] = (buy_range_low, buy_range_high)
            buy_signal['position_size'] = params['position'] * 0.7  # 减少仓位
            buy_signal['holding_days'] = params['days']
            
        else:
            buy_signal['suggested_action'] = '观望'
            return buy_signal
        
        # 计算目标价和风险收益比
        target_price = current_price * (1 + params['target_pct'])
        risk_amount = current_price - stop_loss
        reward_amount = target_price - current_price
        
        if risk_amount > 0:
            risk_reward_ratio = reward_amount / risk_amount
        else:
            risk_reward_ratio = 3  # 默认值
            
        buy_signal['target_price'] = round(target_price, 2)
        buy_signal['risk_reward_ratio'] = round(risk_reward_ratio, 2)
        
        # 添加交易备注
        notes = []
        
        if risk_reward_ratio >= 3:
            notes.append("风险收益比优秀(≥3:1)")
        elif risk_reward_ratio >= 2:
            notes.append("风险收益比良好(≥2:1)")
        else:
            notes.append("风险收益比较低，需谨慎")
            
        if change_pct > 5:
            notes.append("今日涨幅较大，避免追高")
        elif change_pct < 0:
            notes.append("今日调整，可能提供更好买点")
            
        buy_signal['trading_notes'] = notes
        
        return buy_signal
    
    @staticmethod
    def generate_trading_plan(stock_data: Dict, sector_data: Dict = None) -> str:
        """
        生成详细交易计划
        """
        plan = []
        
        # 股票基本信息
        plan.append(f"📋 交易计划: {stock_data.get('name', 'N/A')} ({stock_data.get('symbol', 'N/A')})")
        plan.append(f"   当前价格: {stock_data.get('price', 0):.2f} | 今日涨跌: {stock_data.get('change_pct', 0):.2f}%")
        plan.append(f"   综合评分: {stock_data.get('total_score', 0)}/100 | 入场信号: {stock_data.get('entry_signal', 'N/A')}")
        
        # 板块信息
        if 'sector_name' in stock_data:
            plan.append(f"   所属板块: {stock_data['sector_name']}")
        if 'sector_score' in stock_data:
            plan.append(f"   板块强度: {stock_data['sector_score']}/100")
        
        # 买入建议
        market_condition = "normal"  # 可以根据实际情况判断
        buy_signal = ShortTermTradingDecision.get_buy_signal(stock_data, market_condition)
        
        plan.append(f"\n🎯 操作建议: {buy_signal['suggested_action']}")
        
        if buy_signal['suggested_action'] != '观望':
            # 价格建议
            low, high = buy_signal['buy_price_range']
            plan.append(f"   建议买入区间: {low:.2f} - {high:.2f}")
            plan.append(f"   理想买入价: {(low+high)/2:.2f} (±{((high-low)/low*100):.1f}%)")
            
            # 仓位管理
            plan.append(f"   建议仓位: {buy_signal['position_size']*100:.1f}% (单只股票)")
            plan.append(f"   建议持有: {buy_signal['holding_days']}个交易日")
            
            # 风控参数
            plan.append(f"   止损位置: {buy_signal['stop_loss_price']:.2f}")
            plan.append(f"   目标价格: {buy_signal['target_price']:.2f}")
            plan.append(f"   风险收益比: 1:{buy_signal['risk_reward_ratio']:.1f}")
            
            # 交易备注
            if buy_signal['trading_notes']:
                plan.append(f"   备注: {'; '.join(buy_signal['trading_notes'])}")
            
            # 具体操作步骤
            plan.append(f"\n📝 具体操作步骤:")
            plan.append(f"   1. 次日开盘观察9:30-9:45走势")
            plan.append(f"   2. 确认成交量健康、趋势延续")
            plan.append(f"   3. 在建议区间内分批买入")
            plan.append(f"   4. 买入后立即设置止损单")
            plan.append(f"   5. 每日收盘检查持仓情况")
            
        return "\n".join(plan)
    
    @staticmethod
    def pre_buy_checklist(stock_data: Dict, market_data: Dict = None) -> Tuple[bool, list]:
        """买入前检查清单"""
        checks = []
        market_data = market_data or {}
        
        # 1. 技术面检查
        if stock_data.get('total_score', 0) >= 65:
            checks.append("✅ 技术评分≥65")
        else:
            checks.append("❌ 技术评分不足")
        
        # 2. 板块强度
        if stock_data.get('sector_score', 0) >= 60:
            checks.append("✅ 板块强度≥60")
        else:
            checks.append("❌ 板块偏弱")
        
        # 3. 市场环境
        market_trend = market_data.get('market_trend', 'neutral')
        if market_trend != 'downtrend':
            checks.append("✅ 市场非单边下跌")
        else:
            checks.append("❌ 市场单边下跌")
        
        # 4. 成交量检查
        volume_ratio = stock_data.get('volume_ratio', 1)
        if volume_ratio >= 0.8:
            checks.append("✅ 成交量健康")
        else:
            checks.append("❌ 成交量不足")
        
        # 5. 价格位置
        current_price = stock_data.get('price', 0)
        stop_loss = stock_data.get('stop_loss', 0)
        if current_price > 0 and stop_loss > 0:
            if current_price > stop_loss * 1.03:
                checks.append("✅ 价格离止损位>3%")
            else:
                checks.append("❌ 离止损位太近")
        else:
            checks.append("⚠️  无法判断价格位置")
        
        # 至少4个✅才能买入
        passed = sum(1 for check in checks if check.startswith('✅')) >= 4
        
        return passed, checks
