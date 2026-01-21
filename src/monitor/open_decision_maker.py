"""
开盘决策生成器 - 基于监控结果 + 盘前计划 生成具体买入指令
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class OpenDecisionMaker:
    """开盘决策生成器"""

    def __init__(self, pre_market_analysis: Dict[str, Any]):
        """
        Args:
            pre_market_analysis: 盘前分析结果（推荐股票列表等）
        """
        self.pre_market_analysis = pre_market_analysis or {}

    def generate_trading_instructions(self, monitor_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成交易指令

        Returns:
            {
              immediate_buy: [...],
              wait_buy: [...],
              cancel_buy: [...],
              summary: {...}
            }
        """
        print("\n" + "=" * 90)
        print("生成开盘交易指令（基于 9:30-9:45 监控 + 盘前计划）")
        print("=" * 90)

        instructions = {"immediate_buy": [], "wait_buy": [], "cancel_buy": [], "summary": {}}

        for stock in monitor_results.get("buy_recommended", []):
            symbol = stock.get("symbol", "")
            pre = self._find_pre_market_info(symbol)
            if not pre:
                logger.warning("找不到 %s 的盘前信息，跳过", symbol)
                continue
            instr = self._create_buy_instruction(stock, pre)
            (instructions["immediate_buy"] if instr["urgency"] == "high" else instructions["wait_buy"]).append(instr)

        for stock in monitor_results.get("avoid_list", []):
            symbol = stock.get("symbol", "")
            pre = self._find_pre_market_info(symbol)
            if pre:
                instructions["cancel_buy"].append(
                    {
                        "symbol": symbol,
                        "name": stock.get("name", ""),
                        "action": "cancel",
                        "reason": "开盘信号不足",
                        "current_price": stock.get("current_price", 0),
                        "pre_market_target": pre.get("target_price", 0),
                        "notes": f"仅获得 {stock.get('signal_count', 0)} 个开盘信号",
                    }
                )

        instructions["summary"] = self._generate_summary(instructions, monitor_results)
        return instructions

    def _find_pre_market_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        for stock in self.pre_market_analysis.get("recommended_stocks", []):
            if stock.get("symbol") == symbol:
                return stock
        return None

    def _create_buy_instruction(self, realtime_data: Dict[str, Any], pre_market_info: Dict[str, Any]) -> Dict[str, Any]:
        symbol = realtime_data.get("symbol", "")
        current_price = float(realtime_data.get("current_price", 0) or 0)
        change_pct = float(realtime_data.get("change_pct", 0) or 0)

        target_price = float(pre_market_info.get("target_price", 0) or 0)
        stop_loss = float(pre_market_info.get("stop_loss", 0) or 0)
        suggested_range = pre_market_info.get("buy_price_range", (0, 0))
        position_size = float(pre_market_info.get("position_size", pre_market_info.get("buy_position_size", 0.05)) or 0.05)

        in_range = False
        low = high = 0.0
        if isinstance(suggested_range, (tuple, list)) and len(suggested_range) == 2:
            low, high = float(suggested_range[0] or 0), float(suggested_range[1] or 0)
            in_range = low <= current_price <= high if low > 0 and high > 0 else False

        # 风险收益比
        risk = (current_price - stop_loss) if stop_loss > 0 else (current_price * 0.05)
        reward = (target_price - current_price) if target_price > current_price else (current_price * 0.08)
        rr = (reward / risk) if risk > 0 else 0

        urgency = "medium"
        reasons: List[str] = []

        if change_pct > 1.5:
            urgency = "high"
            reasons.append("开盘强势上涨")
        elif change_pct < 0:
            urgency = "low"
            reasons.append("开盘回调")

        if in_range:
            reasons.append("在盘前建议区间内")
            if urgency == "medium":
                urgency = "high"
        else:
            if low > 0 and high > 0:
                reasons.append("价格偏离建议区间")
                if current_price > high:
                    urgency = "low"
                    reasons.append("价格偏高")

        if rr >= 3:
            reasons.append("风险收益比优秀(≥3)")
            urgency = "high"
        elif rr < 1.5:
            reasons.append("风险收益比较低(<1.5)")
            urgency = "low"

        if urgency == "high":
            price_suggestion = f"立即买入 @ {current_price:.2f}"
            timing = "9:45前完成"
            final_pos = position_size
        elif urgency == "medium":
            price_suggestion = f"等待回调至 {current_price * 0.99:.2f} 附近"
            timing = "10:00-10:30观察"
            final_pos = position_size * 0.8
        else:
            price_suggestion = f"观望，回调到 {low:.2f} 附近再评估" if low > 0 else "观望"
            timing = "盘中观察"
            final_pos = position_size * 0.5

        return {
            "symbol": symbol,
            "name": realtime_data.get("name", ""),
            "action": "buy",
            "urgency": urgency,
            "current_price": current_price,
            "change_pct": change_pct,
            "pre_market_target": target_price,
            "stop_loss": stop_loss,
            "risk_reward_ratio": round(rr, 2),
            "price_suggestion": price_suggestion,
            "timing": timing,
            "position_size": round(final_pos, 4),
            "reasons": reasons,
            "signals": realtime_data.get("signals", []),
            "signal_count": int(realtime_data.get("signal_count", 0) or 0),
        }

    def _generate_summary(self, instructions: Dict[str, Any], monitor_results: Dict[str, Any]) -> Dict[str, Any]:
        ms = monitor_results.get("monitor_summary", {})
        total = int(ms.get("total_stocks", 0) or 0)
        buy = int(ms.get("buy_recommended", 0) or 0)
        ratio = (buy / total) if total > 0 else 0

        if ratio >= 0.3:
            market_status = "强势市场"
        elif ratio >= 0.15:
            market_status = "正常市场"
        elif ratio >= 0.05:
            market_status = "弱势市场"
        else:
            market_status = "极弱市场"

        rec_actions: List[str] = []
        if instructions["immediate_buy"]:
            rec_actions.append(f"立即买入 {len(instructions['immediate_buy'])} 只强势股（优先在9:45前执行）")
        if instructions["wait_buy"]:
            rec_actions.append(f"等待回调/确认后买入 {len(instructions['wait_buy'])} 只观察股（10:00-10:30）")
        if not rec_actions:
            rec_actions.append("建议观望，开盘延续信号不足")

        return {
            "total_analyzed": total,
            "immediate_buy": len(instructions["immediate_buy"]),
            "wait_buy": len(instructions["wait_buy"]),
            "cancel_buy": len(instructions["cancel_buy"]),
            "market_status": market_status,
            "recommended_actions": rec_actions,
            "generation_time": datetime.now().strftime("%H:%M:%S"),
        }

    def display_instructions(self, instructions: Dict[str, Any]) -> None:
        print("\n" + "=" * 90)
        print("开盘交易指令汇总")
        print("=" * 90)

        if instructions["immediate_buy"]:
            print("\n立即买入（建议 9:45 前完成）")
            print("-" * 90)
            for i, instr in enumerate(instructions["immediate_buy"], 1):
                print(f"{i}. {instr['name']} ({instr['symbol']})")
                print(f"   当前价: {instr['current_price']:.2f}  涨幅: {instr['change_pct']:+.2f}%")
                print(f"   建议: {instr['price_suggestion']}")
                print(f"   仓位: {instr['position_size']*100:.1f}%  止损: {instr['stop_loss']:.2f}  RR: {instr['risk_reward_ratio']}")
                print(f"   理由: {', '.join(instr['reasons'][:3])}")
                print(f"   信号: {', '.join(instr.get('signals', [])[:3])}")

        if instructions["wait_buy"]:
            print("\n等待买入（建议 10:00-10:30 观察）")
            print("-" * 90)
            for i, instr in enumerate(instructions["wait_buy"], 1):
                print(f"{i}. {instr['name']} ({instr['symbol']})")
                print(f"   当前价: {instr['current_price']:.2f}  涨幅: {instr['change_pct']:+.2f}%")
                print(f"   建议: {instr['price_suggestion']}  时机: {instr['timing']}")

        if instructions["cancel_buy"]:
            print("\n取消买入（开盘信号不足）")
            print("-" * 90)
            for i, instr in enumerate(instructions["cancel_buy"][:10], 1):
                print(f"{i}. {instr['name']} ({instr['symbol']}) - {instr['notes']}")

        s = instructions["summary"]
        print("\n" + "-" * 90)
        print("开盘决策总结")
        print("-" * 90)
        print(f"分析股票数: {s.get('total_analyzed', 0)}")
        print(f"立即买入: {s.get('immediate_buy', 0)} | 等待买入: {s.get('wait_buy', 0)} | 取消: {s.get('cancel_buy', 0)}")
        print(f"市场状态: {s.get('market_status', 'N/A')}")
        print("操作建议:")
        for a in s.get("recommended_actions", []):
            print(f"  - {a}")
        print(f"生成时间: {s.get('generation_time', '')}")
        print("=" * 90)

