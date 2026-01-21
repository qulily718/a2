"""
开盘监控主程序 - 建议在交易日 9:30-9:45 运行

用法：
  python monitor_open_market.py
  python monitor_open_market.py --force        # 超过 9:45 也继续跑（不交互）
  python monitor_open_market.py --max-monitor 20
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, time as dtime
from typing import Dict, Any, List

import numpy as np
import pandas as pd

# 添加项目路径（支持直接运行该脚本）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.monitor.open_market_monitor import OpenMarketMonitor
from src.monitor.open_decision_maker import OpenDecisionMaker


def _find_latest_csv(results_dir: str, patterns: List[str]) -> str | None:
    import glob

    files: List[str] = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(results_dir, p)))
    if not files:
        return None
    return max(files, key=os.path.getctime)


def load_pre_market_analysis(results_dir: str = "results") -> Dict[str, Any] | None:
    """
    从 results/ 读取最近一次盘前分析输出。
    优先读取 main_realtime.py 产出的 recommended_stocks_*.csv；
    如果不存在，则退回 simple_recommendations_*.csv / recommendations_*.csv。
    """
    if not os.path.exists(results_dir):
        print("结果目录不存在，请先运行盘前分析（例如 main_realtime.py）")
        return None

    latest = _find_latest_csv(
        results_dir,
        patterns=[
            "recommended_stocks_*.csv",
            "stocks_simple_*.csv",
            "simple_recommendations_*.csv",
            "recommendations_*.csv",
        ],
    )
    if latest is None:
        print("找不到盘前分析 CSV，请先运行盘前分析（例如 main_realtime.py）")
        return None

    print(f"加载盘前分析文件: {latest}")
    df = pd.read_csv(latest, encoding="utf-8-sig")
    if df.empty:
        print("盘前分析文件为空")
        return None

    # 规范化字段
    def _to_float(x: Any, default: float = 0.0) -> float:
        v = pd.to_numeric(x, errors="coerce")
        return float(v) if pd.notna(v) else default

    watchlist: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        symbol = str(row.get("symbol", "")).strip()
        if not symbol:
            continue
        watchlist.append(
            {
                "symbol": symbol,
                "name": str(row.get("name", "")).strip(),
                "sector_name": str(row.get("sector_name", row.get("sector", ""))).strip(),
                "pre_market_score": _to_float(row.get("total_score", 0)),
                "pre_market_signal": str(row.get("entry_signal", "")).strip(),
                "stop_loss": _to_float(row.get("stop_loss", 0)),
                "target_price": _to_float(row.get("buy_target_price", 0), default=0.0)
                or (_to_float(row.get("price", 0)) * 1.08),
                # 若 CSV 里存在展开后的 buy_* 字段，则带上
                "buy_price_range": (
                    _to_float(row.get("buy_buy_price_range", 0), default=0.0),
                    _to_float(row.get("buy_buy_price_range", 0), default=0.0),
                ),
                "position_size": _to_float(row.get("buy_position_size", 0.05), default=0.05),
            }
        )

    return {"file": os.path.basename(latest), "recommended_stocks": watchlist, "total_stocks": len(watchlist)}


def check_market_time(force: bool) -> bool:
    now = datetime.now().time()
    start = dtime(9, 30)
    end = dtime(9, 45)
    if now < start:
        print(f"当前时间 {now.strftime('%H:%M')}，未到开盘监控窗口（9:30-9:45）")
        return False
    if now > end and not force:
        print(f"当前时间 {now.strftime('%H:%M')}，已过最佳监控窗口（9:30-9:45）")
        print("可使用 --force 强制运行（不交互）")
        return False
    if now > end and force:
        print(f"当前时间 {now.strftime('%H:%M')}，已过最佳窗口，但将继续运行（--force）")
    return True


def save_results(instructions: Dict[str, Any], monitor_results: Dict[str, Any]) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = "monitor_results"
    os.makedirs(out_dir, exist_ok=True)

    # JSON
    json_path = os.path.join(out_dir, f"trading_instructions_{ts}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"instructions": instructions, "monitor_results": monitor_results}, f, ensure_ascii=False, indent=2, default=str)
    print(f"已保存: {json_path}")

    # CSV 汇总
    all_rows: List[Dict[str, Any]] = []
    for cat in ["immediate_buy", "wait_buy", "cancel_buy"]:
        for r in instructions.get(cat, []):
            rr = dict(r)
            rr["category"] = cat
            all_rows.append(rr)
    if all_rows:
        df = pd.DataFrame(all_rows)
        csv_path = os.path.join(out_dir, f"all_instructions_{ts}.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        print(f"已保存: {csv_path}")

    return ts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="超过 9:45 也继续运行（不交互）")
    parser.add_argument("--max-monitor", type=int, default=20, help="最多监控股票数量（默认 20）")
    parser.add_argument("--interval", type=int, default=30, help="刷新间隔秒（默认 30）")
    args = parser.parse_args()

    print("=" * 90)
    print("短线策略 - 开盘实时监控系统")
    print("=" * 90)
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not check_market_time(force=args.force):
        return

    pre = load_pre_market_analysis()
    if pre is None:
        print("无法加载盘前分析，退出")
        return

    watchlist = pre["recommended_stocks"]
    if len(watchlist) > args.max_monitor:
        print(f"监控列表过大({len(watchlist)})，截断为前 {args.max_monitor} 只")
        watchlist = watchlist[: args.max_monitor]

    print(f"\n📊 准备监控 {len(watchlist)} 只股票")
    print(f"⏱️  监控时长: 15分钟 | 检查间隔: {args.interval}秒")
    print("⚠️  注意：如果看到进度条，这是 akshare 库在获取数据，请耐心等待...\n")
    
    monitor = OpenMarketMonitor(watchlist, config={"check_interval_sec": args.interval})
    monitor_results = monitor.start_monitoring()

    decision_maker = OpenDecisionMaker(pre)
    instructions = decision_maker.generate_trading_instructions(monitor_results)
    decision_maker.display_instructions(instructions)

    ts = save_results(instructions, monitor_results)
    print("=" * 90)
    print(f"开盘监控完成，结果时间戳: {ts}")
    print("=" * 90)


if __name__ == "__main__":
    try:
        import akshare  # noqa: F401
    except Exception as e:
        print(f"缺少依赖或 akshare 不可用: {e}")
        sys.exit(1)
    main()

