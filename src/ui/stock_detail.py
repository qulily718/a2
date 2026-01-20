"""
个股详情视图
"""
import streamlit as st
import pandas as pd
from typing import Dict

def render_stock_detail(stock_info: Dict, hist_data: pd.DataFrame):
    """渲染个股详情"""
    st.header(f"📊 {stock_info['name']} ({stock_info['symbol']})")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("当前价格", f"{stock_info.get('price', 0):.2f}")
    col2.metric("涨跌幅", f"{stock_info.get('change_pct', 0):.2f}%")
    col3.metric("综合评分", f"{stock_info.get('total_score', 0):.1f}")
    col4.metric("技术评分", f"{stock_info.get('tech_score', 0):.1f}")
    
    st.subheader("评分理由")
    reasons = stock_info.get('reasons', [])
    for reason in reasons:
        st.write(f"- {reason}")
    
    if not hist_data.empty:
        st.subheader("价格走势")
        st.line_chart(hist_data['close'])
