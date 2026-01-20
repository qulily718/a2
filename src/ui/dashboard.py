"""
主仪表板
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict

def render_dashboard(recommended_stocks: List[Dict], 
                    sector_analysis: pd.DataFrame):
    """渲染主仪表板"""
    st.title("📊 短线稳健策略执行系统")
    
    st.header("📈 板块强度分析")
    if not sector_analysis.empty:
        st.dataframe(sector_analysis, use_container_width=True)
    
    st.header("🎯 推荐个股")
    if recommended_stocks:
        stocks_df = pd.DataFrame(recommended_stocks)
        st.dataframe(stocks_df, use_container_width=True)
    else:
        st.info("暂无推荐个股")
    
    st.sidebar.header("系统信息")
    st.sidebar.write(f"更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
