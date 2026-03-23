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
        self._spot_df_cache: Optional[pd.DataFrame] = None  # 缓存全市场实时行情（避免重复请求）
        self._spot_df_cache_time: Optional[datetime] = None
        self._spot_df_cache_ttl = 10  # 缓存有效期（秒）
        # 初始化时就创建数据获取器，确保整个监控过程使用同一个实例（BaoStock连接复用）
        from src.data.data_fetcher import ShortTermDataFetcher
        self._data_fetcher = ShortTermDataFetcher(use_cache=True, rate_limit=0.1)

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
        
        # 关闭数据获取器连接（如果有）
        if self._data_fetcher is not None:
            try:
                self._data_fetcher.close()
            except Exception:
                pass
        
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
            # 如果实时数据完全失败，至少尝试用历史数据填充基本信息
            logger.debug("实时数据获取失败，尝试用历史数据填充 %s", symbol)
            try:
                hist = self._data_fetcher.get_stock_history(symbol, period="5d")
                if not hist.empty and len(hist) >= 1:
                    latest = hist.iloc[-1]
                    current_price = float(pd.to_numeric(latest.get("close", np.nan), errors="coerce"))
                    change_pct = np.nan
                    if len(hist) >= 2:
                        yesterday_close = float(pd.to_numeric(hist['close'].iloc[-2], errors="coerce"))
                        if not pd.isna(current_price) and not pd.isna(yesterday_close) and yesterday_close > 0:
                            change_pct = (current_price / yesterday_close - 1) * 100
                    volume = float(pd.to_numeric(latest.get("volume", np.nan), errors="coerce"))
                    
                    # 使用历史数据填充（至少能显示价格和涨跌幅）
                    realtime = {
                        "current_price": current_price,
                        "change_pct": change_pct,
                        "volume": volume,
                    }
                    logger.info("使用历史数据填充 %s: 价格=%.2f, 涨跌幅=%.2f%%", symbol, current_price, change_pct if not pd.isna(change_pct) else 0)
                else:
                    return  # 历史数据也失败，跳过
            except Exception as e:
                logger.warning("历史数据降级也失败 %s: %s", symbol, e)
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
        添加重试机制和降级策略。
        """
        code = symbol.replace(".SS", "").replace(".SZ", "")
        
        # 1. 尝试从缓存获取全市场实时行情（避免重复请求）
        now = datetime.now()
        if (self._spot_df_cache is None or 
            self._spot_df_cache_time is None or 
            (now - self._spot_df_cache_time).total_seconds() > self._spot_df_cache_ttl):
            # 缓存过期或不存在，重新获取（带重试）
            for attempt in range(3):
                try:
                    self._spot_df_cache = ak.stock_zh_a_spot_em()
                    if self._spot_df_cache is not None and not self._spot_df_cache.empty:
                        self._spot_df_cache_time = now
                        break
                except Exception as e:
                    if attempt < 2:
                        logger.debug("stock_zh_a_spot_em 获取失败(第%d次): %s", attempt + 1, e)
                        ttime.sleep(0.5 * (attempt + 1))  # 简单退避
                    else:
                        logger.warning("stock_zh_a_spot_em 获取失败(3次均失败): %s", e)
                        self._spot_df_cache = None
        
        # 2. 从缓存中查找目标股票
        if self._spot_df_cache is not None and not self._spot_df_cache.empty:
            try:
                code_col = "代码" if "代码" in self._spot_df_cache.columns else self._spot_df_cache.columns[1]
                row = self._spot_df_cache[self._spot_df_cache[code_col].astype(str) == str(code)]
                if not row.empty:
                    r0 = row.iloc[0]
                    # 常见列名
                    def _get(col_cn: str, fallback: float = np.nan) -> float:
                        return float(pd.to_numeric(r0.get(col_cn, fallback), errors="coerce"))

                    change_pct = _get("涨跌幅")
                    current_price = _get("最新价")
                    
                    # 如果涨跌幅是 nan，尝试用当前价和今开价计算
                    if pd.isna(change_pct) and not pd.isna(current_price):
                        open_price = _get("今开")
                        if not pd.isna(open_price) and open_price > 0:
                            # 用当前价相对今开价计算（近似涨跌幅）
                            change_pct = (current_price / open_price - 1) * 100

                    return {
                        "current_price": current_price,
                        "change_pct": change_pct,
                        "volume": _get("成交量"),
                        "amount": _get("成交额"),
                        "open": _get("今开"),
                        "high": _get("最高"),
                        "low": _get("最低"),
                    }
            except Exception as e:
                logger.debug("从缓存解析股票 %s 数据失败: %s", symbol, e)

        # 3. 降级策略：直接从历史数据获取最新价格和涨跌幅
        # 如果实时数据完全失败，使用历史数据（BaoStock 作为备选）
        try:
            # 获取最近几天的历史数据（用于计算涨跌幅）
            hist = self._data_fetcher.get_stock_history(symbol, period="5d")
            if not hist.empty and len(hist) >= 1:
                # 使用最新一条数据的收盘价作为当前价格（近似）
                latest = hist.iloc[-1]
                current_price = float(pd.to_numeric(latest.get("close", np.nan), errors="coerce"))
                
                # 计算涨跌幅：相对于昨日收盘
                change_pct = np.nan
                if len(hist) >= 2:
                    yesterday_close = float(pd.to_numeric(hist['close'].iloc[-2], errors="coerce"))
                    if not pd.isna(current_price) and not pd.isna(yesterday_close) and yesterday_close > 0:
                        change_pct = (current_price / yesterday_close - 1) * 100
                        logger.debug("从历史数据计算 %s 涨跌幅: %.2f%% (当前价: %.2f, 昨收: %.2f)", 
                                   symbol, change_pct, current_price, yesterday_close)
                
                # 获取成交量（如果有）
                volume = float(pd.to_numeric(latest.get("volume", np.nan), errors="coerce"))
                
                if not pd.isna(current_price):
                    logger.info("使用历史数据作为 %s 的实时数据（实时接口失败）", symbol)
                    return {
                        "current_price": current_price,
                        "change_pct": change_pct,
                        "volume": volume,
                        "amount": float(pd.to_numeric(latest.get("amount", np.nan), errors="coerce")),
                        "open": float(pd.to_numeric(latest.get("open", np.nan), errors="coerce")),
                        "high": float(pd.to_numeric(latest.get("high", np.nan), errors="coerce")),
                        "low": float(pd.to_numeric(latest.get("low", np.nan), errors="coerce")),
                    }
        except Exception as e:
            logger.warning("降级到历史数据失败 %s: %s", symbol, e)

        # 4. 最后尝试：分钟线（如果历史数据也失败）
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
                current_price = float(pd.to_numeric(last.get("收盘", np.nan), errors="coerce"))
                vol = float(pd.to_numeric(last.get("成交量", np.nan), errors="coerce"))
                
                # 尝试计算涨跌幅：从历史数据获取昨日收盘价
                change_pct = np.nan
                if not pd.isna(current_price):
                    try:
                        hist = self._data_fetcher.get_stock_history(symbol, period="5d")
                        if not hist.empty and len(hist) >= 2:
                            yesterday_close = hist['close'].iloc[-2]  # 昨日收盘
                            if not pd.isna(yesterday_close) and yesterday_close > 0:
                                change_pct = (current_price / yesterday_close - 1) * 100
                                logger.debug("从分钟线+历史数据计算 %s 涨跌幅: %.2f%%", symbol, change_pct)
                    except Exception as e:
                        logger.debug("计算涨跌幅失败 %s: %s", symbol, e)
                
                return {"current_price": current_price, "change_pct": change_pct, "volume": vol}
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
            
            # 格式化涨跌幅显示
            if pd.isna(chg):
                chg_str = "  N/A"
            else:
                chg_str = f"{chg:>6.2f}%"
            
            print(f"{name:<10} {price:>8.2f} {chg_str:>7} {len(sigs):>4}  {sig_text:<45} {decision_text:<8}")

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

