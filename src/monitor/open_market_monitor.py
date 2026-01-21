"""
开盘市场监控器 - 监控 9:30-9:45 的关键信号

目标：用尽量少的请求频率，对 watchlist 内股票做“开盘是否延续强势”的确认。
"""

from __future__ import annotations

import logging
import time as ttime
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import akshare as ak
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class OpenMonitorConfig:
    monitor_minutes: int = 15          # 监控时长（分钟）
    check_interval_sec: int = 30       # 检查间隔（秒）
    required_signals: int = 2          # ≥N 个信号 -> 考虑买入
    min_volume_ratio: float = 1.3      # 相对近期分时量能（近5分钟均量）放大倍数
    max_price_deviation: float = 0.03  # 相对昨日收盘（估算）允许偏离
    max_watchlist_display: int = 12    # 面板最多显示


class OpenMarketMonitor:
    """开盘市场监控器"""

    def __init__(self, watchlist: List[Dict[str, Any]], config: Optional[Dict[str, Any]] = None):
        self.watchlist = watchlist
        base = OpenMonitorConfig()
        if config:
            for k, v in config.items():
                if hasattr(base, k):
                    setattr(base, k, v)
        self.config = base

        self.monitor_data: Dict[str, Dict[str, Any]] = {}

    def start_monitoring(self, start_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        开始监控。
        默认从“现在”开始计时 monitor_minutes；外部也可传入 start_time 便于测试。
        """
        logger.info("开始开盘监控（目标窗口：9:30-9:45）")
        logger.info("监控股票数: %s", len(self.watchlist))

        start_time = start_time or datetime.now()
        end_time = start_time + timedelta(minutes=self.config.monitor_minutes)

        # 初始化结构
        for stock in self.watchlist:
            symbol = stock.get("symbol", "")
            if not symbol:
                continue
            self.monitor_data[symbol] = {
                "name": stock.get("name", ""),
                "signals": [],
                "signal_count": 0,
                "decision": "pending",
                "current_price": np.nan,
                "change_pct": np.nan,
                "volume": np.nan,
                "last_update": None,
            }

        print("\n" + "=" * 90)
        print("开盘实时监控面板（建议 9:30-9:45 运行）")
        print("=" * 90)

        last_tick = 0.0
        while datetime.now() < end_time:
            now = datetime.now()
            if (now.timestamp() - last_tick) >= self.config.check_interval_sec:
                last_tick = now.timestamp()
                self._update_all_stocks()
                self._display_monitor_panel()
            ttime.sleep(1)

        print("\n" + "=" * 90)
        print("开盘监控结束，生成买入决策")
        print("=" * 90)
        return self._generate_final_decisions()

    def _update_all_stocks(self) -> None:
        """更新所有监控股票的数据"""
        total = len(self.watchlist)
        for idx, stock in enumerate(self.watchlist, 1):
            symbol = stock.get("symbol", "")
            if not symbol:
                continue
            try:
                # 显示进度（每10只显示一次，避免刷屏）
                if idx % 10 == 0 or idx == total:
                    print(f"  正在更新数据: {idx}/{total} ({stock.get('name', symbol)})", end='\r')
                self._update_stock_data(symbol)
            except Exception as e:
                logger.warning("更新股票 %s 失败: %s", symbol, e)
        # 清除进度行
        print(" " * 80, end='\r')

    def _update_stock_data(self, symbol: str) -> None:
        realtime = self._get_realtime_data(symbol)
        if realtime is None:
            return

        current_price = float(realtime.get("current_price", np.nan))
        volume = float(realtime.get("volume", np.nan))
        change_pct = float(realtime.get("change_pct", np.nan))

        tick_df = self._get_tick_data(symbol)
        signals = self._analyze_open_signals(symbol, current_price, volume, change_pct, tick_df)

        d = self.monitor_data.get(symbol, {})
        d.update(
            current_price=current_price,
            change_pct=change_pct,
            volume=volume,
            signals=signals,
            signal_count=len(signals),
            last_update=datetime.now(),
            decision="positive" if len(signals) >= self.config.required_signals else ("watch" if len(signals) == 1 else "negative"),
        )
        self.monitor_data[symbol] = d

    def _get_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情数据。
        优先用“全市场实时行情”筛选目标股票（一次请求），避免每只股票单独请求。
        """
        code = symbol.replace(".SS", "").replace(".SZ", "")
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                # 兼容列名
                code_col = "代码" if "代码" in df.columns else df.columns[1]
                row = df[df[code_col].astype(str) == str(code)]
                if not row.empty:
                    r0 = row.iloc[0]
                    # 常见列名
                    def _get(col_cn: str, fallback: float = np.nan) -> float:
                        return float(pd.to_numeric(r0.get(col_cn, fallback), errors="coerce"))

                    return {
                        "current_price": _get("最新价"),
                        "change_pct": _get("涨跌幅"),
                        "volume": _get("成交量"),
                        "amount": _get("成交额"),
                        "open": _get("今开"),
                        "high": _get("最高"),
                        "low": _get("最低"),
                    }
        except Exception as e:
            logger.debug("stock_zh_a_spot_em 获取失败 %s: %s", symbol, e)

        # 备用：分钟线（会更慢，尽量少用）
        try:
            df_min = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period="1",
                start_date=datetime.now().strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="",
            )
            if df_min is not None and not df_min.empty:
                last = df_min.iloc[-1]
                close = float(pd.to_numeric(last.get("收盘", np.nan), errors="coerce"))
                vol = float(pd.to_numeric(last.get("成交量", np.nan), errors="coerce"))
                return {"current_price": close, "change_pct": np.nan, "volume": vol}
        except Exception as e:
            logger.debug("分钟线备用接口失败 %s: %s", symbol, e)

        return None

    def _get_tick_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取当日 1 分钟线数据（用于分时信号）"""
        code = symbol.replace(".SS", "").replace(".SZ", "")
        try:
            tick_df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period="1",
                start_date=datetime.now().strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
                adjust="",
            )
            if tick_df is None or tick_df.empty:
                return None

            # 尝试统一字段
            # AKShare 分钟线常见列：["日期", "时间", "开盘", "收盘", "最高", "最低", "成交量", "成交额", ...]
            date_col = "日期" if "日期" in tick_df.columns else tick_df.columns[0]
            time_col = "时间" if "时间" in tick_df.columns else tick_df.columns[1]
            close_col = "收盘" if "收盘" in tick_df.columns else None
            vol_col = "成交量" if "成交量" in tick_df.columns else None

            df = tick_df.copy()
            if close_col is None:
                return None

            # 彻底避免 pandas 的 “Could not infer format” 警告：
            # - 先把日期/时间字符串规范化（补秒、去空格）
            # - 再用明确的 format 解析（分别尝试“有秒/无秒”、“带横杠/纯数字”）
            date_s = df[date_col].astype(str).str.strip()
            time_s = df[time_col].astype(str).str.strip()

            # 统一时间为 HH:MM:SS（如果是 HH:MM 则补 :00）
            time_s = time_s.where(time_s.str.len() != 5, time_s + ":00")

            dt_str = (date_s + " " + time_s).str.replace(r"\s+", " ", regex=True)

            dt = pd.to_datetime(dt_str, format="%Y-%m-%d %H:%M:%S", errors="coerce")
            if dt.isna().all():
                dt = pd.to_datetime(dt_str, format="%Y-%m-%d %H:%M", errors="coerce")
            if dt.isna().all():
                dt = pd.to_datetime(dt_str, format="%Y%m%d %H:%M:%S", errors="coerce")
            if dt.isna().all():
                dt = pd.to_datetime(dt_str, format="%Y%m%d %H:%M", errors="coerce")

            # 仍然全 NaT：直接放弃（不要再走“自动推断”，避免刷屏警告）
            if dt.isna().all():
                logger.debug("分时时间解析失败 %s: date_col=%s time_col=%s sample=%s", symbol, date_col, time_col, dt_str.iloc[0] if len(dt_str) else "")
                return None

            df["dt"] = dt
            
            df = df.sort_values("dt")
            df["close"] = pd.to_numeric(df[close_col], errors="coerce")
            if vol_col:
                df["vol"] = pd.to_numeric(df[vol_col], errors="coerce")
            else:
                df["vol"] = np.nan
            df["ma5"] = df["close"].rolling(5).mean()
            return df
        except Exception as e:
            logger.debug("获取分时失败 %s: %s", symbol, e)
            return None

    def _analyze_open_signals(
        self,
        symbol: str,
        current_price: float,
        volume: float,
        change_pct: float,
        tick_data: Optional[pd.DataFrame],
    ) -> List[str]:
        """分析开盘信号（越少越稳健，避免过拟合）"""
        signals: List[str] = []

        # 1) 价格/相对强度（注意判断顺序）
        if pd.notna(change_pct):
            if change_pct > 0.5:
                signals.append("相对强势(>0.5%)")
            elif change_pct > 0:
                signals.append("价格上涨")

        # 2) 分时逐级抬升（最近 5 根 close 单调上升）
        if tick_data is not None and len(tick_data) >= 6:
            recent = tick_data["close"].tail(5).dropna().values
            if len(recent) >= 4:
                if all(recent[i] >= recent[i - 1] for i in range(1, len(recent))):
                    signals.append("分时逐级抬升")

        # 3) 价格在分时均线之上
        if tick_data is not None and "ma5" in tick_data.columns and len(tick_data) >= 6:
            last_ma5 = tick_data["ma5"].iloc[-1]
            if pd.notna(last_ma5) and pd.notna(current_price) and current_price > float(last_ma5):
                signals.append("价格在分时均线上方")

        # 4) 量能（用近5分钟均量作基准，避免跨日同刻对比的重请求）
        if tick_data is not None and "vol" in tick_data.columns and len(tick_data) >= 10:
            recent_vol = tick_data["vol"].tail(6).dropna()
            if len(recent_vol) >= 3:
                baseline = float(recent_vol.iloc[:-1].mean()) if len(recent_vol) > 1 else float(recent_vol.mean())
                cur = float(recent_vol.iloc[-1])
                if baseline > 0:
                    ratio = cur / baseline
                    if ratio >= self.config.min_volume_ratio:
                        signals.append(f"量能放大(x{ratio:.1f})")

        # 5) 走势稳定（近10分钟波动小）
        if tick_data is not None and len(tick_data) >= 12 and pd.notna(current_price) and current_price > 0:
            std = tick_data["close"].tail(10).dropna().std()
            if pd.notna(std) and (std / current_price) < 0.005:
                signals.append("走势稳定(低波动)")

        return signals

    def _display_monitor_panel(self) -> None:
        # 尽量不使用 ANSI 颜色，兼容 PowerShell/日志
        now_str = datetime.now().strftime("%H:%M:%S")
        print("\n" + "-" * 90)
        print(f"监控时间: {now_str} | 监控股票数: {len(self.watchlist)}")
        print("-" * 90)
        print(f"{'股票':<10} {'价格':>8} {'涨幅':>8} {'信号':>4}  {'关键信号':<45} {'决策':<8}")
        print("-" * 90)

        items = []
        for s in self.watchlist:
            sym = s.get("symbol", "")
            if not sym:
                continue
            d = self.monitor_data.get(sym, {})
            items.append((sym, d.get("signal_count", 0)))

        items.sort(key=lambda x: x[1], reverse=True)
        for sym, _ in items[: self.config.max_watchlist_display]:
            d = self.monitor_data.get(sym, {})
            name = (d.get("name") or "")[:4]
            price = d.get("current_price", np.nan)
            chg = d.get("change_pct", np.nan)
            sigs = d.get("signals", [])
            sig_text = ", ".join(sigs[:3])
            decision = d.get("decision", "pending")
            decision_text = {"positive": "考虑", "watch": "观察", "negative": "放弃"}.get(decision, "观察")
            print(f"{name:<10} {price:>8.2f} {chg:>7.2f}% {len(sigs):>4}  {sig_text:<45} {decision_text:<8}")

        print("-" * 90)
        print(f"决策规则：≥{self.config.required_signals} 信号=考虑；1 信号=观察；0 信号=放弃")

    def _generate_final_decisions(self) -> Dict[str, Any]:
        decisions = {"buy_recommended": [], "watch_list": [], "avoid_list": [], "monitor_summary": {}}

        for stock in self.watchlist:
            symbol = stock.get("symbol", "")
            if not symbol:
                continue
            d = self.monitor_data.get(symbol, {})
            sig_count = int(d.get("signal_count", 0) or 0)
            info = {
                "symbol": symbol,
                "name": stock.get("name", d.get("name", "")),
                "current_price": d.get("current_price", np.nan),
                "change_pct": d.get("change_pct", np.nan),
                "signals": d.get("signals", []),
                "signal_count": sig_count,
            }
            if sig_count >= self.config.required_signals:
                decisions["buy_recommended"].append(info)
            elif sig_count >= 1:
                decisions["watch_list"].append(info)
            else:
                decisions["avoid_list"].append(info)

        decisions["monitor_summary"] = {
            "total_stocks": len(self.watchlist),
            "buy_recommended": len(decisions["buy_recommended"]),
            "watch_list": len(decisions["watch_list"]),
            "avoid_list": len(decisions["avoid_list"]),
            "monitor_end_time": datetime.now().strftime("%H:%M:%S"),
        }
        return decisions

